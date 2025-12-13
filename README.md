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

To enable email alerts, create the Gmail configuration:

```bash
mkdir -p ~/.gmail_send
cat > ~/.gmail_send/.env << 'EOF'
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
EOF
chmod 600 ~/.gmail_send/.env
```

**Generating a Gmail App Password:**
1. Navigate to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification
3. Create an App Password for "Mail"

### Email Recipients

Create `email_recipients.txt` in the project directory:
```
# One email per line, comments start with #
analyst@yourfirm.com
portfolio@yourfirm.com
```

---

## Usage

### Quick Start

```bash
python main.py --symbol VOO --source alpaca --email_notifications
```

### Full Configuration

```bash
python main.py \
  --symbol VOO \
  --source alpaca \
  --original_start 2016-11-08 \
  --original_end 2020-11-03 \
  --new_start 2024-11-05 \
  --sma_window 100 \
  --email_notifications \
  --check_frequency 15
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--symbol` | `VOO` | Ticker symbol (e.g., VOO, SPY, QQQ) |
| `--source` | `alpaca` | Data provider: `alpaca` or `yfinance` |
| `--original_start` | `2016-11-08` | Reference period start (Trump 1st term) |
| `--original_end` | `2020-11-03` | Reference period end |
| `--new_start` | `2024-11-05` | Current period start (Trump 2nd term) |
| `--new_end` | Today | Current period end |
| `--sma_window` | `100` | Moving average window (days) |
| `--check_frequency` | `15` | Monitoring interval (minutes) |
| `--email_notifications` | `True` | Enable email alerts |
| `--plot_bands` | `True` | Show regression bands on chart |
| `--html_output_path` | `./plots/index.html` | Output file path |

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

The tool reads parquet files from a configurable data directory:

```
/home/shared/algos/asset_prices/data/
├── alpaca/
│   ├── VOO.parquet
│   ├── SPY.parquet
│   └── ...
└── yfinance/
    └── ...
```

Each parquet file should contain at minimum:
- Datetime index or column
- `adj_close` (or `Adj Close` or `close`) price column

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
ExecStart=/usr/bin/python3 main.py --symbol VOO --source alpaca --email_notifications
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
