# Architecture

**Analysis Date:** 2026-04-17

## Pattern Overview

**Overall:** Script-oriented modular monolith with a single long-running monitoring process

**Key Characteristics:**
- Root-level Python scripts are both the executable entry points and the module boundaries; there is no package directory such as `src/` or `trump_era_delta/`.
- `main.py` centralizes orchestration, statistical analysis, visualization generation, and alert triggering in one process.
- External integrations stay thin: `main.py` and `predict_prophet.py` import market data from the sibling `asset_prices` repository, while `send_gmail.py` handles outbound email over Gmail SMTP.
- Runtime state is mostly ephemeral `pandas` DataFrames plus a small amount of file-based output in `./plots` and `main.log`.

## Layers

**CLI And Orchestration Layer:**
- Purpose: Start the monitor, run one-off test flows, and expose standalone CLIs.
- Location: `main.py`, `predict_prophet.py`, `send_gmail.py`, `send_test_email.py`
- Contains: `argparse` parsing, infinite-loop control flow, mode selection, and manual verification flows.
- Depends on: Standard library CLI/file APIs, local helper modules, and external services.
- Used by: Shell execution and process managers such as the `systemd` example in `README.md`.

**Market Data Boundary:**
- Purpose: Read parquet-backed market data from the sibling `asset_prices` project and normalize it into a consistent frame.
- Location: `main.py`, `predict_prophet.py`
- Contains: `ASSET_PRICES_REPO`, `ASSET_PRICES_DATA_DIR`, `DEFAULT_DATA_TYPE`, and `load_data(...)`.
- Depends on: External `lib.read_utils.read_symbol_data` imported by mutating `sys.path`.
- Used by: The continuous monitor in `main.py`, the forecast workflow in `predict_prophet.py`, and the manual verification script `send_test_email.py`.

**Statistical Analysis Layer:**
- Purpose: Transform normalized prices into cumulative-return series, regression bands, and band classifications.
- Location: `main.py`, `predict_prophet.py`
- Contains: `calculate_cumulative_pct_change(...)`, `calculate_regression_bands(...)`, `get_regression_band(...)`, `calculate_daily_pct_change(...)`, `prepare_aligned_data(...)`, and `predict_for_new_period(...)`.
- Depends on: `pandas`, `numpy`, and `prophet`.
- Used by: Plot generation, band-change detection, and email composition inputs.

**Visualization Layer:**
- Purpose: Turn analyzed data into static and interactive chart artifacts.
- Location: `main.py`, `predict_prophet.py`
- Contains: `plot_comparison(...)`, Plotly figure assembly, HTML wrapping, and image export.
- Depends on: `plotly`, `kaleido`, and filesystem writes to `./plots`.
- Used by: The production monitoring loop in `main.py`, the one-off email flow in `send_test_email.py`, and the forecast CLI in `predict_prophet.py`.

**Notification Composition Layer:**
- Purpose: Render domain metrics into polished alert content without handling transport.
- Location: `email_template.py`
- Contains: Color/presentation helpers plus `build_email_content(...)`.
- Depends on: Standard library typing helpers only.
- Used by: `main.py` and `send_test_email.py`.

**Notification Delivery Layer:**
- Purpose: Authenticate with Gmail and send multipart emails with optional inline images and attachments.
- Location: `send_gmail.py`
- Contains: `load_config()`, `send_email(...)`, and a standalone mailer CLI.
- Depends on: `smtplib`, MIME helpers from the standard library, `pathlib`, and external credentials stored in `~/.gmail_send/.env`.
- Used by: `main.py`, `send_test_email.py`, and direct CLI usage of `send_gmail.py`.

## Data Flow

**Continuous Monitoring Flow:**

1. `main.py` parses CLI flags, loads recipients from `email_recipients.txt`, and chooses between `send_test_email_now(...)` and `main_loop(...)`.
2. `main_loop(...)` in `main.py` resolves the earliest required date, calls `load_data(...)`, and normalizes the imported `asset_prices` frame into `index` and `adj_close`.
3. `calculate_cumulative_pct_change(...)` and `calculate_regression_bands(...)` in `main.py` derive the full benchmark frame, the truncated benchmark frame, and the current-period frame.
4. `get_regression_band(...)` in `main.py` classifies the most recent cumulative return against the truncated benchmark bands.
5. `plot_comparison(...)` in `main.py` writes `./plots/{symbol}_zoomed_{source}.jpeg`, `./plots/{symbol}_full_{source}.jpeg`, and `./plots/{symbol}_{source}.html`, then optionally copies the HTML file to `--html_output_path`.
6. When `current_band` differs from the in-memory `previous_band`, `build_email_content(...)` in `email_template.py` renders the alert body and `send_email(...)` in `send_gmail.py` delivers it with inline chart images.
7. `main_loop(...)` logs progress to `main.log`, sleeps for `--check_frequency` minutes, and repeats.

**Forecast Exploration Flow:**

1. `predict_prophet.py` parses a one-shot CLI invocation and loads the same external market data boundary used by `main.py`.
2. `prepare_aligned_data(...)` and `calculate_daily_pct_change(...)` in `predict_prophet.py` create aligned training and current-period frames.
3. `predict_for_new_period(...)` in `predict_prophet.py` fits a `Prophet` model and emits forecasted cumulative percent change for the new period.
4. `plot_comparison(...)` in `predict_prophet.py` writes a multi-panel HTML report to `./plots/{symbol}_comparison.html`.

**State Management:**
- Cross-iteration state is a single `previous_band` variable inside `main_loop(...)` in `main.py`; there is no database, cache, or persisted run history.
- Per-run state lives in local `pandas` DataFrames such as `df_original`, `df_original_truncated`, and `df_new` inside `main.py`, plus `df_old`, `df_new`, and `forecast` inside `predict_prophet.py`.
- Persistent outputs are filesystem artifacts only: `main.log`, the runtime-created `./plots/` directory, and the optional copied HTML output from `--html_output_path`.

## Key Abstractions

**Normalized Price Frame:**
- Purpose: Provide one internal data shape regardless of the external source schema.
- Examples: `load_data(...)` in `main.py`, `load_data(...)` in `predict_prophet.py`
- Pattern: Rename the timestamp column/index to `index`, normalize it to UTC, rename the usable price column to `adj_close`, and pass only that compact frame downstream.

**Reference Versus Current Window Pair:**
- Purpose: Compare a historical benchmark period with the active monitoring period on aligned trading days.
- Examples: `df_original`, `df_original_truncated`, and `df_new` in `main.py`; `df_old` and `df_new` in `predict_prophet.py`
- Pattern: Read one shared source frame, then slice it into multiple date-bounded views instead of re-reading the source for each stage.

**Band Transition Alert:**
- Purpose: Suppress noisy notifications by sending mail only when the sigma bucket changes.
- Examples: `previous_band` and `current_band` handling in `main_loop(...)` and `send_test_email_now(...)` within `main.py`
- Pattern: Compute benchmark bands from truncated historical data, classify the latest current-period value, and gate notification delivery on a bucket transition.

**Email Payload Separation:**
- Purpose: Keep domain metrics, HTML rendering, and SMTP transport as separate concerns even without a package structure.
- Examples: `build_email_content(...)` in `email_template.py`, `send_email(...)` in `send_gmail.py`, and the call sites in `main.py`
- Pattern: `main.py` assembles alert metrics, `email_template.py` renders the content, and `send_gmail.py` handles MIME construction plus delivery.

## Entry Points

**Production Monitor:**
- Location: `main.py`
- Triggers: `python main.py ...` or a service wrapper such as the `systemd` example in `README.md`
- Responsibilities: Parse configuration, load recipients, run the continuous monitor, generate charts, update HTML output, and send band-change alerts.

**Experimental Forecast CLI:**
- Location: `predict_prophet.py`
- Triggers: `python predict_prophet.py ...`
- Responsibilities: Fit the alternative Prophet workflow and produce a comparison report under `./plots`.

**SMTP Utility CLI:**
- Location: `send_gmail.py`
- Triggers: `python send_gmail.py --to ... --subject ...`
- Responsibilities: Send plain text, HTML, or inline-image emails independently of the market-analysis pipeline.

**Ad Hoc Verification Script:**
- Location: `send_test_email.py`
- Triggers: Manual execution during template or delivery checks
- Responsibilities: Reuse analysis helpers from `main.py`, generate current charts, compose a sample alert, and send a one-off verification email.

## Error Handling

**Strategy:** Fail fast for missing external dependencies at import time, then favor log-and-continue behavior inside the long-running monitor.

**Patterns:**
- `main.py` and `predict_prophet.py` raise `ImportError` immediately if `lib.read_utils` cannot be imported from the external `asset_prices` repository.
- Data-shape checks in `load_data(...)`, `calculate_cumulative_pct_change(...)`, and `calculate_regression_bands(...)` raise `ValueError` when required columns or date ranges are missing.
- `main_loop(...)` in `main.py` wraps each cycle in `try/except`, logs the failure, and keeps the process alive for the next interval.
- `send_gmail.py` converts SMTP and attachment failures into `(success, message)` tuples instead of propagating exceptions to callers.
- `load_email_recipients()` in `main.py` treats a missing `email_recipients.txt` as a warning and returns an empty recipient list.

## Cross-Cutting Concerns

**Logging:** `main.py` configures root logging to both `main.log` and the console via `logging.basicConfig(...)`; `predict_prophet.py` configures console logging only.
**Validation:** CLI validation is handled by `argparse` in `main.py`, `predict_prophet.py`, and `send_gmail.py`, while runtime validation relies on DataFrame emptiness checks, required-column normalization, and explicit date filtering.
**Authentication:** Market data access depends on `ASSET_PRICES_REPO` and `ASSET_PRICES_DATA_DIR` in `main.py` and `predict_prophet.py`; email delivery authenticates through `~/.gmail_send/.env` in `send_gmail.py`.

---

*Architecture analysis: 2026-04-17*
