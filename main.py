import argparse
import json
import logging
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from shutil import copyfile

from email_template import build_email_content
from send_gmail import send_email
from service_bootstrap import (
    build_preflight_report,
    load_asset_prices_reader,
    print_preflight_report,
)
from service_config import (
    load_gmail_secret_config,
    load_service_config,
    redact_service_config,
)

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

pd = None
np = None
go = None


def _load_analysis_dependencies():
    global go, np, pd

    if pd is None:
        import pandas as pandas_module

        pd = pandas_module

    if np is None:
        import numpy as numpy_module

        np = numpy_module

    if go is None:
        import plotly.graph_objects as go_module

        go = go_module

    return pd, np, go


def _configure_logging(log_path=None):
    handlers = [logging.StreamHandler()]

    if log_path:
        log_file = Path(log_path).expanduser()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.insert(0, logging.FileHandler(log_file))

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
        force=True,
    )


def _resolve_output_dir(html_output_path):
    html_output = Path(html_output_path).expanduser()
    return html_output.parent if html_output.parent != Path("") else Path(".")


_configure_logging()

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

def load_data(
    symbol,
    source,
    start_date=None,
    end_date=None,
    data_type="adjusted",
    data_dir=None,
    read_symbol_data_fn=None,
):
    """Load price data using the asset_prices partition-aware reader."""
    pd_module, _, _ = _load_analysis_dependencies()

    if read_symbol_data_fn is None:
        raise ValueError("read_symbol_data_fn is required.")
    if data_dir is None:
        raise ValueError("data_dir is required.")

    df = read_symbol_data_fn(
        symbol=symbol,
        source=source,
        data_type=data_type,
        start_date=start_date,
        end_date=end_date,
        base_dir=Path(data_dir)
    )

    if df.empty:
        logging.warning(f"No data returned for {symbol} from {source} ({data_type}).")
        return df

    df = df.copy()

    # Normalize the datetime column
    if 'timestamp' in df.columns:
        df.rename(columns={'timestamp': 'index'}, inplace=True)
    elif pd_module.api.types.is_datetime64_any_dtype(df.index):
        index_name = df.index.name or 'index'
        df = df.reset_index().rename(columns={index_name: 'index'})
    else:
        datetime_cols = [col for col in df.columns if pd_module.api.types.is_datetime64_any_dtype(df[col])]
        if datetime_cols:
            df.rename(columns={datetime_cols[0]: 'index'}, inplace=True)
        else:
            raise ValueError("Dataset must have a datetime 'timestamp' column or index.")

    df['index'] = pd_module.to_datetime(df['index'], utc=True, errors='coerce')
    df = df.dropna(subset=['index'])

    if "adj_close" not in df.columns:
        if "Adj Close" in df.columns:
            df.rename(columns={"Adj Close": "adj_close"}, inplace=True)
        elif "close" in df.columns:
            df.rename(columns={"close": "adj_close"}, inplace=True)
        else:
            raise ValueError("Missing `adj_close` column in data.")

    df = df[['index', 'adj_close']].dropna(subset=['adj_close'])
    df = df.sort_values('index').reset_index(drop=True)

    if not df.empty:
        min_date = df['index'].min()
        max_date = df['index'].max()
        logging.info(
            f"Loaded {len(df)} rows for {symbol} from {source} ({data_type}) "
            f"via asset_prices at {data_dir} | range {min_date} → {max_date}"
        )
    else:
        logging.warning(f"No data available for {symbol} after cleaning.")

    return df

def calculate_cumulative_pct_change(df, start_date, end_date, sma_window=None, plot_bollinger_bands=False):
    """
    Calculates the cumulative percent change for a given date range
    and applies SMA and Bollinger Bands if specified.
    """
    pd_module, _, _ = _load_analysis_dependencies()

    # Convert start_date and end_date to datetime with the same timezone as 'index'
    start_date = pd_module.to_datetime(start_date)
    end_date = pd_module.to_datetime(end_date)

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
    _, np_module, _ = _load_analysis_dependencies()

    if df.empty:
        raise ValueError("DataFrame is empty. Cannot perform regression.")

    # Ensure that 'cumulative_pct_change' column exists
    if 'cumulative_pct_change' not in df.columns:
        raise ValueError("DataFrame must contain 'cumulative_pct_change' column for regression analysis.")

    x = df['day_index'].values
    y = df['cumulative_pct_change'].values

    # Fit a linear regression model
    coef = np_module.polyfit(x, y, 1)
    df['regression_line'] = coef[0] * x + coef[1]

    # Calculate residuals and standard deviation
    residuals = y - df['regression_line']
    residual_std = np_module.std(residuals)

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
    _, _, go_module = _load_analysis_dependencies()
    go = go_module

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
    fig = go_module.Figure()

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
            title=dict(text='', font=dict(size=10)),
            orientation='h',
            yanchor='top',
            y=-0.12,
            xanchor='center',
            x=0.5,
            bgcolor='rgba(255, 255, 255, 0.9)',
            bordercolor=COLORS['grid'],
            borderwidth=1,
            font=dict(size=9)
        ),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='#f8f9fa',
            font=dict(color=COLORS['text'], size=11),
            bordercolor='#dee2e6'
        ),
        template='plotly_white',
        font=dict(family='Arial, sans-serif', size=12, color=COLORS['text']),
        margin=dict(l=60, r=60, t=100, b=120),
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

    # ========== SAVE ZOOMED JPEG (current period view) ==========
    zoomed_file_jpeg = output_dir / f"{symbol}_zoomed_{source}.jpeg"
    try:
        fig.write_image(str(zoomed_file_jpeg), format='jpeg', width=1600, height=900, scale=2)
        logging.info(f"Zoomed-in plot saved as JPEG to {zoomed_file_jpeg}")
    except Exception as e:
        logging.error(f"Failed to save zoomed-in plot as JPEG: {e}")
        zoomed_file_jpeg = None

    # ========== SAVE FULL-TERM JPEG (entire original period view) ==========
    # Adjust x-axis to show full original period
    full_term_fig = go.Figure(fig)
    full_num_days = len(df_original)
    full_term_fig.update_xaxes(range=[0, full_num_days + full_num_days * 0.05])

    # Recalculate y-axis for full range
    if 'regression_upper_band_3' in df_original.columns:
        full_max_y = max(df_original['cumulative_pct_change'].max(),
                        df_original['regression_upper_band_3'].max())
        full_min_y = min(df_original['cumulative_pct_change'].min(),
                        df_original['regression_lower_band_3'].min())
    else:
        full_max_y = df_original['cumulative_pct_change'].max()
        full_min_y = df_original['cumulative_pct_change'].min()

    full_y_range = full_max_y - full_min_y
    full_buffer = full_y_range * 0.1
    full_term_fig.update_yaxes(range=[full_min_y - full_buffer, full_max_y + full_buffer])

    # Update title for full-term view
    full_term_fig.update_layout(
        title=dict(
            text=f"<b>{symbol}</b> | Full Reference Period ({original_start[:4]}–{original_end[:4]}) vs Current",
        )
    )

    full_file_jpeg = output_dir / f"{symbol}_full_{source}.jpeg"
    try:
        full_term_fig.write_image(str(full_file_jpeg), format='jpeg', width=1600, height=900, scale=2)
        logging.info(f"Full-term plot saved as JPEG to {full_file_jpeg}")
    except Exception as e:
        logging.error(f"Failed to save full-term plot as JPEG: {e}")
        full_file_jpeg = None

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

    return zoomed_file_jpeg, full_file_jpeg, html_file

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


def send_test_email_now(
    symbol,
    source,
    original_start,
    original_end,
    new_start,
    new_end,
    sma_window,
    plot_bands,
    plot_bollinger_bands,
    email_recipients,
    html_output_path,
    data_dir,
    data_type,
    read_symbol_data_fn,
    check_frequency,
):
    """
    Run one analysis cycle and send a test email with the current chart.
    """
    pd_module, _, _ = _load_analysis_dependencies()
    earliest_start = min(pd_module.to_datetime(original_start), pd_module.to_datetime(new_start)).strftime('%Y-%m-%d')
    parsed_end = pd_module.to_datetime(new_end) if new_end else None
    end_date = parsed_end.strftime('%Y-%m-%d') if parsed_end is not None else None

    logging.info(f"Generating test email for {symbol}...")

    df = load_data(
        symbol,
        source,
        start_date=earliest_start,
        end_date=end_date,
        data_type=data_type,
        data_dir=data_dir,
        read_symbol_data_fn=read_symbol_data_fn,
    )
    if df.empty:
        logging.error(f"No data available for {symbol}. Cannot send test email.")
        return False

    latest_data_date = df['index'].max()
    today = datetime.now(timezone.utc)
    adjusted_new_end = min(latest_data_date, today)

    df_original = calculate_cumulative_pct_change(df, original_start, original_end, sma_window=sma_window,
                                                  plot_bollinger_bands=plot_bollinger_bands)
    df_new = calculate_cumulative_pct_change(df, new_start, adjusted_new_end)

    df_original['day_index'] = range(len(df_original))
    df_new['day_index'] = range(len(df_new))

    if not df_original.empty:
        df_original = calculate_regression_bands(df_original)

    num_days_new = len(df_new)
    df_original_truncated = df_original.iloc[:num_days_new].copy()
    df_original_truncated.reset_index(drop=True, inplace=True)
    df_original_truncated['day_index'] = range(len(df_original_truncated))

    if not df_original_truncated.empty:
        df_original_truncated = calculate_regression_bands(df_original_truncated)

    # Generate charts
    output_dir = _resolve_output_dir(html_output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    zoomed_jpeg_path, full_jpeg_path, html_path = plot_comparison(symbol, df_original, df_original_truncated, df_new, output_dir,
                                           sma_window, source, plot_bands, plot_bollinger_bands,
                                           original_start, original_end, new_start)

    if html_output_path and html_path:
        try:
            copyfile(html_path, html_output_path)
            logging.info(f"Updated HTML file at {html_output_path}")
        except Exception as e:
            logging.error(f"Failed to update HTML file: {e}")

    if not zoomed_jpeg_path or not zoomed_jpeg_path.exists():
        logging.error("Failed to generate zoomed chart. Cannot send test email.")
        return False

    if not full_jpeg_path or not full_jpeg_path.exists():
        logging.warning("Failed to generate full-term chart. Email will only include zoomed chart.")

    # Get current values
    latest_cumulative_pct_change = df_new['cumulative_pct_change'].iloc[-1]
    current_band = get_regression_band(latest_cumulative_pct_change, df_original_truncated)
    current_pct = latest_cumulative_pct_change
    reg_line = df_original_truncated['regression_line'].iloc[-1]

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

    from datetime import datetime as dt
    orig_start_dt = dt.strptime(original_start, '%Y-%m-%d')
    orig_end_dt = dt.strptime(original_end, '%Y-%m-%d')
    new_start_dt = dt.strptime(new_start, '%Y-%m-%d')

    html_body, text_body = build_email_content(
        symbol=symbol,
        source=source,
        timestamp_utc=timestamp_utc,
        latest_price=latest_price,
        previous_band=current_band,  # Same as current for test
        current_band=current_band,
        current_pct=current_pct,
        regression_line=reg_line,
        bands=bands,
        days_original=len(df_original),
        days_new=len(df_new),
        sma_window=sma_window,
        check_frequency=check_frequency,
        reference_period_name="Trump First Term",
        reference_start=orig_start_dt.strftime('%b %Y'),
        reference_end=orig_end_dt.strftime('%b %Y'),
        current_period_name="Trump Second Term",
        current_start=new_start_dt.strftime('%b %Y'),
        html_link=None
    )

    # Read chart images
    with open(zoomed_jpeg_path, 'rb') as f:
        zoomed_chart_bytes = f.read()

    inline_images = [{
        'cid': 'chart_zoomed',
        'content': zoomed_chart_bytes,
        'subtype': 'jpeg'
    }]

    # Add full-term chart if available
    if full_jpeg_path and full_jpeg_path.exists():
        with open(full_jpeg_path, 'rb') as f:
            full_chart_bytes = f.read()
        inline_images.append({
            'cid': 'chart_full',
            'content': full_chart_bytes,
            'subtype': 'jpeg'
        })

    band_label = f"{'+' if current_band > 0 else ''}{current_band}σ"
    subject = f"🧪 TEST EMAIL: {symbol} @ {band_label} ({current_pct:+.2%})"

    success, message = send_email(
        to_addrs=email_recipients,
        subject=subject,
        body=None,
        html_body=html_body,
        text_body=text_body,
        inline_images=inline_images
    )

    if success:
        logging.info(f"Test email sent successfully to {email_recipients}")
    else:
        logging.error(f"Failed to send test email: {message}")

    return success


def main_loop(
    symbol,
    source,
    original_start,
    original_end,
    new_start,
    new_end,
    sma_window,
    plot_bands,
    plot_bollinger_bands,
    email_notifications,
    email_recipients,
    check_frequency,
    html_output_path,
    data_dir,
    data_type,
    read_symbol_data_fn,
):
    """
    Main function to load data, calculate percent changes, plot comparison, and send emails.
    """
    pd_module, _, _ = _load_analysis_dependencies()
    earliest_start = min(pd_module.to_datetime(original_start), pd_module.to_datetime(new_start)).strftime('%Y-%m-%d')
    parsed_end = pd_module.to_datetime(new_end) if new_end else None
    end_date = parsed_end.strftime('%Y-%m-%d') if parsed_end is not None else None
    previous_band = None  # Store the previous band for comparison
    output_dir = _resolve_output_dir(html_output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    while True:
        # Load data and process
        try:
            now = datetime.now(timezone.utc)
            logging.info(f"Running analysis for {symbol} at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            df = load_data(
                symbol,
                source,
                start_date=earliest_start,
                end_date=end_date,
                data_type=data_type,
                data_dir=data_dir,
                read_symbol_data_fn=read_symbol_data_fn,
            )

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
            zoomed_jpeg_path, full_jpeg_path, html_path = plot_comparison(symbol, df_original, df_original_truncated, df_new, output_dir,
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
                    if email_notifications and zoomed_jpeg_path and zoomed_jpeg_path.exists():
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

                        # Read JPEGs for inline embedding
                        with open(zoomed_jpeg_path, 'rb') as f:
                            zoomed_chart_bytes = f.read()

                        # Prepare inline images
                        inline_images = [{
                            'cid': 'chart_zoomed',
                            'content': zoomed_chart_bytes,
                            'subtype': 'jpeg'
                        }]

                        # Add full-term chart if available
                        if full_jpeg_path and full_jpeg_path.exists():
                            with open(full_jpeg_path, 'rb') as f:
                                full_chart_bytes = f.read()
                            inline_images.append({
                                'cid': 'chart_full',
                                'content': full_chart_bytes,
                                'subtype': 'jpeg'
                            })

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

def _add_shared_cli_options(parser):
    parser.add_argument(
        "--config",
        default=str(Path("config") / "service.json"),
        help="Path to the committed service config file.",
    )
    parser.add_argument(
        "--local-config",
        default=str(Path("config") / "service.local.json"),
        help="Path to the local override config file.",
    )
    parser.add_argument(
        "--env-file",
        default=None,
        help="Optional secret file path. Defaults to .env.local with legacy fallback to ~/.gmail_send/.env.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output where supported.",
    )


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Run the Trump Era Delta monitor with validated service configuration."
    )
    subparsers = parser.add_subparsers(dest="command")

    check_parser = subparsers.add_parser(
        "check",
        help="Validate config, paths, recipients, and Gmail readiness without sending mail.",
    )
    _add_shared_cli_options(check_parser)

    run_parser = subparsers.add_parser(
        "run",
        help="Run the monitoring loop after preflight validation succeeds.",
    )
    _add_shared_cli_options(run_parser)

    test_email_parser = subparsers.add_parser(
        "test-email",
        help="Run one analysis cycle and send a test email after preflight validation.",
    )
    _add_shared_cli_options(test_email_parser)

    show_config_parser = subparsers.add_parser(
        "show-config",
        help="Print the merged config with secrets redacted.",
    )
    _add_shared_cli_options(show_config_parser)

    return parser


def _prepare_validation_config(config, force_alert_readiness=False):
    validation_config = deepcopy(config)
    if force_alert_readiness:
        validation_config.setdefault("alerts", {})["enabled"] = True
    return validation_config


def _load_command_context(args, require_gmail=False, force_alert_readiness=False):
    config, metadata, config_error = load_service_config(
        config_path=args.config,
        local_config_path=args.local_config,
    )
    metadata = dict(metadata or {})

    if config is None:
        config = {
            "asset_prices": {},
            "monitor": {},
            "alerts": {},
            "runtime": {},
            "_metadata": metadata,
        }

    gmail_config, secret_source, gmail_error = load_gmail_secret_config(env_file=args.env_file)
    if secret_source:
        metadata["secret_source"] = secret_source
        config.setdefault("_metadata", {})["secret_source"] = secret_source

    validation_config = _prepare_validation_config(config, force_alert_readiness=force_alert_readiness)
    validation_config["_metadata"] = dict(validation_config.get("_metadata", {}), **metadata)

    report = build_preflight_report(
        validation_config,
        metadata,
        gmail_config=None if gmail_error else gmail_config,
        require_gmail=require_gmail,
    )

    if config_error and config_error not in report["errors"]:
        report["errors"].insert(0, config_error)
    if gmail_error and require_gmail and gmail_error not in report["errors"]:
        report["errors"].append(gmail_error)

    report["ok"] = not report["errors"]
    return config, metadata, gmail_config, report, config_error, gmail_error


def _runtime_settings_from_config(config, reader_callable):
    asset_prices = config.get("asset_prices", {})
    monitor = config.get("monitor", {})
    alerts = config.get("alerts", {})
    runtime = config.get("runtime", {})

    return {
        "symbol": monitor.get("symbol", "VOO"),
        "source": monitor.get("source", "alpaca"),
        "original_start": monitor.get("original_start", "2016-11-08"),
        "original_end": monitor.get("original_end", "2020-11-03"),
        "new_start": monitor.get("new_start", "2024-11-05"),
        "new_end": monitor.get("new_end", datetime.today().strftime("%Y-%m-%d")),
        "sma_window": monitor.get("sma_window", 100),
        "plot_bands": monitor.get("plot_bands", True),
        "plot_bollinger_bands": monitor.get("plot_bollinger_bands", False),
        "email_notifications": alerts.get("enabled", True),
        "email_recipients": alerts.get("recipients", []),
        "check_frequency": monitor.get("check_frequency_minutes", 15),
        "html_output_path": runtime.get("html_output_path", "./plots/index.html"),
        "log_path": runtime.get("log_path", "./runtime/main.log"),
        "data_dir": asset_prices.get("data_dir"),
        "data_type": asset_prices.get("data_type", "adjusted"),
        "read_symbol_data_fn": reader_callable,
    }


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "check":
        config, metadata, _gmail_config, report, _config_error, _gmail_error = _load_command_context(
            args,
            require_gmail=True,
            force_alert_readiness=True,
        )
        print_preflight_report(report, as_json=args.json)
        return 0 if report["ok"] else 1

    if args.command == "show-config":
        config, metadata, _gmail_config, report, config_error, _gmail_error = _load_command_context(
            args,
            require_gmail=False,
            force_alert_readiness=False,
        )
        if config_error:
            print_preflight_report(report, as_json=args.json)
            return 1

        rendered = redact_service_config(config, metadata)
        if args.json:
            print(json.dumps(rendered, indent=2, sort_keys=True))
        else:
            print(json.dumps(rendered, indent=2, sort_keys=True))
        return 0

    require_gmail = args.command == "test-email"
    force_alert_readiness = args.command in {"check", "test-email"}

    config, metadata, gmail_config, report, _config_error, _gmail_error = _load_command_context(
        args,
        require_gmail=require_gmail,
        force_alert_readiness=force_alert_readiness,
    )

    if args.command == "run" and config.get("alerts", {}).get("enabled"):
        require_gmail = True
        config, metadata, gmail_config, report, _config_error, _gmail_error = _load_command_context(
            args,
            require_gmail=True,
            force_alert_readiness=False,
        )

    if not report["ok"]:
        print_preflight_report(report, as_json=args.json)
        return 1

    reader_callable, reader_error = load_asset_prices_reader(config["asset_prices"]["repo_path"])
    if reader_error:
        report["errors"].append(reader_error)
        report["ok"] = False
        print_preflight_report(report, as_json=args.json)
        return 1

    runtime_settings = _runtime_settings_from_config(config, reader_callable)
    _configure_logging(runtime_settings["log_path"])

    if args.command == "run":
        main_loop(**runtime_settings)
        return 0

    success = send_test_email_now(
        symbol=runtime_settings["symbol"],
        source=runtime_settings["source"],
        original_start=runtime_settings["original_start"],
        original_end=runtime_settings["original_end"],
        new_start=runtime_settings["new_start"],
        new_end=runtime_settings["new_end"],
        sma_window=runtime_settings["sma_window"],
        plot_bands=runtime_settings["plot_bands"],
        plot_bollinger_bands=runtime_settings["plot_bollinger_bands"],
        email_recipients=runtime_settings["email_recipients"],
        html_output_path=runtime_settings["html_output_path"],
        data_dir=runtime_settings["data_dir"],
        data_type=runtime_settings["data_type"],
        read_symbol_data_fn=runtime_settings["read_symbol_data_fn"],
        check_frequency=runtime_settings["check_frequency"],
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
