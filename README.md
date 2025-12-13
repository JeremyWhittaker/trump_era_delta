# Compare Timeframes

A financial analysis tool that compares historical asset performance across different timeframes using statistical analysis, regression bands, and optional Prophet-based forecasting. The tool monitors how current market behavior compares to a historical reference period and sends email alerts when assets cross regression band thresholds.

## Overview

This project provides continuous monitoring of asset prices by:
- Calculating cumulative percentage changes over specified date ranges
- Computing linear regression lines and standard deviation bands (±1σ to ±4σ)
- Comparing current market behavior against historical reference periods
- Generating interactive Plotly visualizations
- Sending email alerts when regression band transitions occur

## Project Structure

```
compare_timeframes/
├── main.py              # Primary analysis and monitoring script
├── send_gmail.py        # Gmail SMTP utility for email notifications
├── predict_prophet.py   # Prophet-based time series forecasting
├── requirements.txt     # Python dependencies
├── main.log             # Application logs
├── README.md            # This file
└── plots/               # Output directory for visualizations
    ├── index.html       # Main interactive plot
    ├── *.html           # Symbol-specific HTML plots
    └── *.jpeg           # High-resolution static exports
```

## Installation

### Prerequisites

- Python 3.8+
- Access to asset price data in parquet format (from `/home/shared/algos/asset_prices/data/`)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Gmail Configuration (for email notifications)

Create the configuration file `~/.gmail_send/.env`:

```bash
mkdir -p ~/.gmail_send
cat > ~/.gmail_send/.env << 'EOF'
GMAIL_ADDRESS=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password
EOF
chmod 600 ~/.gmail_send/.env
```

To generate a Gmail App Password:
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification if not already enabled
3. Go to "App passwords" and generate a new password for "Mail"
4. Use this 16-character password in the configuration

## Usage

### Basic Usage

```bash
python main.py --symbol VOO --source alpaca
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
  --email_recipients me@example.com \
  --check_frequency 15 \
  --html_output_path ./plots/index.html
```

### Command-Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--symbol` | `VOO` | Asset symbol to analyze |
| `--source` | `alpaca` | Data source: `yfinance` or `alpaca` |
| `--original_start` | `2016-11-08` | Reference period start date |
| `--original_end` | `2020-11-03` | Reference period end date |
| `--new_start` | `2024-11-05` | Analysis period start date |
| `--new_end` | Today | Analysis period end date |
| `--sma_window` | `100` | Simple Moving Average window (days) |
| `--plot_bands` | `True` | Plot regression bands |
| `--plot_bollinger_bands` | `False` | Plot Bollinger Bands |
| `--email_notifications` | `True` | Send alerts on band changes |
| `--email_recipients` | - | Email addresses for alerts |
| `--check_frequency` | `15` | Check interval in minutes |
| `--html_output_path` | `./plots/index.html` | Output HTML file path |

## Prophet Forecasting

The `predict_prophet.py` script generates time series forecasts using Facebook's Prophet library.

```bash
python predict_prophet.py \
  --symbol VOO \
  --source alpaca \
  --original_start 2016-11-08 \
  --original_end 2020-11-03 \
  --new_start 2024-11-05 \
  --new_end 2024-12-31
```

## How It Works

### Data Flow

```
Load Data (parquet files)
    ↓
Parse & Normalize Timestamps (UTC)
    ↓
Calculate Cumulative % Change
    ↓
Calculate Regression Bands
    ↓
Compare Current vs Historical Period
    ↓
Detect Band Changes → Send Email Alert
    ↓
Generate Visualizations
    ↓
Sleep & Repeat
```

### Key Algorithms

#### Cumulative Percent Change

```python
daily_pct_change = adj_close.pct_change()
cumulative_pct_change = daily_pct_change.fillna(0).cumsum()
```

#### Linear Regression with Standard Deviation Bands

1. Fit linear model: `y = ax + b` using polynomial fitting
2. Calculate residuals: `residuals = actual_y - predicted_y`
3. Compute standard deviation of residuals
4. Create bands at ±1σ, ±2σ, ±3σ, ±4σ levels

```python
regression_line = coef[0] * x + coef[1]
residuals = actual_y - regression_line
residual_std = np.std(residuals)
upper_band_i = regression_line + (i * residual_std)
lower_band_i = regression_line - (i * residual_std)
```

#### Band Classification

The current price position is classified into bands from -4 to +4:
- **+4**: Above upper 4σ band (extreme outperformance)
- **+3 to +1**: Above regression line
- **0**: At regression line
- **-1 to -3**: Below regression line
- **-4**: Below lower 4σ band (extreme underperformance)

## Output

### Interactive HTML Plots

- Generated in `plots/` directory
- Features: hover tooltips, legend toggles, zoom/pan
- Shows regression bands, reference period, and current data

### Static JPEG Exports

- High-resolution (1600x1000px) images
- Zoomed to focus on new period data
- Suitable for email attachments

### Email Alerts

When band transitions are detected, an email is sent containing:
- Band transition information (e.g., "Band changed from +1 to +2")
- Visual ASCII representation of all bands with current position
- JPEG attachment of the latest plot

## Data Sources

Data is loaded from parquet files in `/home/shared/algos/asset_prices/data/`:

```
asset_prices/data/
├── alpaca/
│   ├── VOO.parquet
│   ├── SPY.parquet
│   └── ...
└── yfinance/
    ├── VOO.parquet
    └── ...
```

### Supported Sources

| Source | Description |
|--------|-------------|
| `alpaca` | Alpaca trading platform (real-time capable) |
| `yfinance` | Yahoo Finance historical data |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pandas | 2.2.3 | Data manipulation |
| numpy | 2.0.2 | Numerical computations |
| plotly | 5.24.1 | Interactive visualizations |
| yfinance | 0.2.49 | Yahoo Finance data |
| alpaca-trade-api | 3.2.0 | Alpaca broker API |
| pyarrow | 18.0.0 | Parquet file support |
| prophet | - | Time series forecasting |

## Logging

Logs are written to `main.log` with format:
```
2024-11-27 17:13:24 - INFO - Running analysis for VOO at 2024-11-27 17:13:24 UTC
2024-11-27 17:13:24 - INFO - Data range for VOO from 2016-01-04 to 2024-11-27
2024-11-27 17:13:24 - INFO - Plot saved to plots/VOO_comparison_alpaca.html
```

## Deployment

The script is designed for continuous operation. To run as a systemd service:

```ini
[Unit]
Description=Compare Timeframes Monitor
After=network.target

[Service]
Type=simple
User=shared
WorkingDirectory=/home/shared/algos/compare_timeframes
ExecStart=/usr/bin/python3 main.py --symbol VOO --source alpaca
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

## Related Projects

- **asset_prices**: Provides the parquet data files used by this project

## License

Internal project - not for public distribution.
