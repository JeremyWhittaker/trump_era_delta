# Testing Patterns

**Analysis Date:** 2026-04-17

## Test Framework

**Runner:**
- Not detected. No `pytest`, `unittest`, `nose`, `tox`, or dedicated test runner config is present in the repository root.
- Config: Not applicable

**Assertion Library:**
- Not applicable. The current codebase does not contain formal assertion-based test modules.

**Run Commands:**
```bash
python send_test_email.py           # Manual end-to-end smoke test: load data, build charts, compose HTML, send Gmail
python main.py --send_test_email    # One-shot validation through the main CLI path, then exit with status code
python main.py --symbol VOO --source alpaca --email_notifications  # Manual long-running verification of the monitor loop
```

## Test File Organization

**Location:**
- Separate root-level smoke script rather than co-located unit tests.
- The only test-like file detected is `send_test_email.py` in the repository root.

**Naming:**
- Ad hoc executable naming rather than `test_*.py` or `*_test.py` patterns in a `tests/` directory.
- The current project convention for manual verification is descriptive script naming (`send_test_email.py`).

**Structure:**
```text
trump_era_delta/
├── main.py
├── send_gmail.py
├── email_template.py
├── predict_prophet.py
└── send_test_email.py
```

## Test Structure

**Suite Organization:**
The current test workflow is script-driven. `send_test_email.py` imports production functions, runs the real data path, and exits non-zero on failure:

```python
df = load_data(symbol, source)
df_original = calculate_cumulative_pct_change(...)
df_original = calculate_regression_bands(df_original)
html_body, text_body = build_email_content(...)
success, message = send_email(...)

if not success:
    sys.exit(1)
```

Source files: `send_test_email.py`, `main.py`, `send_gmail.py`

**Patterns:**
- Setup pattern: Hard-coded defaults inside `send_test_email.py` define symbol, source, date ranges, SMA window, and check frequency.
- Setup pattern: `main.py --send_test_email` reuses production argument parsing and recipient loading before executing one analysis cycle.
- Teardown pattern: No explicit teardown. Output files are written to `./plots`, and email side effects are real.
- Assertion pattern: Success is validated through guard clauses (`if df.empty`), return-value checks (`success, message = send_email(...)`), and process exit codes (`sys.exit(1)`).

## Mocking

**Framework:** Not used.

**Patterns:**
There are no mocks in the current repository. External systems are exercised directly:

```python
df = load_data(symbol, source)
zoomed_jpeg_path, full_jpeg_path, html_path = plot_comparison(...)
success, message = send_email(...)
```

Source files: `send_test_email.py`, `main.py`

**What to Mock:**
- If formal tests are added, mock the external boundaries that are already isolated behind helper calls:
  - `lib.read_utils.read_symbol_data` in `main.py` and `predict_prophet.py`
  - `smtplib.SMTP` in `send_gmail.py`
  - Filesystem writes to `./plots` in `main.py` and `predict_prophet.py`
  - Clock/time dependencies such as `datetime.now(...)` and `time.sleep(...)` in `main.py`

**What NOT to Mock:**
- Do not mock pure transformation helpers where deterministic inputs can be asserted directly:
  - `calculate_cumulative_pct_change` in `main.py`
  - `calculate_regression_bands` and `get_regression_band` in `main.py`
  - `hex_to_rgba`, `format_band_label`, `get_band_interpretation`, and `build_email_content` in `email_template.py`

## Fixtures and Factories

**Test Data:**
- Not formalized. Current smoke tests construct inputs inline and depend on live/parquet-backed market data plus local Gmail configuration.
- Example pattern from `send_test_email.py`:

```python
symbol = "VOO"
source = "alpaca"
original_start = "2016-11-08"
original_end = "2020-11-03"
new_start = "2024-11-05"
```

**Location:**
- No fixture or factory directory exists.
- Runtime dependencies come from the external `asset_prices` repository via `read_symbol_data(...)` and Gmail credentials loaded by `send_gmail.py`.

## Coverage

**Requirements:** None enforced. No coverage config, thresholds, or CI coverage reporting are present.

**View Coverage:**
```bash
# Not available in the current repository
```

## Test Types

**Unit Tests:**
- Not used. There are no isolated unit-test modules for calculation helpers or email formatting helpers.

**Integration Tests:**
- Manual integration testing is the dominant pattern.
- `send_test_email.py` exercises production imports from `main.py`, `email_template.py`, and `send_gmail.py`.
- `main.py --send_test_email` executes the main CLI path, data loading, plot generation, and email delivery in one pass.

**E2E Tests:**
- Not used as a formal suite.
- The closest current equivalent is the manual full-path smoke run through `send_test_email.py`.

## Common Patterns

**Async Testing:**
```python
# Not applicable
# The repository is synchronous; long-running behavior is implemented with:
time.sleep(check_frequency * 60)
```

Source file: `main.py`

**Error Testing:**
Current validation favors status checks and explicit exits:

```python
if df.empty:
    print("No data available")
    sys.exit(1)

success, message = send_email(...)
if not success:
    sys.exit(1)
```

Source files: `send_test_email.py`, `send_gmail.py`

**Operational prerequisites for any test run:**
- `ASSET_PRICES_REPO` and related environment defaults must point to a readable `asset_prices` checkout, because both `main.py` and `predict_prophet.py` import `lib.read_utils.read_symbol_data`.
- Gmail smoke tests require `~/.gmail_send/.env`, because `send_gmail.py` reads credentials from that file at runtime.
- The process must be able to create `./plots`, because both `main.py` and `predict_prophet.py` write output files there.

---

*Testing analysis: 2026-04-17*
