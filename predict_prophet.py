import argparse
import logging
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from prophet import Prophet

from analysis_core import load_price_history, prepare_aligned_period, slice_period
from service_bootstrap import load_asset_prices_reader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

ASSET_PRICES_REPO = Path(os.getenv("ASSET_PRICES_REPO", "/home/shared/algos/asset_prices"))
ASSET_PRICES_DATA_DIR = Path(os.getenv("ASSET_PRICES_DATA_DIR", ASSET_PRICES_REPO / "data"))
DEFAULT_DATA_TYPE = os.getenv("ASSET_PRICES_DATA_TYPE", "adjusted")


def calculate_daily_pct_change(df, start_date, end_date):
    """Calculate daily percent change for a given date range."""
    df_filtered = slice_period(df, start_date, end_date)
    df_filtered["daily_pct_change"] = df_filtered["adj_close"].pct_change().fillna(0) * 100
    logging.info("Prepared daily percent change frame for forecast input.")
    logging.info(f"Columns: {list(df_filtered.columns)}")
    return df_filtered


def prepare_prophet_data(df):
    """Prepare daily percent change data for Prophet model."""
    logging.info("Preparing daily percent change data for Prophet.")
    try:
        df_prophet = df[["index", "daily_pct_change"]].rename(
            columns={"index": "ds", "daily_pct_change": "y"}
        )
    except KeyError as exc:
        logging.error(f"Error in selecting columns: {exc}")
        logging.info(f"Available columns: {list(df.columns)}")
        raise

    df_prophet["ds"] = pd.to_datetime(df_prophet["ds"])
    df_prophet["ds"] = df_prophet["ds"].dt.tz_localize(None)
    return df_prophet


def predict_for_new_period(df_old, new_start, new_end):
    """Fit Prophet on the aligned reference period and predict the new-period dates."""
    df_old_prophet = prepare_prophet_data(df_old.copy())

    model = Prophet()
    model.fit(df_old_prophet)
    logging.info("Prophet model fitted on daily percent change data.")

    future_dates = pd.date_range(start=new_start, end=new_end)
    future = pd.DataFrame({"ds": future_dates})
    forecast = model.predict(future)
    forecast["cumulative_pct_change"] = forecast["yhat"].cumsum()
    forecast["ds"] = forecast["ds"].dt.strftime("%Y-%m-%d")
    return forecast[["ds", "cumulative_pct_change"]]


def plot_comparison(symbol, df_old, df_new, forecast, output_dir):
    """Plot aligned historical data, current data, and the forecast overlay."""
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=False,
        subplot_titles=(
            "Original Period Cumulative Percent Change (Aligned Days)",
            "New Period Cumulative Percent Change (Actual Date)",
            "New Period Cumulative Percent Change with Forecast (Actual Date)",
        ),
    )

    fig.add_trace(
        go.Scatter(
            x=df_old["day_index"],
            y=df_old["cumulative_pct_change"],
            mode="lines",
            name="Original Period",
            hovertemplate="<b>Aligned Day</b>: %{x}<br><b>Cumulative % Change</b>: %{y:.2f}%",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df_new["index"],
            y=df_new["cumulative_pct_change"],
            mode="lines",
            name="New Period (Actual)",
            hovertemplate="<b>Date</b>: %{x}<br><b>Cumulative % Change</b>: %{y:.2f}%",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df_new["index"],
            y=df_new["cumulative_pct_change"],
            mode="lines",
            name="New Period (Actual)",
            hovertemplate="<b>Date</b>: %{x}<br><b>Cumulative % Change</b>: %{y:.2f}%",
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=forecast["ds"],
            y=forecast["cumulative_pct_change"],
            mode="lines",
            name="New Period (Forecast)",
            line={"color": "orange", "dash": "dot"},
            hovertemplate="<b>Date</b>: %{x}<br><b>Forecasted % Change</b>: %{y:.2f}%",
        ),
        row=3,
        col=1,
    )

    fig.update_layout(
        title=f"Cumulative Percent Change Comparison for {symbol}",
        xaxis={"title": "Aligned Days (Original Period)", "matches": "x3"},
        xaxis2={"title": "Date (New Period)", "matches": "x3"},
        xaxis3={"title": "Date (Forecast)", "title_standoff": 15},
        yaxis_title="Cumulative % Change",
        height=900,
        template="plotly_white",
    )

    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{symbol}_comparison.html"
    fig.write_html(output_file)
    logging.info(f"Plot saved to {output_file}")


def main(symbol, source, original_start, original_end, new_start, new_end):
    reader_callable, reader_error = load_asset_prices_reader(ASSET_PRICES_REPO)
    if reader_error:
        raise ImportError(reader_error)

    earliest_start = min(pd.to_datetime(original_start), pd.to_datetime(new_start)).strftime(
        "%Y-%m-%d"
    )
    parsed_end = pd.to_datetime(new_end) if new_end else None
    end_date = parsed_end.strftime("%Y-%m-%d") if parsed_end is not None else None

    df = load_price_history(
        symbol,
        source,
        start_date=earliest_start,
        end_date=end_date,
        data_type=DEFAULT_DATA_TYPE,
        data_dir=ASSET_PRICES_DATA_DIR,
        read_symbol_data_fn=reader_callable,
    )
    df_old = prepare_aligned_period(df, original_start, original_end)
    df_new = calculate_daily_pct_change(df, new_start, new_end)
    df_new["cumulative_pct_change"] = df_new["daily_pct_change"].cumsum()

    forecast = predict_for_new_period(df_old, new_start, new_end)

    output_dir = Path("./plots")
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_comparison(symbol, df_old, df_new, forecast, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Forecast cumulative percent change with Prophet."
    )
    parser.add_argument("--symbol", type=str, required=True, help="The asset symbol to analyze.")
    parser.add_argument(
        "--source",
        type=str,
        choices=["yfinance", "alpaca"],
        required=True,
        help="Data source to use (yfinance or alpaca).",
    )
    parser.add_argument(
        "--original_start",
        type=str,
        required=True,
        help="Start date for the original period (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--original_end",
        type=str,
        required=True,
        help="End date for the original period (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--new_start",
        type=str,
        required=True,
        help="Start date for the new period (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--new_end",
        type=str,
        required=True,
        help="End date for the new period (YYYY-MM-DD).",
    )
    args = parser.parse_args()

    main(
        symbol=args.symbol,
        source=args.source,
        original_start=args.original_start,
        original_end=args.original_end,
        new_start=args.new_start,
        new_end=args.new_end,
    )
