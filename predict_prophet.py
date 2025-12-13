import os
import pandas as pd
from prophet import Prophet
import plotly.graph_objects as go
from pathlib import Path
import argparse
import logging
from plotly.subplots import make_subplots

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


def load_data(symbol, source):
    """Loads data from the specified data source (yfinance or alpaca) for a given symbol."""
    data_dir = Path('/home/shared/algos/asset_prices/data') / source
    file_path = data_dir / f"{symbol}.parquet"

    if not file_path.exists():
        raise FileNotFoundError(f"Data file for {symbol} not found in {source} directory.")

    df = pd.read_parquet(file_path)
    logging.info(f"Loaded data for {symbol} from {source}. Data range: {df.index.min()} to {df.index.max()}")
    return df


def calculate_daily_pct_change(df, start_date, end_date):
    """Calculate daily percent change for a given date range."""
    df_filtered = df.loc[start_date:end_date].copy()
    if df_filtered.empty:
        raise ValueError(f"No data available for the specified date range: {start_date} to {end_date}")

    df_filtered['daily_pct_change'] = df_filtered['adj_close'].pct_change().fillna(0) * 100  # Daily percentage change
    df_filtered.reset_index(inplace=True)  # Ensure index is a column for Prophet
    logging.info("After calculating daily percent change and resetting index:")
    logging.info(f"Columns: {df_filtered.columns}")
    logging.info(f"First few rows:\n{df_filtered.head()}")
    return df_filtered


def prepare_prophet_data(df):
    """Prepare daily percent change data for Prophet model."""
    logging.info("Preparing daily percent change data for Prophet.")
    logging.info(f"Initial columns before preparation: {df.columns}")
    # Ensure columns are renamed correctly for Prophet
    try:
        df_prophet = df[['index', 'daily_pct_change']].rename(columns={'index': 'ds', 'daily_pct_change': 'y'})
    except KeyError as e:
        logging.error(f"Error in selecting columns: {e}")
        logging.info(f"Available columns: {df.columns}")
        raise

    df_prophet['ds'] = pd.to_datetime(df_prophet['ds'])  # Ensure ds is a datetime column
    df_prophet['ds'] = df_prophet['ds'].dt.tz_localize(None)  # Remove timezone if it exists
    logging.info(f"Prepared Prophet data columns: {df_prophet.columns}")
    logging.info(f"First few rows of Prophet input data:\n{df_prophet.head()}")
    return df_prophet


def predict_for_new_period(df_old, new_start, new_end):
    """Fit Prophet model on daily percent change of old period and predict for new period dates."""
    # Reset index in df_old to ensure the date is available as a column
    df_old = df_old.reset_index()
    logging.info("After resetting index on df_old:")
    logging.info(f"Columns: {df_old.columns}")
    logging.info(f"First few rows:\n{df_old.head()}")

    df_old_prophet = prepare_prophet_data(df_old)

    model = Prophet()
    model.fit(df_old_prophet)
    logging.info("Prophet model fitted on daily percent change data.")

    # Generate forecast for new period dates
    future_dates = pd.date_range(start=new_start, end=new_end)
    future = pd.DataFrame({'ds': future_dates})
    forecast = model.predict(future)

    # Cumulatively sum the forecasted daily percent changes to align with cumulative percent change
    forecast['cumulative_pct_change'] = forecast['yhat'].cumsum()
    forecast['ds'] = forecast['ds'].dt.strftime('%Y-%m-%d')
    logging.info(f"Forecast data columns: {forecast.columns}")
    logging.info(f"First few rows of forecast:\n{forecast.head()}")
    return forecast[['ds', 'cumulative_pct_change']]


def prepare_aligned_data(df, start_date, end_date):
    """Prepare data with day index starting from 0 for relative alignment."""
    df_filtered = df.loc[start_date:end_date].copy()
    if df_filtered.empty:
        raise ValueError(f"No data available for the specified date range: {start_date} to {end_date}")

    # Calculate cumulative percent change and add day index
    df_filtered['cumulative_pct_change'] = df_filtered['adj_close'].pct_change().fillna(0).cumsum() * 100
    df_filtered['daily_pct_change'] = df_filtered['adj_close'].pct_change().fillna(0) * 100  # Add daily percent change
    df_filtered['day_index'] = range(len(df_filtered))  # Align by relative days
    logging.info(
        f"Prepared aligned data with day index and daily percent change. First few rows:\n{df_filtered.head()}")
    return df_filtered


def plot_comparison(symbol, df_old, df_new, forecast, output_dir):
    """Plot three graphs: aligned original data, new period data by actual date, and forecast with actual new data."""

    # Create a figure with 3 rows for subplots
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=False,
        subplot_titles=(
            "Original Period Cumulative Percent Change (Aligned Days)",
            "New Period Cumulative Percent Change (Actual Date)",
            "New Period Cumulative Percent Change with Forecast (Actual Date)"
        )
    )

    # Plot 1: Original Period Cumulative Percent Change (Aligned Days)
    fig.add_trace(
        go.Scatter(
            x=df_old['day_index'],
            y=df_old['cumulative_pct_change'],
            mode='lines',
            name='Original Period',
            hovertemplate='<b>Aligned Day</b>: %{x}<br><b>Cumulative % Change</b>: %{y:.2f}%',
        ),
        row=1, col=1
    )

    # Plot 2: New Period Cumulative Percent Change (Actual Date)
    fig.add_trace(
        go.Scatter(
            x=df_new['index'],
            y=df_new['cumulative_pct_change'],
            mode='lines',
            name='New Period (Actual)',
            hovertemplate='<b>Date</b>: %{x}<br><b>Cumulative % Change</b>: %{y:.2f}%',
        ),
        row=2, col=1
    )

    # Plot 3: New Period Cumulative Percent Change with Forecast (Actual Date)
    fig.add_trace(
        go.Scatter(
            x=df_new['index'],
            y=df_new['cumulative_pct_change'],
            mode='lines',
            name='New Period (Actual)',
            hovertemplate='<b>Date</b>: %{x}<br><b>Cumulative % Change</b>: %{y:.2f}%',
        ),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=forecast['ds'],
            y=forecast['cumulative_pct_change'],
            mode='lines',
            name='New Period (Forecast)',
            line=dict(color='orange', dash='dot'),
            hovertemplate='<b>Date</b>: %{x}<br><b>Forecasted % Change</b>: %{y:.2f}%',
        ),
        row=3, col=1
    )

    # Update layout with synchronized x-axis for the actual date subplots
    fig.update_layout(
        title=f"Cumulative Percent Change Comparison for {symbol}",
        xaxis=dict(title="Aligned Days (Original Period)", matches='x3'),
        xaxis2=dict(title="Date (New Period)", matches='x3'),
        xaxis3=dict(title="Date (Forecast)", title_standoff=15),
        yaxis_title="Cumulative % Change",
        height=900,
        template='plotly_white'
    )

    # Save the plot as HTML with all three graphs
    output_file = output_dir / f"{symbol}_comparison.html"
    fig.write_html(output_file)
    logging.info(f"Plot saved to {output_file}")


def main(symbol, source, original_start, original_end, new_start, new_end):
    df = load_data(symbol, source)
    df_old = prepare_aligned_data(df, original_start, original_end)
    df_new = calculate_daily_pct_change(df, new_start, new_end)
    df_new['cumulative_pct_change'] = df_new['daily_pct_change'].cumsum()

    forecast = predict_for_new_period(df_old, new_start, new_end)

    output_dir = Path('./plots')
    output_dir.mkdir(parents=True, exist_ok=True)

    plot_comparison(symbol, df_old, df_new, forecast, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Forecast cumulative percent change with Prophet.")
    parser.add_argument('--symbol', type=str, required=True, help="The asset symbol to analyze.")
    parser.add_argument('--source', type=str, choices=['yfinance', 'alpaca'], required=True,
                        help="Data source to use (yfinance or alpaca).")
    parser.add_argument('--original_start', type=str, required=True,
                        help="Start date for the original period (YYYY-MM-DD).")
    parser.add_argument('--original_end', type=str, required=True,
                        help="End date for the original period (YYYY-MM-DD).")
    parser.add_argument('--new_start', type=str, required=True, help="Start date for the new period (YYYY-MM-DD).")
    parser.add_argument('--new_end', type=str, required=True, help="End date for the new period (YYYY-MM-DD).")
    args = parser.parse_args()

    main(
        symbol=args.symbol,
        source=args.source,
        original_start=args.original_start,
        original_end=args.original_end,
        new_start=args.new_start,
        new_end=args.new_end
    )
