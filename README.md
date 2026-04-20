# Trump Era Delta

**Statistical Analysis of Market Performance Across Presidential Terms**

A quantitative finance tool that compares current S&P 500 performance against historical presidential term benchmarks using regression analysis and standard deviation bands. The system provides real-time monitoring with institutional-grade email alerts when market behavior deviates significantly from historical patterns.

---

## Executive Summary

This tool answers a fundamental question: *How does current market performance compare to a historical reference period?*

By default, it compares:
- **Reference Period**: Trump First Term (November 2016 - November 2020)
- **Current Period**: Trump Second Term (November 2024 - Present)

The analysis calculates cumulative returns and fits a linear regression model to the reference period, then tracks where current returns fall relative to statistical bands (±1σ to ±4σ). When the market crosses these thresholds, professional HTML email alerts are dispatched.

---

## Methodology

### Statistical Framework

1. **Cumulative Return Calculation**
   ```
   Daily Return(t) = (Price(t) - Price(t-1)) / Price(t-1)
   Cumulative Return(t) = Σ Daily Return(0 to t)
   ```

2. **Linear Regression Model**
   - Fit: `y = βx + α` where y = cumulative return, x = trading day
   - Residuals: `ε = y_actual - y_predicted`
   - Standard Deviation: `σ = std(ε)`

3. **Regression Bands**
   - Upper bands: `regression_line + (n × σ)` for n = 1, 2, 3, 4
   - Lower bands: `regression_line - (n × σ)` for n = 1, 2, 3, 4

### Band Classification

| Band | Interpretation |
|------|----------------|
| +4σ | Extreme outperformance (>99.99% historical) |
| +3σ | Strong outperformance (>99.7% historical) |
| +2σ | Notable outperformance (>95% historical) |
| +1σ | Slight outperformance (>68% historical) |
| 0 | At historical average |
| -1σ | Slight underperformance |
| -2σ | Notable underperformance |
| -3σ | Strong underperformance |
| -4σ | Extreme underperformance |

---

## Features

- **Real-Time Monitoring**: Configurable check intervals (default: 15 minutes)
- **Regression Band Analysis**: ±1σ to ±4σ deviation tracking
- **Professional Email Alerts**: Institutional-grade HTML emails with embedded charts
- **Interactive Visualizations**: Plotly-based charts with hover tooltips
- **Multiple Data Sources**: Support for Alpaca and Yahoo Finance
- **Continuous Operation**: Designed for 24/7 deployment

---

## Project Structure

```
trump_era_delta/
├── main.py              # Core analysis engine and monitoring loop
├── email_template.py    # Professional HTML email builder
├── send_gmail.py        # SMTP email utility with inline image support
├── predict_prophet.py   # Prophet-based forecasting (experimental)
├── requirements.txt     # Python dependencies
├── .gitignore          # Git exclusions
└── plots/              # Generated visualizations (gitignored)
```

---

## Installation

### Prerequisites

- Python 3.8+
- Access to market data in parquet format

### Setup

```bash
git clone https://github.com/JeremyWhittaker/trump_era_delta.git
cd trump_era_delta
pip install -r requirements.txt
```

### Email Configuration

The preferred secret path is the gitignored project-local `.env.local` file:

```bash
cat > .env.local << 'EOF'
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
EOF
chmod 600 .env.local
```

The old `~/.gmail_send/.env` path still works as a temporary fallback during migration, but new setup should use `.env.local`.

**Generating a Gmail App Password:**
1. Navigate to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification
3. Create an App Password for "Mail"

### Alert Recipients

Keep machine-specific recipients in `config/service.local.json`:

```json
{
  "alerts": {
    "enabled": true,
    "recipients": [
      "analyst@yourfirm.com",
      "portfolio@yourfirm.com"
    ]
  }
}
```

You can also override local paths or other runtime values in the same file without editing Python code.

---

## Usage

### Operator Workflow

1. Inspect the merged config:

```bash
python3 main.py show-config --json
```

2. Run strict no-send validation before enabling the service:

```bash
python3 main.py check
```

3. Generate the supported no-email report and chart artifacts through the shared analysis core:

```bash
python3 main.py report
```

4. Send a one-shot test email through the same validated analysis and report pipeline:

```bash
python3 main.py test-email
```

The legacy helper now forwards to the same command:

```bash
python3 send_test_email.py
```

5. Run one live-monitor cycle without sleeping so you can verify transition handling against the persisted alert state:

```bash
python3 main.py run --once
```

6. Start the long-running monitor only after `check` succeeds:

```bash
python3 main.py run
```

`run`, `run --once`, `report`, and `test-email` now share the same validated analysis core and chart/report generation path. `report` never invokes SMTP; `test-email` proves the real email path; `run --once` executes one live alert-evaluation cycle without entering the long-running loop.

### Config Files

| File | Purpose |
|------|---------|
| `config/service.json` | Committed defaults for asset paths, monitor settings, alerts, and runtime outputs |
| `config/service.local.json` | Gitignored machine-local overrides, including recipients |
| `.env.local` | Gitignored Gmail credentials |

---

## Email Alerts

When the market crosses a regression band threshold, the system sends a professional HTML email containing:

- **Executive Summary**: Current position and band transition
- **Methodology Explanation**: Clear description of what's being measured
- **Statistical Metrics**: Current cumulative return, regression line, and all band values
- **Embedded Chart**: High-resolution visualization inline (not as attachment)
- **Interpretation Guide**: Context for understanding the signal

The email design follows institutional standards with a navy/charcoal/gold color palette.

---

## Data Sources

Prices come from the sibling `asset_prices` project via its `lib.read_utils.read_symbol_data` helper, which supports both the new partitioned layout and any legacy single-file remnants.

Default paths (override via env vars):
- `ASSET_PRICES_REPO`: `/home/shared/algos/asset_prices`
- `ASSET_PRICES_DATA_DIR`: `/home/shared/algos/asset_prices/data`
- `ASSET_PRICES_DATA_TYPE`: `adjusted` (set to `raw` for unadjusted OHLCV)

Current parquet layout:
```
/home/shared/algos/asset_prices/data/
├── alpaca/
│   └── symbol=VOO/year=2024/month=11/data.parquet
├── yfinance/
│   └── symbol=VOO/year=2024/month=11/data.parquet
└── ... (also supports alpaca_raw/yfinance_raw)
```

Files follow the canonical schema (`timestamp`, `open`, `high`, `low`, `close`, `adj_close`, `volume`), use UTC timestamps, and are sorted chronologically. The reader prunes partitions automatically when you pass `start_date` and `end_date`.

---

## Deployment

### Systemd Service

For production deployment:

```ini
[Unit]
Description=Trump Era Delta Market Monitor
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/trump_era_delta
ExecStart=/usr/bin/python3 /path/to/trump_era_delta/main.py run
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| pandas | Data manipulation and time series |
| numpy | Numerical computations |
| plotly | Interactive visualizations |
| alpaca-trade-api | Real-time market data |
| yfinance | Historical market data |
| pyarrow | Parquet file support |

---

## License

MIT License

---

## Author

Jeremy Whittaker

---

*This tool is for informational and educational purposes only. It does not constitute financial advice. Past performance does not guarantee future results.*
