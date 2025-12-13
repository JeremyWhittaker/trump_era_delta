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

def plot_comparison(symbol, df_original, df_original_truncated, df_new, output_dir, sma_window, source, plot_bands=False, plot_bollinger_bands=False):
    """
    Plots cumulative percent change, Bollinger Bands, and regression bands on the original period,
    and compares with the new period's cumulative percent change.
    Also plots regression line/bands on the truncated original data.
    Additionally, saves the plot as a JPEG image and HTML file.
    """
    if df_new.empty:
        logging.warning(f"No new period data available for plotting for {symbol}. Skipping plot.")
        return None, None

    # Prepare hover data and alignment indices
    df_original['hover_date'] = df_original['index'].dt.strftime('%Y-%m-%d')
    df_original['hover_price'] = df_original['adj_close']
    df_original_truncated['hover_date'] = df_original_truncated['index'].dt.strftime('%Y-%m-%d')
    df_original_truncated['hover_price'] = df_original_truncated['adj_close']
    df_new['hover_date'] = df_new['index'].dt.strftime('%Y-%m-%d')
    df_new['hover_price'] = df_new['adj_close']

    # Get the latest price and date from the data
    latest_price = df_new.iloc[-1]['adj_close']
    latest_date = df_new.iloc[-1]['index']
    latest_datetime = latest_date.strftime('%Y-%m-%d %H:%M:%S %Z')

    # Create the plot
    fig = go.Figure()

    # Original period cumulative percent change
    fig.add_trace(
        go.Scatter(
            x=df_original['day_index'],
            y=df_original['cumulative_pct_change'],
            mode='lines',
            name='Original Period',
            hoverinfo='skip',  # Disable hover for this trace
            line=dict(color='blue')
        )
    )

    # Bollinger Bands for original data
    if plot_bollinger_bands and 'upper_band' in df_original.columns and 'lower_band' in df_original.columns:
        fig.add_trace(
            go.Scatter(
                x=df_original['day_index'],
                y=df_original['upper_band'],
                line=dict(color='rgba(0,0,0,0)'),  # Invisible line
                name='Bollinger Bands',
                showlegend=False,
                hoverinfo='skip'  # Disable hover
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_original['day_index'],
                y=df_original['lower_band'],
                line=dict(color='rgba(0,0,0,0)'),  # Invisible line
                fill='tonexty',
                fillcolor='rgba(173, 216, 230, 0.3)',  # Light blue fill
                name='Bollinger Bands',
                hoverinfo='skip',  # Disable hover
                showlegend=True
            )
        )

    # Regression line and bands on df_original
    if 'regression_line' in df_original.columns:
        fig.add_trace(
            go.Scatter(
                x=df_original['day_index'],
                y=df_original['regression_line'],
                mode='lines',
                name='Regression Line (Original)',
                line=dict(color='black'),
                hoverinfo='skip',  # Disable hover
            )
        )

        # Plot filled regression bands for original data
        if plot_bands and 'regression_upper_band_1' in df_original.columns:
            max_stddev = 4  # Changed to 4
            # Ensure colors list has 4 colors
            colors = [
                'rgba(255, 165, 0, 0.15)',  # Orange, alpha=0.15
                'rgba(255, 165, 0, 0.1)',   # Orange, alpha=0.1
                'rgba(255, 165, 0, 0.07)',  # Orange, alpha=0.07
                'rgba(255, 165, 0, 0.04)'   # Orange, alpha=0.04
            ]

            # Upper bands for original data
            for i in range(max_stddev, 0, -1):
                upper_band = df_original[f'regression_upper_band_{i}']
                lower_band = df_original[f'regression_upper_band_{i - 1}'] if i > 1 else df_original['regression_line']

                fig.add_trace(
                    go.Scatter(
                        x=df_original['day_index'],
                        y=upper_band,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'  # Disable hover
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_original['day_index'],
                        y=lower_band,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor=colors[max_stddev - i],
                        name=f'+{i}σ Regression Band' if i == 1 else None,
                        hoverinfo='skip',  # Disable hover
                        showlegend=i == 1
                    )
                )

            # Lower bands for original data
            for i in range(max_stddev, 0, -1):
                lower_band = df_original[f'regression_lower_band_{i}']
                upper_band = df_original[f'regression_lower_band_{i - 1}'] if i > 1 else df_original['regression_line']

                fig.add_trace(
                    go.Scatter(
                        x=df_original['day_index'],
                        y=lower_band,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'  # Disable hover
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_original['day_index'],
                        y=upper_band,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor=colors[max_stddev - i],
                        name=f'-{i}σ Regression Band' if i == 1 else None,
                        hoverinfo='skip',  # Disable hover
                        showlegend=i == 1
                    )
                )

    # Regression line and bands on df_original_truncated
    if 'regression_line' in df_original_truncated.columns:
        fig.add_trace(
            go.Scatter(
                x=df_original_truncated['day_index'],
                y=df_original_truncated['regression_line'],
                mode='lines',
                name='Regression Line (Truncated)',
                line=dict(color='green', dash='dash'),
                hoverinfo='skip',  # Disable hover
            )
        )

        # Plot regression bands for truncated data
        if plot_bands and 'regression_upper_band_1' in df_original_truncated.columns:
            max_stddev = 4  # Changed to 4
            # Ensure colors list has 4 colors
            colors = [
                'rgba(0, 128, 0, 0.15)',  # Green, alpha=0.15
                'rgba(0, 128, 0, 0.1)',   # Green, alpha=0.1
                'rgba(0, 128, 0, 0.07)',  # Green, alpha=0.07
                'rgba(0, 128, 0, 0.04)'   # Green, alpha=0.04
            ]

            # Upper bands for truncated data
            for i in range(max_stddev, 0, -1):
                upper_band = df_original_truncated[f'regression_upper_band_{i}']
                lower_band = df_original_truncated[f'regression_upper_band_{i - 1}'] if i > 1 else df_original_truncated['regression_line']

                fig.add_trace(
                    go.Scatter(
                        x=df_original_truncated['day_index'],
                        y=upper_band,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'  # Disable hover
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_original_truncated['day_index'],
                        y=lower_band,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor=colors[max_stddev - i],
                        name=f'+{i}σ Regression Band (Truncated)' if i == 1 else None,
                        hoverinfo='skip',  # Disable hover
                        showlegend=i == 1
                    )
                )

            # Lower bands for truncated data
            for i in range(max_stddev, 0, -1):
                lower_band = df_original_truncated[f'regression_lower_band_{i}']
                upper_band = df_original_truncated[f'regression_lower_band_{i - 1}'] if i > 1 else df_original_truncated['regression_line']

                fig.add_trace(
                    go.Scatter(
                        x=df_original_truncated['day_index'],
                        y=lower_band,
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'  # Disable hover
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_original_truncated['day_index'],
                        y=upper_band,
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor=colors[max_stddev - i],
                        name=f'-{i}σ Regression Band (Truncated)' if i == 1 else None,
                        hoverinfo='skip',  # Disable hover
                        showlegend=i == 1
                    )
                )

    # Plot cumulative percent change of the new period
    fig.add_trace(
        go.Scatter(
            x=df_new['day_index'],
            y=df_new['cumulative_pct_change'],
            mode='lines',
            name='New Period',
            hoverinfo='skip',  # Disable hover for this trace
            line=dict(color='red')
        )
    )

    # Add a separate trace for the latest price with hover info
    fig.add_trace(
        go.Scatter(
            x=[df_new['day_index'].iloc[-1]],
            y=[df_new['cumulative_pct_change'].iloc[-1]],
            mode='markers',
            name='Latest Price',
            hovertemplate=(
                f"<b>Date</b>: {latest_datetime}<br>"
                f"<b>Latest Price</b>: ${latest_price:.2f}"
            ),
            marker=dict(color='gold', size=10, symbol='star'),
            showlegend=False
        )
    )

    # Update the layout with the new title and disable default hover modes
    fig.update_layout(
        title=f"Cumulative Percent Change, Bollinger Bands, and Regression Bands for {symbol} | Date/Time: {latest_datetime} | Latest Price: ${latest_price:.2f}",
        xaxis_title="Aligned Days",
        yaxis_title="Cumulative % Change",
        template='simple_white',
        legend=dict(x=0, y=1),
        hovermode='closest',  # Ensures hover interactions are handled correctly
        xaxis=dict(
            showspikes=True,
            spikemode='across',
            spikesnap='cursor',
            showline=True,
            spikethickness=1,
            spikecolor="grey",
            spikedash='solid',
        ),
        yaxis=dict(
            showspikes=True,
            spikemode='across',
            spikesnap='cursor',
            showline=True,
            spikethickness=1,
            spikecolor="grey",
            spikedash='solid',
        )
    )

    # Calculate dynamic y-axis range with a buffer
    if 'regression_upper_band_1' in df_original_truncated.columns and 'regression_lower_band_1' in df_original_truncated.columns:
        max_y = max(df_new['cumulative_pct_change'].max(), df_original_truncated['regression_upper_band_1'].max())
        min_y = min(df_new['cumulative_pct_change'].min(), df_original_truncated['regression_lower_band_1'].min())
    else:
        max_y = df_new['cumulative_pct_change'].max()
        min_y = df_new['cumulative_pct_change'].min()

    # Add a buffer (20% of the y-range)
    y_range = max_y - min_y
    buffer = y_range * 0.2
    max_y += buffer
    min_y -= buffer

    # Apply y-axis range and update title for zoomed-in plot
    fig.update_layout(
        yaxis=dict(range=[min_y, max_y]),
        title=f"Cumulative Percent Change for {symbol} | Date/Time: {latest_datetime} | Latest Price: ${latest_price:.2f}",
        xaxis=dict(
            range=[df_new['day_index'].min(), df_new['day_index'].max()],
        ),
    )

    # Save the zoomed-in plot as JPEG
    zoomed_file_jpeg = output_dir / f"{symbol}_zoomed_{source}.jpeg"
    try:
        fig.write_image(str(zoomed_file_jpeg), format='jpeg', width=1600, height=1000)
        logging.info(f"Zoomed-in plot saved as JPEG to {zoomed_file_jpeg}")
    except Exception as e:
        logging.error(f"Failed to save zoomed-in plot as JPEG: {e}")

    # Save the plot as an HTML file
    html_file = output_dir / f"{symbol}_{source}.html"
    try:
        fig.write_html(str(html_file))
        logging.info(f"Plot saved as HTML to {html_file}")
    except Exception as e:
        logging.error(f"Failed to save plot as HTML: {e}")

    return zoomed_file_jpeg, html_file  # Return both paths

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
                                                   sma_window, source, plot_bands, plot_bollinger_bands)

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

                        # Build professional HTML email content
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
