# Technology Stack

**Analysis Date:** 2026-04-17

## Languages

**Primary:**
- Python 3.x - all application code lives in `main.py`, `send_gmail.py`, `email_template.py`, `predict_prophet.py`, and `send_test_email.py`

**Secondary:**
- HTML/CSS - generated email markup is assembled in `email_template.py` and Plotly HTML is emitted from `main.py`
- Plain text config/data - dependency pins live in `requirements.txt` and recipient configuration lives in `email_recipients.txt`

## Runtime

**Environment:**
- CPython 3.8+ is the documented minimum in `README.md`
- CPython 3.12.3 is the interpreter available in the current workspace

**Package Manager:**
- `pip` 24.0 via `pip install -r requirements.txt` from `README.md`
- Lockfile: missing

## Frameworks

**Core:**
- `pandas==2.2.3` - time-series loading, date filtering, and return calculations in `main.py` and `predict_prophet.py`
- `numpy==2.0.2` - linear regression and residual standard deviation calculations in `main.py`
- `plotly==5.24.1` - interactive chart generation and HTML export in `main.py` and `predict_prophet.py`

**Testing:**
- Not detected - there is no test framework, test config, or test suite in the repository root

**Build/Dev:**
- `kaleido==0.2.1` - static JPEG export backend for `fig.write_image(...)` in `main.py`
- Python stdlib `argparse` - CLI entrypoints for `main.py`, `predict_prophet.py`, and `send_gmail.py`
- Python stdlib `logging` - file and console logging, with `main.py` writing `main.log`

## Key Dependencies

**Critical:**
- `pandas==2.2.3` - core dataframe and time-series processing in `main.py` and `predict_prophet.py`
- `numpy==2.0.2` - regression fitting and sigma-band calculations in `main.py`
- `plotly==5.24.1` - chart rendering, HTML output, and interactive visualization in `main.py` and `predict_prophet.py`
- `kaleido==0.2.1` - required by `main.py` for JPEG alert images
- `pyarrow==18.0.0` - parquet interoperability expected by the external reader imported into `main.py` and `predict_prophet.py`

**Infrastructure:**
- `alpaca-trade-api==3.2.0` - upstream market-data ecosystem dependency referenced by provider choice in `main.py`, though direct client calls are delegated to the external `asset_prices` project
- `yfinance==0.2.49` - alternate market-data ecosystem dependency referenced by provider choice in `main.py`, also delegated through the external `asset_prices` reader
- `aiohttp==3.11.0`, `websocket-client==1.8.0`, and `websockets==10.4` - transport-layer dependencies pinned in `requirements.txt`, likely supporting upstream data-provider packages rather than direct imports in this repo
- `python-dotenv==1.0.1` - present in `requirements.txt`, but configuration loading in `send_gmail.py` is implemented manually instead of via this package
- `prophet` - imported in `predict_prophet.py` for experimental forecasting, but no version is declared in `requirements.txt`

## Configuration

**Environment:**
- `main.py` and `predict_prophet.py` read `ASSET_PRICES_REPO`, `ASSET_PRICES_DATA_DIR`, and `ASSET_PRICES_DATA_TYPE` to locate the sibling `asset_prices` project and its parquet dataset
- `send_gmail.py` reads Gmail credentials from `~/.gmail_send/.env` outside the repository; the repo does not contain a checked-in `.env` file
- `main.py` reads recipient addresses from `email_recipients.txt` when `--email_recipients` is not passed on the CLI

**Build:**
- Dependency manifest: `requirements.txt`
- No `pyproject.toml`, `setup.py`, `tox.ini`, Dockerfile, or CI config was detected in the repository root
- Output artifacts are written at runtime to `./plots/` and `main.log` from `main.py`

## Platform Requirements

**Development:**
- Python 3.8+ with `pip` and the packages from `requirements.txt`
- Local filesystem access to a sibling `asset_prices` checkout at the path expected by `main.py` and `predict_prophet.py`
- Writable local paths for `./plots/`, `main.log`, and optional `--html_output_path` targets from `main.py`

**Production:**
- A long-running Python process on a Linux-style host is the operational model shown in `README.md`
- `README.md` includes a `systemd` service example, but no deployment manifests are committed in this repository

---

*Stack analysis: 2026-04-17*
