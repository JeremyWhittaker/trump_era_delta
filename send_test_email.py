#!/usr/bin/env python3
"""
Send a test email with the latest template using current data.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

# Import from the main project
from main import load_data, calculate_cumulative_pct_change, calculate_regression_bands, get_regression_band
from email_template import build_email_content
from send_gmail import send_email


def main():
    # Configuration
    symbol = "VOO"
    source = "alpaca"
    original_start = "2016-11-08"
    original_end = "2020-11-03"
    new_start = "2024-11-05"
    sma_window = 100
    check_frequency = 15

    # Load and process data
    print(f"Loading data for {symbol}...")
    df = load_data(symbol, source)

    if df.empty:
        print("No data available")
        sys.exit(1)

    latest_data_date = df['index'].max()
    today = datetime.now(timezone.utc)
    adjusted_new_end = min(latest_data_date, today)

    # Calculate cumulative percent change
    print("Calculating cumulative percent change...")
    df_original = calculate_cumulative_pct_change(df, original_start, original_end, sma_window=sma_window, plot_bollinger_bands=False)
    df_new = calculate_cumulative_pct_change(df, new_start, adjusted_new_end)

    df_original['day_index'] = range(len(df_original))
    df_new['day_index'] = range(len(df_new))

    # Calculate regression bands
    df_original = calculate_regression_bands(df_original)

    num_days_new = len(df_new)
    df_original_truncated = df_original.iloc[:num_days_new].copy()
    df_original_truncated.reset_index(drop=True, inplace=True)
    df_original_truncated['day_index'] = range(len(df_original_truncated))
    df_original_truncated = calculate_regression_bands(df_original_truncated)

    # Get current values
    latest_cumulative_pct_change = df_new['cumulative_pct_change'].iloc[-1]
    current_band = get_regression_band(latest_cumulative_pct_change, df_original_truncated)

    # For test email, simulate a band change
    previous_band = current_band - 1  # Simulate upgrade

    current_pct = latest_cumulative_pct_change
    reg_line = df_original_truncated['regression_line'].iloc[-1]

    # Build bands dictionary
    bands = {
        '+4σ': df_original_truncated['regression_upper_band_4'].iloc[-1],
        '+3σ': df_original_truncated['regression_upper_band_3'].iloc[-1],
        '+2σ': df_original_truncated['regression_upper_band_2'].iloc[-1],
        '+1σ': df_original_truncated['regression_upper_band_1'].iloc[-1],
        'avg': reg_line,
        '-1σ': df_original_truncated['regression_lower_band_1'].iloc[-1],
        '-2σ': df_original_truncated['regression_lower_band_2'].iloc[-1],
        '-3σ': df_original_truncated['regression_lower_band_3'].iloc[-1],
        '-4σ': df_original_truncated['regression_lower_band_4'].iloc[-1]
    }

    latest_price = df_new.iloc[-1]['adj_close']
    latest_date = df_new.iloc[-1]['index']
    timestamp_utc = latest_date.strftime('%Y-%m-%d %H:%M:%S UTC')

    days_original = len(df_original)
    days_new = len(df_new)

    # Period formatting
    orig_start_dt = datetime.strptime(original_start, '%Y-%m-%d')
    orig_end_dt = datetime.strptime(original_end, '%Y-%m-%d')
    new_start_dt = datetime.strptime(new_start, '%Y-%m-%d')

    print(f"Building email content...")
    print(f"  Symbol: {symbol}")
    print(f"  Latest Price: ${latest_price:.2f}")
    print(f"  Current Band: {current_band}σ")
    print(f"  Cumulative Return: {current_pct*100:.2f}%")
    print(f"  Days in new period: {days_new}")

    # Build email content
    html_body, text_body = build_email_content(
        symbol=symbol,
        source=source,
        timestamp_utc=timestamp_utc,
        latest_price=latest_price,
        previous_band=previous_band,
        current_band=current_band,
        current_pct=current_pct,
        regression_line=reg_line,
        bands=bands,
        days_original=days_original,
        days_new=days_new,
        sma_window=sma_window,
        check_frequency=check_frequency,
        reference_period_name="Trump First Term",
        reference_start=orig_start_dt.strftime('%b %Y'),
        reference_end=orig_end_dt.strftime('%b %Y'),
        current_period_name="Trump Second Term",
        current_start=new_start_dt.strftime('%b %Y'),
        html_link=None
    )

    # Generate chart
    print("Generating chart...")
    from main import plot_comparison
    output_dir = Path('./plots')
    output_dir.mkdir(parents=True, exist_ok=True)
    jpeg_path, html_path = plot_comparison(symbol, df_original, df_original_truncated, df_new, output_dir, sma_window, source, True, False,
                                          original_start, original_end, new_start)

    if jpeg_path and jpeg_path.exists():
        with open(jpeg_path, 'rb') as f:
            chart_bytes = f.read()

        inline_images = [{
            'cid': 'chart',
            'content': chart_bytes,
            'subtype': 'jpeg'
        }]
    else:
        print("Warning: Could not generate chart")
        inline_images = None

    # Send email
    recipient = "me@jeremywhittaker.com"
    subject = f"📈 [TEST] Regression Band Alert: {symbol} → {'+' if current_band > 0 else ''}{current_band}σ"

    print(f"Sending test email to {recipient}...")
    success, message = send_email(
        to_addrs=[recipient],
        subject=subject,
        body=None,
        html_body=html_body,
        text_body=text_body,
        inline_images=inline_images
    )

    if success:
        print(f"✓ Email sent successfully!")
    else:
        print(f"✗ Failed to send email: {message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
