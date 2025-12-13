import os
import argparse
import logging
import pandas as pd
from pathlib import Path
import plotly.graph_objects as go
import numpy as np
import time
from datetime import datetime, timedelta, timezone
from shutil import copyfile
from send_gmail import send_email
from email_template import build_email_content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("main.log"),
        logging.StreamHandler()
    ]
)

# Path to email recipients file
EMAIL_RECIPIENTS_FILE = Path(__file__).parent / 'email_recipients.txt'


def load_email_recipients():
    """Load email recipients from email_recipients.txt file."""
    if not EMAIL_RECIPIENTS_FILE.exists():
        logging.warning(f"Email recipients file not found: {EMAIL_RECIPIENTS_FILE}")
        return []

    recipients = []
    with open(EMAIL_RECIPIENTS_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                recipients.append(line)

    logging.info(f"Loaded {len(recipients)} email recipients from {EMAIL_RECIPIENTS_FILE}")
    return recipients

def load_data(symbol, source):
    """Loads data from the specified data source (yfinance or alpaca) for a given symbol, retaining only the 'adj_close' column."""
    data_dir = Path('/home/shared/algos/asset_prices/data') / source
    file_path = data_dir / f"{symbol}.parquet"

    if not file_path.exists():
        raise FileNotFoundError(f"Data file for {symbol} not found in {source} directory.")

    df = pd.read_parquet(file_path)

    # Log columns and index name for debugging
    logging.debug(f"DataFrame columns: {df.columns.tolist()}")
    logging.debug(f"DataFrame index name: {df.index.name}")
    logging.debug(f"DataFrame index dtype: {df.index.dtype}")

    # Handle cases where the index is datetime but may not have a name
    if pd.api.types.is_datetime64_any_dtype(df.index):
        logging.info("DataFrame index is datetime")
        if df.index.name is None:
            # Index is datetime and unnamed, set index name to 'index'
            df.index.name = 'index'
        else:
            # Index is datetime and has a name, rename it to 'index'
            df.index.name = 'index'
        df.reset_index(inplace=True)
    elif 'timestamp' in df.columns and pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        logging.info("DataFrame has 'timestamp' column")
        df.rename(columns={'timestamp': 'index'}, inplace=True)
    else:
        # Check for any datetime column
        datetime_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col])]
        if datetime_cols:
            # If there is exactly one datetime column, use it
            if len(datetime_cols) == 1:
                df.rename(columns={datetime_cols[0]: 'index'}, inplace=True)
            else:
                raise ValueError("Multiple datetime columns found. Unable to determine which one to use as 'index'.")
        else:
            raise ValueError("Dataset must have a datetime 'timestamp' column or index.")

    # Now, 'index' column should exist
    if 'index' not in df.columns:
        raise ValueError("Failed to create 'index' column from datetime index or column.")

    # Proceed with the rest of the function
    # Handle column renaming for 'adj_close'
    if "adj_close" not in df.columns:
        if "Adj Close" in df.columns:
            df.rename(columns={"Adj Close": "adj_close"}, inplace=True)
        elif "close" in df.columns:
            df.rename(columns={"close": "adj_close"}, inplace=True)
        else:
            raise ValueError("Missing `adj_close` column in data.")

    # Retain only the 'index' and 'adj_close' columns
    columns_to_keep = ['index', 'adj_close']
    df = df[columns_to_keep]

    # Drop rows where 'adj_close' is NaN
    initial_row_count = len(df)
    df = df.dropna(subset=['adj_close'])
    final_row_count = len(df)
    dropped_rows = initial_row_count - final_row_count
    if dropped_rows > 0:
        logging.info(f"Dropped {dropped_rows} rows due to NaN values in 'adj_close'.")

    # Ensure 'index' is in datetime format with timezone awareness
    if not pd.api.types.is_datetime64_any_dtype(df['index']):
        df['index'] = pd.to_datetime(df['index'], errors='coerce')
        if df['index'].isna().any():
            raise ValueError("Some 'index' values could not be converted to datetime.")

    # Check if 'index' is timezone-aware; if not, localize to UTC
    if df['index'].dt.tz is None:
        df['index'] = df['index'].dt.tz_localize('UTC')
        logging.info(f"'index' column localized to UTC timezone.")
    else:
        logging.info(f"'index' column is already timezone-aware with timezone: {df['index'].dt.tz}")

    # Log the data range
    if not df.empty:
        min_date = df['index'].min()
        max_date = df['index'].max()
        logging.info(f"Data range for {symbol} from {min_date} to {max_date}")
    else:
        logging.warning(f"No data available for {symbol} after cleaning.")

    return df

def calculate_cumulative_pct_change(df, start_date, end_date, sma_window=None, plot_bollinger_bands=False):
    """
    Calculates the cumulative percent change for a given date range
    and applies SMA and Bollinger Bands if specified.
    """
    # Convert start_date and end_date to datetime with the same timezone as 'index'
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    if start_date.tz is None:
        start_date = start_date.tz_localize(df['index'].dt.tz)
    if end_date.tz is None:
        end_date = end_date.tz_localize(df['index'].dt.tz)

    df_filtered = df.loc[df['index'].between(start_date, end_date)].copy()

    if df_filtered.empty:
        raise ValueError(f"No data available for the specified date range: {start_date} to {end_date}")

    # Calculate cumulative percent change
    df_filtered['cumulative_pct_change'] = df_filtered['adj_close'].pct_change().fillna(0).cumsum()

    # Calculate SMA and Bollinger Bands if specified
    if sma_window and plot_bollinger_bands:
        # SMA of the cumulative percent change
        df_filtered['sma'] = df_filtered['cumulative_pct_change'].rolling(window=sma_window).mean()

        # Standard deviation of the cumulative percent change over the same window
        df_filtered['stddev'] = df_filtered['cumulative_pct_change'].rolling(window=sma_window).std()

        # Bollinger Bands: Upper and Lower
        df_filtered['upper_band'] = df_filtered['sma'] + (2 * df_filtered['stddev'])
        df_filtered['lower_band'] = df_filtered['sma'] - (2 * df_filtered['stddev'])

    df_filtered.reset_index(drop=True, inplace=True)  # Reset index for hover data
    return df_filtered

def calculate_regression_bands(df, max_stddev=4):
    """
    Calculates linear regression line and ±stddev bands on cumulative percent change.
    """
    if df.empty:
        raise ValueError("DataFrame is empty. Cannot perform regression.")

    # Ensure that 'cumulative_pct_change' column exists
    if 'cumulative_pct_change' not in df.columns:
        raise ValueError("DataFrame must contain 'cumulative_pct_change' column for regression analysis.")

    x = df['day_index'].values
    y = df['cumulative_pct_change'].values

    # Fit a linear regression model
    coef = np.polyfit(x, y, 1)
    df['regression_line'] = coef[0] * x + coef[1]

    # Calculate residuals and standard deviation
    residuals = y - df['regression_line']
    residual_std = np.std(residuals)

    # Store residual_std in df
    df['residual_std'] = residual_std

    # Calculate bands for each stddev level
    for i in range(1, max_stddev + 1):
        df[f'regression_upper_band_{i}'] = df['regression_line'] + (i * residual_std)
        df[f'regression_lower_band_{i}'] = df['regression_line'] - (i * residual_std)

    return df

def plot_comparison(symbol, df_original, df_original_truncated, df_new, output_dir, sma_window, source, plot_bands=False, plot_bollinger_bands=False,
                    original_start="2016-11-08", original_end="2020-11-03", new_start="2024-11-05"):
    """
    Plots cumulative percent change with regression bands, featuring:
    - Clear color coding and legend grouping
    - Dual x-axis showing aligned days AND actual dates
    - Unified hover with detailed tooltips
    - End-of-line annotations
    - Professional HTML wrapper with methodology explanation
    """
    if df_new.empty:
        logging.warning(f"No new period data available for plotting for {symbol}. Skipping plot.")
        return None, None

    # ========== PREPARE DATA ==========
    # Prepare hover data with customdata arrays
    df_original['hover_date'] = df_original['index'].dt.strftime('%Y-%m-%d')
    df_original['hover_price'] = df_original['adj_close']
    df_original_truncated['hover_date'] = df_original_truncated['index'].dt.strftime('%Y-%m-%d')
    df_original_truncated['hover_price'] = df_original_truncated['adj_close']
    df_new['hover_date'] = df_new['index'].dt.strftime('%Y-%m-%d')
    df_new['hover_price'] = df_new['adj_close']

    # Get the latest values
    latest_price = df_new.iloc[-1]['adj_close']
    latest_date = df_new.iloc[-1]['index']
    latest_datetime = latest_date.strftime('%Y-%m-%d %H:%M:%S %Z')
    latest_date_short = latest_date.strftime('%Y-%m-%d')
    latest_cum_pct = df_new.iloc[-1]['cumulative_pct_change']

    # Get current regression band
    current_band = None
    if 'regression_line' in df_original_truncated.columns:
        reg_line_val = df_original_truncated['regression_line'].iloc[-1]
        current_band = get_regression_band(latest_cum_pct, df_original_truncated)

    # ========== COLOR PALETTE (Hedge Fund Style) ==========
    COLORS = {
        'original_period': '#1e3a5f',      # Navy blue
        'new_period': '#c0392b',           # Rich red
        'regression_full': '#2c3e50',      # Dark charcoal
        'regression_truncated': '#27ae60', # Emerald green
        'band_amber': 'rgba(212, 175, 55, {alpha})',  # Gold/amber
        'band_green': 'rgba(39, 174, 96, {alpha})',   # Green
        'bollinger': 'rgba(52, 152, 219, 0.2)',       # Light blue
        'latest_marker': '#f1c40f',        # Bright gold
        'grid': '#ecf0f1',
        'text': '#2c3e50',
    }

    # ========== CREATE FIGURE ==========
    fig = go.Figure()

    # ========== REGRESSION BANDS (Full Original - Background) ==========
    if plot_bands and 'regression_upper_band_1' in df_original.columns:
        max_stddev = 4
        band_alphas = [0.12, 0.09, 0.06, 0.03]  # Decreasing opacity for outer bands

        # Upper bands (plot from outermost to innermost)
        for i in range(max_stddev, 0, -1):
            upper = df_original[f'regression_upper_band_{i}']
            lower = df_original[f'regression_upper_band_{i-1}'] if i > 1 else df_original['regression_line']

            fig.add_trace(go.Scatter(
                x=df_original['day_index'], y=upper,
                mode='lines', line=dict(width=0),
                showlegend=False, hoverinfo='skip',
                legendgroup='bands_original'
            ))
            fig.add_trace(go.Scatter(
                x=df_original['day_index'], y=lower,
                mode='lines', line=dict(width=0),
                fill='tonexty',
                fillcolor=COLORS['band_amber'].format(alpha=band_alphas[i-1]),
                name='Historical σ Bands (Full Period)' if i == max_stddev else None,
                showlegend=(i == max_stddev),
                hoverinfo='skip',
                legendgroup='bands_original'
            ))

        # Lower bands
        for i in range(max_stddev, 0, -1):
            lower = df_original[f'regression_lower_band_{i}']
            upper = df_original[f'regression_lower_band_{i-1}'] if i > 1 else df_original['regression_line']

            fig.add_trace(go.Scatter(
                x=df_original['day_index'], y=lower,
                mode='lines', line=dict(width=0),
                showlegend=False, hoverinfo='skip',
                legendgroup='bands_original'
            ))
            fig.add_trace(go.Scatter(
                x=df_original['day_index'], y=upper,
                mode='lines', line=dict(width=0),
                fill='tonexty',
                fillcolor=COLORS['band_amber'].format(alpha=band_alphas[i-1]),
                showlegend=False, hoverinfo='skip',
                legendgroup='bands_original'
            ))

    # ========== REGRESSION BANDS (Truncated - Active Comparison) ==========
    if plot_bands and 'regression_upper_band_1' in df_original_truncated.columns:
        max_stddev = 4
        band_alphas = [0.18, 0.14, 0.10, 0.06]

        # Upper bands
        for i in range(max_stddev, 0, -1):
            upper = df_original_truncated[f'regression_upper_band_{i}']
            lower = df_original_truncated[f'regression_upper_band_{i-1}'] if i > 1 else df_original_truncated['regression_line']

            fig.add_trace(go.Scatter(
                x=df_original_truncated['day_index'], y=upper,
                mode='lines', line=dict(width=0),
                showlegend=False, hoverinfo='skip',
                legendgroup='bands_truncated'
            ))
            fig.add_trace(go.Scatter(
                x=df_original_truncated['day_index'], y=lower,
                mode='lines', line=dict(width=0),
                fill='tonexty',
                fillcolor=COLORS['band_green'].format(alpha=band_alphas[i-1]),
                name='Active σ Bands (Matched Days)' if i == max_stddev else None,
                showlegend=(i == max_stddev),
                hoverinfo='skip',
                legendgroup='bands_truncated'
            ))

        # Lower bands
        for i in range(max_stddev, 0, -1):
            lower = df_original_truncated[f'regression_lower_band_{i}']
            upper = df_original_truncated[f'regression_lower_band_{i-1}'] if i > 1 else df_original_truncated['regression_line']

            fig.add_trace(go.Scatter(
                x=df_original_truncated['day_index'], y=lower,
                mode='lines', line=dict(width=0),
                showlegend=False, hoverinfo='skip',
                legendgroup='bands_truncated'
            ))
            fig.add_trace(go.Scatter(
                x=df_original_truncated['day_index'], y=upper,
                mode='lines', line=dict(width=0),
                fill='tonexty',
                fillcolor=COLORS['band_green'].format(alpha=band_alphas[i-1]),
                showlegend=False, hoverinfo='skip',
                legendgroup='bands_truncated'
            ))

    # ========== BOLLINGER BANDS ==========
    if plot_bollinger_bands and 'upper_band' in df_original.columns:
        fig.add_trace(go.Scatter(
            x=df_original['day_index'], y=df_original['upper_band'],
            mode='lines', line=dict(width=0),
            showlegend=False, hoverinfo='skip',
            legendgroup='bollinger'
        ))
        fig.add_trace(go.Scatter(
            x=df_original['day_index'], y=df_original['lower_band'],
            mode='lines', line=dict(width=0),
            fill='tonexty', fillcolor=COLORS['bollinger'],
            name=f'Bollinger Bands ({sma_window}d SMA)',
            legendgroup='bollinger',
            hoverinfo='skip'
        ))

    # ========== ORIGINAL PERIOD LINE ==========
    customdata_original = list(zip(df_original['hover_date'], df_original['hover_price']))
    fig.add_trace(go.Scatter(
        x=df_original['day_index'],
        y=df_original['cumulative_pct_change'],
        mode='lines',
        name=f'Trump Term 1 ({original_start[:4]}–{original_end[:4]})',
        line=dict(color=COLORS['original_period'], width=2.5),
        customdata=customdata_original,
        hovertemplate=(
            '<b>Trump Term 1</b><br>'
            'Aligned Day: %{x}<br>'
            'Date: %{customdata[0]}<br>'
            'Price: $%{customdata[1]:.2f}<br>'
            'Cum. Return: %{y:.2%}'
            '<extra></extra>'
        ),
        legendgroup='original'
    ))

    # ========== REGRESSION LINES ==========
    if 'regression_line' in df_original.columns:
        fig.add_trace(go.Scatter(
            x=df_original['day_index'],
            y=df_original['regression_line'],
            mode='lines',
            name='Regression (Full Period)',
            line=dict(color=COLORS['regression_full'], width=1.5, dash='dot'),
            hovertemplate='Regression (Full): %{y:.2%}<extra></extra>',
            legendgroup='regression_full'
        ))

    if 'regression_line' in df_original_truncated.columns:
        fig.add_trace(go.Scatter(
            x=df_original_truncated['day_index'],
            y=df_original_truncated['regression_line'],
            mode='lines',
            name='Regression (Matched Days)',
            line=dict(color=COLORS['regression_truncated'], width=2, dash='dash'),
            hovertemplate='Regression (Matched): %{y:.2%}<extra></extra>',
            legendgroup='regression_truncated'
        ))

    # ========== NEW PERIOD LINE (Primary Focus) ==========
    customdata_new = list(zip(df_new['hover_date'], df_new['hover_price']))
    fig.add_trace(go.Scatter(
        x=df_new['day_index'],
        y=df_new['cumulative_pct_change'],
        mode='lines',
        name=f'Trump Term 2 ({new_start[:4]}–Present)',
        line=dict(color=COLORS['new_period'], width=3),
        customdata=customdata_new,
        hovertemplate=(
            '<b>Trump Term 2 (Current)</b><br>'
            'Aligned Day: %{x}<br>'
            'Date: %{customdata[0]}<br>'
            'Price: $%{customdata[1]:.2f}<br>'
            'Cum. Return: %{y:.2%}'
            '<extra></extra>'
        ),
        legendgroup='new'
    ))

    # ========== LATEST POINT MARKER ==========
    band_label = f"{'+' if current_band > 0 else ''}{current_band}σ" if current_band is not None else "N/A"
    fig.add_trace(go.Scatter(
        x=[df_new['day_index'].iloc[-1]],
        y=[latest_cum_pct],
        mode='markers',
        name='Latest Value',
        marker=dict(
            color=COLORS['latest_marker'],
            size=14,
            symbol='star',
            line=dict(color='#2c3e50', width=1.5)
        ),
        hovertemplate=(
            f'<b>LATEST</b><br>'
            f'Date: {latest_date_short}<br>'
            f'Price: ${latest_price:.2f}<br>'
            f'Cum. Return: {latest_cum_pct:.2%}<br>'
            f'Band: {band_label}'
            '<extra></extra>'
        ),
        showlegend=True
    ))

    # ========== VERTICAL LINE FOR TODAY ==========
    fig.add_vline(
        x=df_new['day_index'].iloc[-1],
        line=dict(color='rgba(44, 62, 80, 0.5)', width=1, dash='dot'),
        annotation_text=f"Today: {latest_date_short}",
        annotation_position="top",
        annotation_font=dict(size=10, color=COLORS['text'])
    )

    # ========== END-OF-LINE ANNOTATIONS ==========
    # New Period label
    fig.add_annotation(
        x=df_new['day_index'].iloc[-1],
        y=latest_cum_pct,
        text=f"  {latest_cum_pct:.1%}",
        showarrow=False,
        xanchor='left',
        font=dict(size=11, color=COLORS['new_period'], family='Arial Black'),
        bgcolor='rgba(255,255,255,0.8)'
    )

    # Original Period label (at truncated length for comparison)
    if len(df_original) > len(df_new):
        orig_at_new_len = df_original.iloc[len(df_new)-1]['cumulative_pct_change']
        fig.add_annotation(
            x=df_new['day_index'].iloc[-1],
            y=orig_at_new_len,
            text=f"  {orig_at_new_len:.1%}",
            showarrow=False,
            xanchor='left',
            font=dict(size=10, color=COLORS['original_period']),
            bgcolor='rgba(255,255,255,0.8)'
        )

    # Regression line label
    if 'regression_line' in df_original_truncated.columns:
        reg_val = df_original_truncated['regression_line'].iloc[-1]
        fig.add_annotation(
            x=df_original_truncated['day_index'].iloc[-1],
            y=reg_val,
            text=f"  Trend: {reg_val:.1%}",
            showarrow=False,
            xanchor='left',
            font=dict(size=9, color=COLORS['regression_truncated']),
            bgcolor='rgba(255,255,255,0.8)'
        )

    # ========== DUAL X-AXIS: Aligned Days + Actual Dates ==========
    # Create tick positions at key intervals (0%, 25%, 50%, 75%, 100%)
    num_days = len(df_new)
    tick_positions = [0, num_days//4, num_days//2, 3*num_days//4, num_days-1]
    tick_positions = [p for p in tick_positions if p < len(df_new)]

    # Get actual dates for the new period at these positions
    new_period_dates = [df_new.iloc[p]['hover_date'] for p in tick_positions]

    # ========== LAYOUT ==========
    fig.update_layout(
        title=dict(
            text=f"<b>{symbol}</b> | Cumulative Return Comparison vs Historical Regression Bands",
            font=dict(size=18, color=COLORS['text'], family='Arial'),
            x=0.5,
            xanchor='center'
        ),
        # Subtitle with key info
        annotations=[
            dict(
                text=(f"<b>Latest:</b> ${latest_price:.2f} ({latest_cum_pct:+.2%}) on {latest_date_short} | "
                      f"<b>Band:</b> {band_label} | "
                      f"<b>Source:</b> {source.upper()}"),
                xref='paper', yref='paper',
                x=0.5, y=1.06,
                showarrow=False,
                font=dict(size=12, color=COLORS['text']),
                xanchor='center'
            )
        ] + list(fig.layout.annotations),  # Keep existing annotations
        xaxis=dict(
            title=dict(
                text='Aligned Trading Days',
                font=dict(size=12, color=COLORS['text'])
            ),
            showgrid=True,
            gridcolor=COLORS['grid'],
            showline=True,
            linecolor=COLORS['text'],
            showspikes=True,
            spikemode='across',
            spikethickness=1,
            spikecolor='#7f8c8d',
            range=[0, num_days + num_days * 0.08],  # Add padding for labels
        ),
        xaxis2=dict(
            title=dict(
                text='Actual Dates (Trump Term 2)',
                font=dict(size=11, color=COLORS['new_period'])
            ),
            overlaying='x',
            side='bottom',
            position=0,
            tickmode='array',
            tickvals=tick_positions,
            ticktext=new_period_dates,
            tickfont=dict(size=10, color=COLORS['new_period']),
            showgrid=False,
            anchor='free',
        ),
        yaxis=dict(
            title=dict(
                text='Cumulative % Change',
                font=dict(size=12, color=COLORS['text'])
            ),
            tickformat='.1%',
            showgrid=True,
            gridcolor=COLORS['grid'],
            showline=True,
            linecolor=COLORS['text'],
            zeroline=True,
            zerolinecolor='#bdc3c7',
            zerolinewidth=1,
        ),
        legend=dict(
            title=dict(text='Series', font=dict(size=11)),
            orientation='v',
            yanchor='top',
            y=0.99,
            xanchor='right',
            x=0.99,
            bgcolor='rgba(255, 255, 255, 0.9)',
            bordercolor=COLORS['grid'],
            borderwidth=1,
            font=dict(size=10)
        ),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='#f8f9fa',
            font=dict(color=COLORS['text'], size=11),
            bordercolor='#dee2e6'
        ),
        template='plotly_white',
        font=dict(family='Arial, sans-serif', size=12, color=COLORS['text']),
        margin=dict(l=60, r=120, t=100, b=80),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#fafafa',
    )

    # ========== CALCULATE Y-AXIS RANGE ==========
    if 'regression_upper_band_2' in df_original_truncated.columns:
        max_y = max(df_new['cumulative_pct_change'].max(),
                   df_original_truncated['regression_upper_band_2'].max())
        min_y = min(df_new['cumulative_pct_change'].min(),
                   df_original_truncated['regression_lower_band_2'].min())
    else:
        max_y = df_new['cumulative_pct_change'].max()
        min_y = df_new['cumulative_pct_change'].min()

    y_range = max_y - min_y
    buffer = y_range * 0.15
    fig.update_yaxes(range=[min_y - buffer, max_y + buffer])

    # ========== SAVE JPEG ==========
    zoomed_file_jpeg = output_dir / f"{symbol}_zoomed_{source}.jpeg"
    try:
        fig.write_image(str(zoomed_file_jpeg), format='jpeg', width=1600, height=900, scale=2)
        logging.info(f"Zoomed-in plot saved as JPEG to {zoomed_file_jpeg}")
    except Exception as e:
        logging.error(f"Failed to save zoomed-in plot as JPEG: {e}")

    # ========== BUILD HTML WITH CONTEXT HEADER ==========
    html_header = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{symbol} Regression Band Analysis</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1a2332 0%, #2d3748 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            padding: 30px 20px;
            color: white;
        }}
        .header h1 {{
            font-size: 28px;
            font-weight: 300;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }}
        .header .gold {{ color: #d4af37; }}
        .header .subtitle {{
            font-size: 14px;
            color: #a0aec0;
        }}
        .card {{
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
            margin-bottom: 20px;
        }}
        .info-bar {{
            background: linear-gradient(90deg, #f7fafc 0%, #edf2f7 100%);
            padding: 20px 24px;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            flex-wrap: wrap;
            gap: 30px;
            align-items: center;
        }}
        .info-item {{
            display: flex;
            flex-direction: column;
        }}
        .info-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #718096;
            margin-bottom: 4px;
        }}
        .info-value {{
            font-size: 18px;
            font-weight: 600;
            color: #2d3748;
        }}
        .info-value.price {{ color: #1a2332; }}
        .info-value.positive {{ color: #2d6a4f; }}
        .info-value.negative {{ color: #9b2c2c; }}
        .chart-container {{
            padding: 0;
        }}
        .legend-guide {{
            padding: 20px 24px;
            background: #f7fafc;
            border-top: 1px solid #e2e8f0;
        }}
        .legend-guide h3 {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #718096;
            margin-bottom: 12px;
        }}
        .legend-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 12px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
            color: #4a5568;
        }}
        .legend-color {{
            width: 24px;
            height: 4px;
            border-radius: 2px;
            flex-shrink: 0;
        }}
        .legend-color.navy {{ background: #1e3a5f; }}
        .legend-color.red {{ background: #c0392b; width: 24px; height: 5px; }}
        .legend-color.green-dash {{ background: repeating-linear-gradient(90deg, #27ae60 0px, #27ae60 6px, transparent 6px, transparent 10px); }}
        .legend-color.amber {{ background: rgba(212, 175, 55, 0.4); height: 12px; }}
        .legend-color.green-band {{ background: rgba(39, 174, 96, 0.3); height: 12px; }}
        .legend-color.gold-star {{ background: #f1c40f; width: 12px; height: 12px; border-radius: 50%; }}
        .methodology {{
            padding: 20px 24px;
            background: #ffffff;
            border-top: 1px solid #e2e8f0;
        }}
        .methodology h3 {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #d4af37;
            margin-bottom: 10px;
        }}
        .methodology p {{
            font-size: 13px;
            line-height: 1.7;
            color: #4a5568;
            margin-bottom: 10px;
        }}
        .methodology ul {{
            font-size: 13px;
            color: #4a5568;
            margin-left: 20px;
            line-height: 1.8;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #718096;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><span class="gold">{symbol}</span> Regression Band Analysis</h1>
            <p class="subtitle">Comparing Trump Term 2 Performance vs Trump Term 1 Historical Pattern</p>
        </div>

        <div class="card">
            <div class="info-bar">
                <div class="info-item">
                    <span class="info-label">Latest Price</span>
                    <span class="info-value price">${latest_price:.2f}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Cumulative Return</span>
                    <span class="info-value {'positive' if latest_cum_pct >= 0 else 'negative'}">{latest_cum_pct:+.2%}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Current Band</span>
                    <span class="info-value">{band_label}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Trading Days</span>
                    <span class="info-value">{num_days}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">As Of</span>
                    <span class="info-value">{latest_date_short}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Data Source</span>
                    <span class="info-value">{source.upper()}</span>
                </div>
            </div>

            <div class="chart-container">
'''

    html_footer = f'''
            </div>

            <div class="legend-guide">
                <h3>Chart Legend</h3>
                <div class="legend-grid">
                    <div class="legend-item">
                        <div class="legend-color red"></div>
                        <span><strong>Trump Term 2 (Current)</strong> — {new_start} to present</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color navy"></div>
                        <span><strong>Trump Term 1 (Reference)</strong> — {original_start} to {original_end}</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color green-dash"></div>
                        <span><strong>Regression Line</strong> — Expected trend based on matched days</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color green-band"></div>
                        <span><strong>Green Bands (±1σ to ±4σ)</strong> — Active comparison zone</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color amber"></div>
                        <span><strong>Amber Bands</strong> — Full historical period σ bands</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color gold-star"></div>
                        <span><strong>Gold Star</strong> — Latest data point</span>
                    </div>
                </div>
            </div>

            <div class="methodology">
                <h3>Methodology</h3>
                <p>
                    This chart compares the <strong>cumulative daily returns</strong> of {symbol} during two presidential terms,
                    aligned by trading day count from the election date. A linear regression is fitted to the reference period
                    to establish the historical trend, with standard deviation bands (±1σ to ±4σ) showing zones of normal vs. abnormal deviation.
                </p>
                <p><strong>How to read the chart:</strong></p>
                <ul>
                    <li><strong>Above the regression line</strong> = outperforming the historical pattern</li>
                    <li><strong>Below the regression line</strong> = underperforming the historical pattern</li>
                    <li><strong>Within ±1σ</strong> = typical variation (~68% of observations)</li>
                    <li><strong>Beyond ±2σ</strong> = unusual deviation (~5% probability)</li>
                    <li><strong>Beyond ±3σ</strong> = extreme deviation (&lt;1% probability)</li>
                </ul>
            </div>

            <div class="methodology">
                <h3>Interactive Features</h3>
                <ul>
                    <li><strong>Hover</strong> — See exact date, price, and cumulative return for any point</li>
                    <li><strong>Click legend items</strong> — Toggle series visibility on/off</li>
                    <li><strong>Drag to zoom</strong> — Select an area to zoom in</li>
                    <li><strong>Double-click</strong> — Reset zoom to full view</li>
                    <li><strong>Toolbar (top-right)</strong> — Download as PNG, pan, zoom, autoscale</li>
                </ul>
            </div>
        </div>

        <div class="footer">
            Compare Timeframes Analysis System · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
            <br>This is a descriptive analytical tool, not investment advice or a trading signal.
        </div>
    </div>
</body>
</html>
'''

    # Generate Plotly HTML (just the chart div)
    chart_html = fig.to_html(
        full_html=False,
        include_plotlyjs='cdn',
        config={
            'displayModeBar': True,
            'displaylogo': False,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
            'toImageButtonOptions': {
                'format': 'png',
                'filename': f'{symbol}_regression_analysis',
                'height': 900,
                'width': 1600,
                'scale': 2
            }
        }
    )

    # Combine header + chart + footer
    full_html = html_header + chart_html + html_footer

    # Save the HTML file
    html_file = output_dir / f"{symbol}_{source}.html"
    try:
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(full_html)
        logging.info(f"Interactive HTML saved to {html_file}")
    except Exception as e:
        logging.error(f"Failed to save HTML: {e}")

    return zoomed_file_jpeg, html_file

def get_regression_band(current_pct, df_truncated):
    """
    Determine the regression band based on explicit intervals rather than rounding.
    This ensures stable band assignment and avoids small fluctuations causing unnecessary emails.
    """
    reg_line = df_truncated['regression_line'].iloc[-1]
    upper_1 = df_truncated['regression_upper_band_1'].iloc[-1]
    upper_2 = df_truncated['regression_upper_band_2'].iloc[-1]
    upper_3 = df_truncated['regression_upper_band_3'].iloc[-1]
    upper_4 = df_truncated['regression_upper_band_4'].iloc[-1]

    lower_1 = df_truncated['regression_lower_band_1'].iloc[-1]
    lower_2 = df_truncated['regression_lower_band_2'].iloc[-1]
    lower_3 = df_truncated['regression_lower_band_3'].iloc[-1]
    lower_4 = df_truncated['regression_lower_band_4'].iloc[-1]

    # Check from top to bottom:
    if current_pct > upper_4:
        return 4
    elif current_pct > upper_3:
        return 3
    elif current_pct > upper_2:
        return 2
    elif current_pct > upper_1:
        return 1
    elif current_pct > reg_line:
        return 0
    elif current_pct > lower_1:
        return -1
    elif current_pct > lower_2:
        return -2
    elif current_pct > lower_3:
        return -3
    elif current_pct > lower_4:
        return -4
    else:
        # If current_pct is even lower than lower_4, it's below -4
        # This shouldn't normally happen if -4σ is the lowest band, but let's just return -4 in that case.
        return -4


def main_loop(symbol, source, original_start, original_end, new_start, new_end, sma_window, plot_bands,
              plot_bollinger_bands, email_notifications, email_recipients, check_frequency, html_output_path):
    """
    Main function to load data, calculate percent changes, plot comparison, and send emails.
    """
    previous_band = None  # Store the previous band for comparison

    while True:
        # Load data and process
        try:
            now = datetime.now(timezone.utc)
            logging.info(f"Running analysis for {symbol} at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            df = load_data(symbol, source)

            if df.empty:
                logging.warning(f"No data available for {symbol}. Skipping analysis.")
                continue

            # Adjust new_end to include the latest data without excluding it
            latest_data_date = df['index'].max()
            logging.info(f"Latest data date: {latest_data_date}")

            today = datetime.now(timezone.utc)
            adjusted_new_end = min(latest_data_date, today)

            # Calculate cumulative percent change for original and new periods
            df_original = calculate_cumulative_pct_change(df, original_start, original_end, sma_window=sma_window,
                                                          plot_bollinger_bands=plot_bollinger_bands)
            df_new = calculate_cumulative_pct_change(df, new_start, adjusted_new_end)

            df_original['day_index'] = range(len(df_original))
            df_new['day_index'] = range(len(df_new))

            # Calculate regression bands
            if not df_original.empty:
                df_original = calculate_regression_bands(df_original)
            else:
                logging.warning("df_original is empty after filtering.")

            num_days_new = len(df_new)
            df_original_truncated = df_original.iloc[:num_days_new].copy()
            df_original_truncated.reset_index(drop=True, inplace=True)
            df_original_truncated['day_index'] = range(len(df_original_truncated))

            if not df_original_truncated.empty:
                df_original_truncated = calculate_regression_bands(df_original_truncated)
            else:
                logging.warning("df_original_truncated is empty after filtering.")

            # Determine the current regression band
            latest_cumulative_pct_change = df_new['cumulative_pct_change'].iloc[-1]
            current_band = get_regression_band(latest_cumulative_pct_change, df_original_truncated)

            # Plot the comparison and update HTML file
            output_dir = Path('./plots')
            output_dir.mkdir(parents=True, exist_ok=True)
            jpeg_path, html_path = plot_comparison(symbol, df_original, df_original_truncated, df_new, output_dir,
                                                   sma_window, source, plot_bands, plot_bollinger_bands,
                                                   original_start, original_end, new_start)

            if html_output_path and html_path:
                # Copy or move the HTML file to the desired output path
                try:
                    copyfile(html_path, html_output_path)
                    logging.info(f"Updated HTML file at {html_output_path}")
                except Exception as e:
                    logging.error(f"Failed to update HTML file at {html_output_path}: {e}")

            # Only send email if this isn't the first loop (previous_band is not None) AND a change occurred
            if previous_band is None:
                # Initial run: just set previous_band without sending an email
                previous_band = current_band
            else:
                if current_band != previous_band:
                    logging.info(f"Regression band changed from {previous_band} to {current_band}.")
                    if email_notifications and jpeg_path and jpeg_path.exists():
                        logging.info(f"Sending professional HTML email with inline chart")

                        # Retrieve current values
                        current_pct = latest_cumulative_pct_change
                        reg_line = df_original_truncated['regression_line'].iloc[-1]

                        # Bands for +1σ to +4σ
                        upper_1 = df_original_truncated['regression_upper_band_1'].iloc[-1]
                        upper_2 = df_original_truncated['regression_upper_band_2'].iloc[-1]
                        upper_3 = df_original_truncated['regression_upper_band_3'].iloc[-1]
                        upper_4 = df_original_truncated['regression_upper_band_4'].iloc[-1]

                        # Bands for -1σ to -4σ
                        lower_1 = df_original_truncated['regression_lower_band_1'].iloc[-1]
                        lower_2 = df_original_truncated['regression_lower_band_2'].iloc[-1]
                        lower_3 = df_original_truncated['regression_lower_band_3'].iloc[-1]
                        lower_4 = df_original_truncated['regression_lower_band_4'].iloc[-1]

                        # Build bands dictionary for template
                        bands = {
                            '+4σ': upper_4,
                            '+3σ': upper_3,
                            '+2σ': upper_2,
                            '+1σ': upper_1,
                            'avg': reg_line,
                            '-1σ': lower_1,
                            '-2σ': lower_2,
                            '-3σ': lower_3,
                            '-4σ': lower_4
                        }

                        # Get latest price and timestamp
                        latest_price = df_new.iloc[-1]['adj_close']
                        latest_date = df_new.iloc[-1]['index']
                        timestamp_utc = latest_date.strftime('%Y-%m-%d %H:%M:%S UTC')

                        # Calculate days in each period
                        days_original = len(df_original)
                        days_new = len(df_new)

                        # HTML link - only include if it's a real URL (not a local path)
                        # Local file paths won't work for email recipients
                        html_link = None
                        # To enable: set html_output_path to a publicly accessible URL
                        # e.g., "https://yourdomain.com/charts/VOO_alpaca.html"

                        # Format period dates for display
                        from datetime import datetime as dt
                        orig_start_dt = dt.strptime(original_start, '%Y-%m-%d')
                        orig_end_dt = dt.strptime(original_end, '%Y-%m-%d')
                        new_start_dt = dt.strptime(new_start, '%Y-%m-%d')

                        # Build professional HTML email content with period context
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
                            # Period context for methodology explanation
                            reference_period_name="Trump First Term",
                            reference_start=orig_start_dt.strftime('%b %Y'),
                            reference_end=orig_end_dt.strftime('%b %Y'),
                            current_period_name="Trump Second Term",
                            current_start=new_start_dt.strftime('%b %Y'),
                            html_link=html_link
                        )

                        # Read JPEG for inline embedding
                        with open(jpeg_path, 'rb') as f:
                            chart_bytes = f.read()

                        # Prepare inline image
                        inline_images = [{
                            'cid': 'chart',
                            'content': chart_bytes,
                            'subtype': 'jpeg'
                        }]

                        subject = f"📈 Regression Band Alert: {symbol} → {'+' if current_band > 0 else ''}{current_band}σ"

                        success, message = send_email(
                            to_addrs=email_recipients,
                            subject=subject,
                            body=None,
                            html_body=html_body,
                            text_body=text_body,
                            inline_images=inline_images
                        )
                        if success:
                            logging.info("Professional HTML email sent successfully.")
                        else:
                            logging.error(f"Failed to send email: {message}")

                    previous_band = current_band



        except Exception as e:
            logging.error(f"Error during analysis: {e}")

        # Sleep for the specified check frequency
        logging.info(f"Sleeping for {check_frequency} minutes before the next check...")
        time.sleep(check_frequency * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare an asset's historical performance with indicators.")
    parser.add_argument('--symbol', type=str, default="VOO", help="The asset symbol to analyze.")
    parser.add_argument('--source', type=str, choices=['yfinance', 'alpaca'], default="alpaca",
                        help="Data source to use (yfinance or alpaca).")
    parser.add_argument('--original_start', type=str, default="2016-11-08",
                        help="Start date for the original period (YYYY-MM-DD).")
    parser.add_argument('--original_end', type=str, default="2020-11-03",
                        help="End date for the original period (YYYY-MM-DD).")
    parser.add_argument('--new_start', type=str, default="2024-11-05",
                        help="Start date for the new period (YYYY-MM-DD).")
    parser.add_argument('--new_end', type=str, default=datetime.today().strftime('%Y-%m-%d'),
                        help="End date for the new period (YYYY-MM-DD).")
    parser.add_argument('--sma_window', type=int, default=100,
                        help="Window size for the Simple Moving Average (default: 100 days).")
    parser.add_argument('--plot_bands', action='store_true', default=True,
                        help="Plot linear regression and standard deviation bands.")
    parser.add_argument('--plot_bollinger_bands', action='store_true',
                        help="Plot Bollinger Bands.")
    parser.add_argument('--email_notifications', action='store_true', default=True,
                        help="Enable email notifications with JPEG attachments.")
    parser.add_argument('--email_recipients', nargs='+', default=None,
                        help="Email address(es) to send notifications to. If not specified, reads from email_recipients.txt")
    parser.add_argument('--check_frequency', type=int, default=15,
                        help="Frequency (in minutes) to check for updates (default: 15).")
    parser.add_argument('--html_output_path', type=str, default='./plots/index.html',
                        help="Path to output the HTML file.")

    args = parser.parse_args()

    # Load email recipients from file if not provided via CLI
    email_recipients = args.email_recipients if args.email_recipients else load_email_recipients()

    main_loop(
        symbol=args.symbol,
        source=args.source,
        original_start=args.original_start,
        original_end=args.original_end,
        new_start=args.new_start,
        new_end=args.new_end,
        sma_window=args.sma_window,
        plot_bands=args.plot_bands,
        plot_bollinger_bands=args.plot_bollinger_bands,
        email_notifications=args.email_notifications,
        email_recipients=email_recipients,
        check_frequency=args.check_frequency,
        html_output_path=args.html_output_path
    )
