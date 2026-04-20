import logging
from pathlib import Path

pd = None
np = None


def _load_analysis_dependencies():
    global np, pd

    if pd is None:
        import pandas as pandas_module

        pd = pandas_module

    if np is None:
        import numpy as numpy_module

        np = numpy_module

    return pd, np


def load_price_history(
    symbol,
    source,
    start_date=None,
    end_date=None,
    data_type="adjusted",
    data_dir=None,
    read_symbol_data_fn=None,
):
    """Load price data using the configured asset_prices reader."""
    pd_module, _ = _load_analysis_dependencies()

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
        base_dir=Path(data_dir),
    )

    if df.empty:
        logging.warning(f"No data returned for {symbol} from {source} ({data_type}).")
        return df

    df = df.copy()

    if "timestamp" in df.columns:
        df.rename(columns={"timestamp": "index"}, inplace=True)
    elif pd_module.api.types.is_datetime64_any_dtype(df.index):
        index_name = df.index.name or "index"
        df = df.reset_index().rename(columns={index_name: "index"})
    else:
        datetime_cols = [
            column
            for column in df.columns
            if pd_module.api.types.is_datetime64_any_dtype(df[column])
        ]
        if datetime_cols:
            df.rename(columns={datetime_cols[0]: "index"}, inplace=True)
        else:
            raise ValueError("Dataset must have a datetime 'timestamp' column or index.")

    df["index"] = pd_module.to_datetime(df["index"], utc=True, errors="coerce")
    df = df.dropna(subset=["index"])

    if "adj_close" not in df.columns:
        if "Adj Close" in df.columns:
            df.rename(columns={"Adj Close": "adj_close"}, inplace=True)
        elif "close" in df.columns:
            df.rename(columns={"close": "adj_close"}, inplace=True)
        else:
            raise ValueError("Missing `adj_close` column in data.")

    df = df[["index", "adj_close"]].dropna(subset=["adj_close"])
    df = df.sort_values("index").reset_index(drop=True)

    if not df.empty:
        min_date = df["index"].min()
        max_date = df["index"].max()
        logging.info(
            f"Loaded {len(df)} rows for {symbol} from {source} ({data_type}) "
            f"via asset_prices at {data_dir} | range {min_date} -> {max_date}"
        )
    else:
        logging.warning(f"No data available for {symbol} after cleaning.")

    return df


def _coerce_timezone(timestamp, timezone_value):
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(timezone_value)
    return timestamp.tz_convert(timezone_value)


def slice_period(df, start_date, end_date):
    pd_module, _ = _load_analysis_dependencies()

    if df.empty:
        return df.copy()

    timezone_value = df["index"].dt.tz
    start_ts = pd_module.to_datetime(start_date) if start_date else df["index"].min()
    end_ts = pd_module.to_datetime(end_date) if end_date else df["index"].max()

    start_ts = _coerce_timezone(start_ts, timezone_value)
    end_ts = _coerce_timezone(end_ts, timezone_value)

    df_filtered = df.loc[df["index"].between(start_ts, end_ts)].copy()
    if df_filtered.empty:
        raise ValueError(
            f"No data available for the specified date range: {start_date} to {end_date}"
        )

    df_filtered.reset_index(drop=True, inplace=True)
    return df_filtered


def calculate_cumulative_pct_change(
    df,
    start_date,
    end_date,
    sma_window=None,
    plot_bollinger_bands=False,
):
    """Calculate cumulative percent change for the requested period."""
    df_filtered = slice_period(df, start_date, end_date)
    df_filtered["cumulative_pct_change"] = (
        df_filtered["adj_close"].pct_change().fillna(0).cumsum()
    )

    if sma_window and plot_bollinger_bands:
        df_filtered["sma"] = (
            df_filtered["cumulative_pct_change"].rolling(window=sma_window).mean()
        )
        df_filtered["stddev"] = (
            df_filtered["cumulative_pct_change"].rolling(window=sma_window).std()
        )
        df_filtered["upper_band"] = df_filtered["sma"] + (2 * df_filtered["stddev"])
        df_filtered["lower_band"] = df_filtered["sma"] - (2 * df_filtered["stddev"])

    return df_filtered


def calculate_regression_bands(df, max_stddev=4):
    """Calculate linear regression plus symmetric residual bands."""
    _, np_module = _load_analysis_dependencies()

    if df.empty:
        raise ValueError("DataFrame is empty. Cannot perform regression.")
    if "cumulative_pct_change" not in df.columns:
        raise ValueError(
            "DataFrame must contain 'cumulative_pct_change' column for regression analysis."
        )

    regression_df = df.copy()
    x = regression_df["day_index"].values
    y = regression_df["cumulative_pct_change"].values

    coef = np_module.polyfit(x, y, 1)
    regression_df["regression_line"] = coef[0] * x + coef[1]

    residuals = y - regression_df["regression_line"]
    residual_std = np_module.std(residuals)
    regression_df["residual_std"] = residual_std

    for band_number in range(1, max_stddev + 1):
        regression_df[f"regression_upper_band_{band_number}"] = (
            regression_df["regression_line"] + (band_number * residual_std)
        )
        regression_df[f"regression_lower_band_{band_number}"] = (
            regression_df["regression_line"] - (band_number * residual_std)
        )

    return regression_df


def get_regression_band(current_pct, df_truncated):
    """Classify the latest value against the explicit regression-band boundaries."""
    reg_line = df_truncated["regression_line"].iloc[-1]
    upper_1 = df_truncated["regression_upper_band_1"].iloc[-1]
    upper_2 = df_truncated["regression_upper_band_2"].iloc[-1]
    upper_3 = df_truncated["regression_upper_band_3"].iloc[-1]
    upper_4 = df_truncated["regression_upper_band_4"].iloc[-1]

    lower_1 = df_truncated["regression_lower_band_1"].iloc[-1]
    lower_2 = df_truncated["regression_lower_band_2"].iloc[-1]
    lower_3 = df_truncated["regression_lower_band_3"].iloc[-1]
    lower_4 = df_truncated["regression_lower_band_4"].iloc[-1]

    if current_pct > upper_4:
        return 4
    if current_pct > upper_3:
        return 3
    if current_pct > upper_2:
        return 2
    if current_pct > upper_1:
        return 1
    if current_pct > reg_line:
        return 0
    if current_pct > lower_1:
        return -1
    if current_pct > lower_2:
        return -2
    if current_pct > lower_3:
        return -3
    if current_pct > lower_4:
        return -4
    return -4


def prepare_analysis_frames(
    df,
    symbol,
    original_start,
    original_end,
    new_start,
    adjusted_new_end,
    sma_window,
    plot_bollinger_bands,
):
    adjusted_new_end_label = (
        adjusted_new_end.strftime("%Y-%m-%d")
        if hasattr(adjusted_new_end, "strftime")
        else str(adjusted_new_end)
    )

    df_original = calculate_cumulative_pct_change(
        df,
        original_start,
        original_end,
        sma_window=sma_window,
        plot_bollinger_bands=plot_bollinger_bands,
    )
    df_new = calculate_cumulative_pct_change(df, new_start, adjusted_new_end)

    if df_new.empty:
        raise ValueError(
            f"Current period produced no rows for {symbol} between {new_start} and "
            f"{adjusted_new_end_label}."
        )

    if len(df_original) < 2:
        raise ValueError(
            f"Reference period produced only {len(df_original)} row(s) for {symbol}; "
            "cannot compute regression bands."
        )

    df_original = df_original.copy()
    df_new = df_new.copy()
    df_original["day_index"] = range(len(df_original))
    df_new["day_index"] = range(len(df_new))
    df_original = calculate_regression_bands(df_original)

    num_days_new = len(df_new)
    df_original_truncated = df_original.iloc[:num_days_new].copy()
    df_original_truncated.reset_index(drop=True, inplace=True)
    df_original_truncated["day_index"] = range(len(df_original_truncated))

    if len(df_original_truncated) < 2:
        raise ValueError(
            f"Reference period produced only {len(df_original_truncated)} row(s) for {symbol}; "
            f"cannot compute regression bands for {num_days_new} current-day rows."
        )

    df_original_truncated = calculate_regression_bands(df_original_truncated)
    return df_original, df_new, df_original_truncated


def prepare_aligned_period(df, start_date, end_date):
    """Prepare a day-aligned percent-return frame for forecast workflows."""
    df_filtered = slice_period(df, start_date, end_date)
    daily_returns = df_filtered["adj_close"].pct_change().fillna(0)
    df_filtered["daily_pct_change"] = daily_returns * 100
    df_filtered["cumulative_pct_change"] = df_filtered["daily_pct_change"].cumsum()
    df_filtered["day_index"] = range(len(df_filtered))
    return df_filtered
