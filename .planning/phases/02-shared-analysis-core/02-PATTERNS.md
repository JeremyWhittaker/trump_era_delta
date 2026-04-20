# Phase 2: Shared Analysis Core - Pattern Map

**Mapped:** 2026-04-19
**Files analyzed:** 7
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `analysis_core.py` | utility | data-processing | `main.py`, `predict_prophet.py` | role-match |
| `report_pipeline.py` | utility | data-processing | `main.py` | role-match |
| `main.py` | controller | request-response | `main.py` | exact |
| `predict_prophet.py` | experimental service | data-processing | `predict_prophet.py` | exact |
| `README.md` | documentation | operator-guidance | `README.md` | exact |
| `tests/test_analysis_core.py` | test | verification | `tests/test_service_config.py` | role-match |
| `tests/test_report_pipeline.py` / `tests/test_main_cli.py` | test | verification | `tests/test_main_cli.py` | exact |

## Pattern Assignments

### `analysis_core.py` (utility, data-processing)

**Analogs:** `main.py`, `predict_prophet.py`

**Current shared-candidate logic in `main.py`:**
```python
def load_data(...):
    df = read_symbol_data_fn(...)
    ...
    if 'timestamp' in df.columns:
        df.rename(columns={'timestamp': 'index'}, inplace=True)
    ...
    if "adj_close" not in df.columns:
        ...
    return df

def calculate_cumulative_pct_change(df, start_date, end_date, sma_window=None, plot_bollinger_bands=False):
    ...

def calculate_regression_bands(df, max_stddev=4):
    ...

def get_regression_band(current_pct, df_truncated):
    ...

def _prepare_analysis_frames(...):
    ...
```

**Duplicate data prep in `predict_prophet.py`:**
```python
def load_data(...):
    df = read_symbol_data(...)
    ...

def calculate_daily_pct_change(df, start_date, end_date):
    ...

def prepare_aligned_data(df, start_date, end_date):
    ...
```

**Phase 2 pattern:** move shared price-frame normalization, date slicing/alignment, cumulative-return preparation, regression-band math, and the existing `_prepare_analysis_frames(...)` logic into a root-level helper module. Keep Prophet-only forecasting transforms local unless they are truly generic.

Use small top-level functions, guard clauses, and actionable `ValueError`/runtime messages, matching the current style instead of introducing classes or dataclasses.

---

### `report_pipeline.py` (utility, data-processing)

**Analog:** `main.py`

**Current report/chart assembly in `main.py`:**
```python
def plot_comparison(symbol, df_original, df_original_truncated, df_new, output_dir, sma_window, source, ...):
    ...
    return zoomed_file_jpeg, full_file_jpeg, html_file

latest_cumulative_pct_change = df_new['cumulative_pct_change'].iloc[-1]
current_band = get_regression_band(latest_cumulative_pct_change, df_original_truncated)
reg_line = df_original_truncated['regression_line'].iloc[-1]
bands = {
    '+4σ': ...,
    ...
}
```

**Email/report payload assembly in `main.py`:**
```python
html_body, text_body = build_email_content(
    symbol=symbol,
    source=source,
    timestamp_utc=timestamp_utc,
    latest_price=latest_price,
    previous_band=current_band,
    current_band=current_band,
    current_pct=current_pct,
    regression_line=reg_line,
    bands=bands,
    ...
)
```

**Phase 2 pattern:** extract chart generation and statistical snapshot assembly behind one shared contract that returns concrete artifact paths plus the values needed by report/email callers. Preserve the current chart semantics and band meanings exactly. Do not move forecast-only Prophet charts into this shared report module.

---

### `main.py` (controller, request-response)

**Analog:** `main.py`

**Current CLI/runtime shape:**
```python
def main(argv=None):
    ...
    if args.command == "run":
        return 0 if main_loop(**runtime_settings) is not False else 1
    success = send_test_email_now(...)
    return 0 if success else 1
```

**Phase 2 controller pattern:**
- Keep `main.py` as the single supported operator entrypoint.
- Import shared helpers from the new modules instead of keeping duplicate data and report logic inline.
- Add the new supported no-email one-shot report subcommand here, not in a side script.
- Preserve strict preflight and import-safe behavior from Phase 1.

---

### `predict_prophet.py` (experimental service, data-processing)

**Analog:** `predict_prophet.py`

**Current experimental boundaries:**
```python
from prophet import Prophet

def predict_for_new_period(...):
    model = Prophet()
    model.fit(df_old_prophet)
    ...

def plot_comparison(symbol, df_old, df_new, forecast, output_dir):
    ...
```

**Phase 2 pattern:** reuse the shared loading/alignment helpers where they fit, but keep Prophet model fitting and forecast-only visualization local to this file. This script remains experimental and should not drag the supported service/report path into forecast-specific abstractions.

---

### Tests (`tests/test_analysis_core.py`, `tests/test_report_pipeline.py`, `tests/test_main_cli.py`)

**Analogs:** `tests/test_service_config.py`, `tests/test_main_cli.py`

**Current test style:**
```python
import tempfile
import unittest
from unittest import mock

class ServiceConfigTests(unittest.TestCase):
    ...
```

**Phase 2 test pattern:**
- Use stdlib `unittest`, `tempfile`, and `unittest.mock`.
- Prefer small deterministic DataFrame fixtures over integration with the real `asset_prices` checkout.
- Verify callable contracts and concrete output keys/paths/CLI help text rather than subjective behavior.

---

## Planning Guidance

- Keep new shared code in root-level `snake_case.py` modules to match the existing repo structure.
- Treat `main.py` and the new `report` command as the supported runtime path; helper scripts should stay thin.
- Preserve current statistical semantics and alert-facing outputs while reducing duplication.
- Use explicit operator-facing failures for supported commands; reserve best-effort behavior for experimental Prophet work only.
