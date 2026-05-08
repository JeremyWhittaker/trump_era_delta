import logging
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from analysis_core import get_regression_band

go = None


def _load_plot_dependencies():
    global go

    if go is None:
        import plotly.graph_objects as go_module

        go = go_module

    return go


def plot_comparison(
    symbol,
    df_original,
    df_original_truncated,
    df_new,
    output_dir,
    sma_window,
    source,
    plot_bands=False,
    plot_bollinger_bands=False,
    original_start="2016-11-08",
    original_end="2020-11-03",
    new_start="2024-11-05",
    data_freshness=None,
):
    """Render comparison charts and the interactive HTML report."""
    go_module = _load_plot_dependencies()
    data_freshness = data_freshness or {}

    output_dir = Path(output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    if df_new.empty:
        logging.warning(
            f"No new period data available for plotting for {symbol}. Skipping plot."
        )
        return None, None, None

    df_original = df_original.copy()
    df_original_truncated = df_original_truncated.copy()
    df_new = df_new.copy()

    df_original["hover_date"] = df_original["index"].dt.strftime("%Y-%m-%d")
    df_original["hover_price"] = df_original["adj_close"]
    df_original_truncated["hover_date"] = df_original_truncated["index"].dt.strftime(
        "%Y-%m-%d"
    )
    df_original_truncated["hover_price"] = df_original_truncated["adj_close"]
    df_new["hover_date"] = df_new["index"].dt.strftime("%Y-%m-%d")
    df_new["hover_price"] = df_new["adj_close"]

    latest_price = df_new.iloc[-1]["adj_close"]
    latest_date = df_new.iloc[-1]["index"]
    latest_date_short = latest_date.strftime("%Y-%m-%d")
    latest_cum_pct = df_new.iloc[-1]["cumulative_pct_change"]
    freshness_warning = data_freshness.get("warning")
    freshness_status = "STALE" if freshness_warning else "OK"
    freshness_age_days = data_freshness.get("age_days")
    freshness_warning_html = escape(freshness_warning or "")
    freshness_detail = (
        f"{freshness_age_days} day(s) old"
        if freshness_age_days is not None
        else "checked"
    )

    current_band = None
    if "regression_line" in df_original_truncated.columns:
        current_band = get_regression_band(latest_cum_pct, df_original_truncated)

    colors = {
        "original_period": "#1e3a5f",
        "new_period": "#c0392b",
        "regression_full": "#2c3e50",
        "regression_truncated": "#27ae60",
        "band_amber": "rgba(212, 175, 55, {alpha})",
        "band_green": "rgba(39, 174, 96, {alpha})",
        "bollinger": "rgba(52, 152, 219, 0.2)",
        "latest_marker": "#f1c40f",
        "grid": "#ecf0f1",
        "text": "#2c3e50",
    }

    fig = go_module.Figure()

    if plot_bands and "regression_upper_band_1" in df_original.columns:
        band_alphas = [0.18, 0.14, 0.10, 0.06]
        for band_number in range(4, 0, -1):
            upper = df_original[f"regression_upper_band_{band_number}"]
            lower = (
                df_original[f"regression_upper_band_{band_number - 1}"]
                if band_number > 1
                else df_original["regression_line"]
            )
            fig.add_trace(
                go_module.Scatter(
                    x=df_original["day_index"],
                    y=upper,
                    mode="lines",
                    line={"width": 0},
                    showlegend=False,
                    hoverinfo="skip",
                    legendgroup="bands_original",
                )
            )
            fig.add_trace(
                go_module.Scatter(
                    x=df_original["day_index"],
                    y=lower,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor=colors["band_amber"].format(alpha=band_alphas[band_number - 1]),
                    name="Historical sigma Bands (Full Period)"
                    if band_number == 4
                    else None,
                    showlegend=(band_number == 4),
                    hoverinfo="skip",
                    legendgroup="bands_original",
                )
            )

        for band_number in range(4, 0, -1):
            lower = df_original[f"regression_lower_band_{band_number}"]
            upper = (
                df_original[f"regression_lower_band_{band_number - 1}"]
                if band_number > 1
                else df_original["regression_line"]
            )
            fig.add_trace(
                go_module.Scatter(
                    x=df_original["day_index"],
                    y=lower,
                    mode="lines",
                    line={"width": 0},
                    showlegend=False,
                    hoverinfo="skip",
                    legendgroup="bands_original",
                )
            )
            fig.add_trace(
                go_module.Scatter(
                    x=df_original["day_index"],
                    y=upper,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor=colors["band_amber"].format(alpha=band_alphas[band_number - 1]),
                    showlegend=False,
                    hoverinfo="skip",
                    legendgroup="bands_original",
                )
            )

    if plot_bands and "regression_upper_band_1" in df_original_truncated.columns:
        band_alphas = [0.30, 0.24, 0.18, 0.12]
        for band_number in range(4, 0, -1):
            upper = df_original_truncated[f"regression_upper_band_{band_number}"]
            lower = (
                df_original_truncated[f"regression_upper_band_{band_number - 1}"]
                if band_number > 1
                else df_original_truncated["regression_line"]
            )
            fig.add_trace(
                go_module.Scatter(
                    x=df_original_truncated["day_index"],
                    y=upper,
                    mode="lines",
                    line={"width": 0},
                    showlegend=False,
                    hoverinfo="skip",
                    legendgroup="bands_truncated",
                )
            )
            fig.add_trace(
                go_module.Scatter(
                    x=df_original_truncated["day_index"],
                    y=lower,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor=colors["band_green"].format(alpha=band_alphas[band_number - 1]),
                    name="Active sigma Bands (Matched Days)"
                    if band_number == 4
                    else None,
                    showlegend=(band_number == 4),
                    hoverinfo="skip",
                    legendgroup="bands_truncated",
                )
            )

        for band_number in range(4, 0, -1):
            lower = df_original_truncated[f"regression_lower_band_{band_number}"]
            upper = (
                df_original_truncated[f"regression_lower_band_{band_number - 1}"]
                if band_number > 1
                else df_original_truncated["regression_line"]
            )
            fig.add_trace(
                go_module.Scatter(
                    x=df_original_truncated["day_index"],
                    y=lower,
                    mode="lines",
                    line={"width": 0},
                    showlegend=False,
                    hoverinfo="skip",
                    legendgroup="bands_truncated",
                )
            )
            fig.add_trace(
                go_module.Scatter(
                    x=df_original_truncated["day_index"],
                    y=upper,
                    mode="lines",
                    line={"width": 0},
                    fill="tonexty",
                    fillcolor=colors["band_green"].format(alpha=band_alphas[band_number - 1]),
                    showlegend=False,
                    hoverinfo="skip",
                    legendgroup="bands_truncated",
                )
            )

    if plot_bollinger_bands and "upper_band" in df_original.columns:
        fig.add_trace(
            go_module.Scatter(
                x=df_original["day_index"],
                y=df_original["upper_band"],
                mode="lines",
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
                legendgroup="bollinger",
            )
        )
        fig.add_trace(
            go_module.Scatter(
                x=df_original["day_index"],
                y=df_original["lower_band"],
                mode="lines",
                line={"width": 0},
                fill="tonexty",
                fillcolor=colors["bollinger"],
                name=f"Bollinger Bands ({sma_window}d SMA)",
                legendgroup="bollinger",
                hoverinfo="skip",
            )
        )

    customdata_original = list(zip(df_original["hover_date"], df_original["hover_price"]))
    fig.add_trace(
        go_module.Scatter(
            x=df_original["day_index"],
            y=df_original["cumulative_pct_change"],
            mode="lines",
            name=f"Trump Term 1 ({original_start[:4]}-{original_end[:4]})",
            line={"color": colors["original_period"], "width": 2.5},
            customdata=customdata_original,
            hovertemplate=(
                "<b>Trump Term 1</b><br>"
                "Aligned Day: %{x}<br>"
                "Date: %{customdata[0]}<br>"
                "Price: $%{customdata[1]:.2f}<br>"
                "Cum. Return: %{y:.2%}<extra></extra>"
            ),
            legendgroup="original",
        )
    )

    if "regression_line" in df_original.columns:
        fig.add_trace(
            go_module.Scatter(
                x=df_original["day_index"],
                y=df_original["regression_line"],
                mode="lines",
                name="Regression (Full Period)",
                line={"color": colors["regression_full"], "width": 1.5, "dash": "dot"},
                hovertemplate="Regression (Full): %{y:.2%}<extra></extra>",
                legendgroup="regression_full",
            )
        )

    if "regression_line" in df_original_truncated.columns:
        fig.add_trace(
            go_module.Scatter(
                x=df_original_truncated["day_index"],
                y=df_original_truncated["regression_line"],
                mode="lines",
                name="Regression (Matched Days)",
                line={"color": colors["regression_truncated"], "width": 2, "dash": "dash"},
                hovertemplate="Regression (Matched): %{y:.2%}<extra></extra>",
                legendgroup="regression_truncated",
            )
        )

    customdata_new = list(zip(df_new["hover_date"], df_new["hover_price"]))
    fig.add_trace(
        go_module.Scatter(
            x=df_new["day_index"],
            y=df_new["cumulative_pct_change"],
            mode="lines",
            name=f"Trump Term 2 ({new_start[:4]}-Present)",
            line={"color": colors["new_period"], "width": 3},
            customdata=customdata_new,
            hovertemplate=(
                "<b>Trump Term 2 (Current)</b><br>"
                "Aligned Day: %{x}<br>"
                "Date: %{customdata[0]}<br>"
                "Price: $%{customdata[1]:.2f}<br>"
                "Cum. Return: %{y:.2%}<extra></extra>"
            ),
            legendgroup="new",
        )
    )

    band_label = (
        f"{'+' if current_band > 0 else ''}{current_band}σ"
        if current_band is not None
        else "N/A"
    )
    fig.add_trace(
        go_module.Scatter(
            x=[df_new["day_index"].iloc[-1]],
            y=[latest_cum_pct],
            mode="markers",
            name="Latest Value",
            marker={
                "color": colors["latest_marker"],
                "size": 14,
                "symbol": "star",
                "line": {"color": "#2c3e50", "width": 1.5},
            },
            hovertemplate=(
                f"<b>LATEST</b><br>Date: {latest_date_short}<br>Price: ${latest_price:.2f}<br>"
                f"Cum. Return: {latest_cum_pct:.2%}<br>Band: {band_label}<extra></extra>"
            ),
            showlegend=True,
        )
    )

    num_days = len(df_new)
    tick_positions = [0, num_days // 4, num_days // 2, 3 * num_days // 4, num_days - 1]
    tick_positions = [position for position in tick_positions if position < len(df_new)]
    new_period_dates = [df_new.iloc[position]["hover_date"] for position in tick_positions]
    summary_annotation_text = (
        f"<b>Latest:</b> ${latest_price:.2f} ({latest_cum_pct:+.2%}) on {latest_date_short} | "
        f"<b>Band:</b> {band_label} | <b>Source:</b> {source.upper()}"
    )
    if freshness_warning:
        summary_annotation_text += f"<br><b>Data warning:</b> {freshness_warning_html}"

    fig.update_layout(
        title={
            "text": f"<b>{symbol}</b> | Cumulative Return Comparison vs Historical Regression Bands",
            "font": {"size": 18, "color": colors["text"], "family": "Arial"},
            "x": 0.5,
            "xanchor": "center",
        },
        annotations=[
            {
                "text": summary_annotation_text,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 1.08 if freshness_warning else 1.06,
                "showarrow": False,
                "font": {"size": 12, "color": colors["text"]},
                "xanchor": "center",
            }
        ],
        xaxis={
            "title": {"text": "Aligned Trading Days", "font": {"size": 12, "color": colors["text"]}},
            "showgrid": True,
            "gridcolor": colors["grid"],
            "showline": True,
            "linecolor": colors["text"],
            "showspikes": True,
            "spikemode": "across",
            "spikethickness": 1,
            "spikecolor": "#7f8c8d",
            "range": [0, num_days + num_days * 0.08],
        },
        xaxis2={
            "title": {
                "text": "Actual Dates (Trump Term 2)",
                "font": {"size": 11, "color": colors["new_period"]},
            },
            "overlaying": "x",
            "side": "bottom",
            "position": 0,
            "tickmode": "array",
            "tickvals": tick_positions,
            "ticktext": new_period_dates,
            "tickfont": {"size": 10, "color": colors["new_period"]},
            "showgrid": False,
            "anchor": "free",
        },
        yaxis={
            "title": {
                "text": "Cumulative % Change",
                "font": {"size": 12, "color": colors["text"]},
            },
            "tickformat": ".1%",
            "showgrid": True,
            "gridcolor": colors["grid"],
            "showline": True,
            "linecolor": colors["text"],
            "zeroline": True,
            "zerolinecolor": "#bdc3c7",
            "zerolinewidth": 1,
        },
        legend={
            "title": {"text": "", "font": {"size": 10}},
            "orientation": "h",
            "yanchor": "top",
            "y": -0.12,
            "xanchor": "center",
            "x": 0.5,
            "bgcolor": "rgba(255, 255, 255, 0.9)",
            "bordercolor": colors["grid"],
            "borderwidth": 1,
            "font": {"size": 9},
        },
        hovermode="x unified",
        hoverlabel={
            "bgcolor": "#f8f9fa",
            "font": {"color": colors["text"], "size": 11},
            "bordercolor": "#dee2e6",
        },
        template="plotly_white",
        font={"family": "Arial, sans-serif", "size": 12, "color": colors["text"]},
        margin={"l": 60, "r": 60, "t": 120 if freshness_warning else 100, "b": 120},
        plot_bgcolor="#ffffff",
        paper_bgcolor="#fafafa",
    )

    if "regression_upper_band_2" in df_original_truncated.columns:
        max_y = max(
            df_new["cumulative_pct_change"].max(),
            df_original_truncated["regression_upper_band_2"].max(),
        )
        min_y = min(
            df_new["cumulative_pct_change"].min(),
            df_original_truncated["regression_lower_band_2"].min(),
        )
    else:
        max_y = df_new["cumulative_pct_change"].max()
        min_y = df_new["cumulative_pct_change"].min()

    y_range = max_y - min_y
    buffer = y_range * 0.15
    fig.update_yaxes(range=[min_y - buffer, max_y + buffer])

    zoomed_file_jpeg = output_dir / f"{symbol}_zoomed_{source}.jpeg"
    try:
        fig.write_image(str(zoomed_file_jpeg), format="jpeg", width=1600, height=900, scale=2)
        logging.info(f"Zoomed-in plot saved as JPEG to {zoomed_file_jpeg}")
    except Exception as exc:
        logging.error(f"Failed to save zoomed-in plot as JPEG: {exc}")
        zoomed_file_jpeg = None

    full_term_fig = go_module.Figure(fig)
    full_num_days = len(df_original)
    full_term_fig.update_xaxes(range=[0, full_num_days + full_num_days * 0.05])

    if "regression_upper_band_3" in df_original.columns:
        full_max_y = max(
            df_original["cumulative_pct_change"].max(),
            df_original["regression_upper_band_3"].max(),
        )
        full_min_y = min(
            df_original["cumulative_pct_change"].min(),
            df_original["regression_lower_band_3"].min(),
        )
    else:
        full_max_y = df_original["cumulative_pct_change"].max()
        full_min_y = df_original["cumulative_pct_change"].min()

    full_y_range = full_max_y - full_min_y
    full_buffer = full_y_range * 0.1
    full_term_fig.update_yaxes(range=[full_min_y - full_buffer, full_max_y + full_buffer])
    full_term_fig.update_layout(
        title={
            "text": f"<b>{symbol}</b> | Full Reference Period ({original_start[:4]}-{original_end[:4]}) vs Current"
        }
    )

    full_file_jpeg = output_dir / f"{symbol}_full_{source}.jpeg"
    try:
        full_term_fig.write_image(str(full_file_jpeg), format="jpeg", width=1600, height=900, scale=2)
        logging.info(f"Full-term plot saved as JPEG to {full_file_jpeg}")
    except Exception as exc:
        logging.error(f"Failed to save full-term plot as JPEG: {exc}")
        full_file_jpeg = None

    freshness_banner = ""
    if freshness_warning:
        freshness_banner = f"""
            <div class="freshness-warning">
                <strong>Data warning:</strong> {freshness_warning_html}
            </div>
"""

    html_header = f"""<!DOCTYPE html>
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
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ text-align: center; padding: 30px 20px; color: white; }}
        .header h1 {{ font-size: 28px; font-weight: 300; margin-bottom: 8px; letter-spacing: -0.5px; }}
        .header .gold {{ color: #d4af37; }}
        .header .subtitle {{ font-size: 14px; color: #a0aec0; }}
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
        .info-item {{ display: flex; flex-direction: column; }}
        .info-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #718096;
            margin-bottom: 4px;
        }}
        .info-value {{ font-size: 18px; font-weight: 600; color: #2d3748; }}
        .info-value.price {{ color: #1a2332; }}
        .info-value.positive {{ color: #2d6a4f; }}
        .info-value.negative {{ color: #9b2c2c; }}
        .info-value.fresh {{ color: #2d6a4f; }}
        .info-value.stale {{ color: #9b2c2c; }}
        .freshness-warning {{
            padding: 14px 24px;
            background: #fff4e5;
            border-bottom: 1px solid #f1c27d;
            color: #7c3d00;
            font-size: 14px;
            line-height: 1.5;
        }}
        .chart-container {{ padding: 0; }}
        .legend-guide {{ padding: 20px 24px; background: #f7fafc; border-top: 1px solid #e2e8f0; }}
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
        .legend-item {{ display: flex; align-items: center; gap: 10px; font-size: 13px; color: #4a5568; }}
        .legend-color {{ width: 24px; height: 4px; border-radius: 2px; flex-shrink: 0; }}
        .legend-color.navy {{ background: #1e3a5f; }}
        .legend-color.red {{ background: #c0392b; width: 24px; height: 5px; }}
        .legend-color.green-dash {{
            background: repeating-linear-gradient(90deg, #27ae60 0px, #27ae60 6px, transparent 6px, transparent 10px);
        }}
        .legend-color.amber {{ background: rgba(212, 175, 55, 0.4); height: 12px; }}
        .legend-color.green-band {{ background: rgba(39, 174, 96, 0.3); height: 12px; }}
        .legend-color.gold-star {{ background: #f1c40f; width: 12px; height: 12px; border-radius: 50%; }}
        .methodology {{ padding: 20px 24px; background: #ffffff; border-top: 1px solid #e2e8f0; }}
        .methodology h3 {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #d4af37;
            margin-bottom: 10px;
        }}
        .methodology p {{ font-size: 13px; line-height: 1.7; color: #4a5568; margin-bottom: 10px; }}
        .methodology ul {{ font-size: 13px; color: #4a5568; margin-left: 20px; line-height: 1.8; }}
        .footer {{ text-align: center; padding: 20px; color: #718096; font-size: 12px; }}
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
                    <span class="info-label">Data Status</span>
                    <span class="info-value {'stale' if freshness_warning else 'fresh'}">{freshness_status}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Data Age</span>
                    <span class="info-value">{freshness_detail}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Data Source</span>
                    <span class="info-value">{source.upper()}</span>
                </div>
            </div>
{freshness_banner}

            <div class="chart-container">
"""

    html_footer = f"""
            </div>

            <div class="legend-guide">
                <h3>Chart Legend</h3>
                <div class="legend-grid">
                    <div class="legend-item">
                        <div class="legend-color red"></div>
                        <span><strong>Trump Term 2 (Current)</strong> - {new_start} to present</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color navy"></div>
                        <span><strong>Trump Term 1 (Reference)</strong> - {original_start} to {original_end}</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color green-dash"></div>
                        <span><strong>Regression Line</strong> - Expected trend based on matched days</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color green-band"></div>
                        <span><strong>Green Bands (±1σ to ±4σ)</strong> - Active comparison zone</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color amber"></div>
                        <span><strong>Amber Bands</strong> - Full historical period σ bands</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color gold-star"></div>
                        <span><strong>Gold Star</strong> - Latest data point</span>
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
                    <li><strong>Hover</strong> - See exact date, price, and cumulative return for any point</li>
                    <li><strong>Click legend items</strong> - Toggle series visibility on/off</li>
                    <li><strong>Drag to zoom</strong> - Select an area to zoom in</li>
                    <li><strong>Double-click</strong> - Reset zoom to full view</li>
                    <li><strong>Toolbar (top-right)</strong> - Download as PNG, pan, zoom, autoscale</li>
                </ul>
            </div>
        </div>

        <div class="footer">
            Compare Timeframes Analysis System - Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
            <br>This is a descriptive analytical tool, not investment advice or a trading signal.
        </div>
    </div>
</body>
</html>
"""

    chart_html = fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"{symbol}_regression_analysis",
                "height": 900,
                "width": 1600,
                "scale": 2,
            },
        },
    )

    html_file = output_dir / f"{symbol}_{source}.html"
    try:
        html_file.write_text(html_header + chart_html + html_footer, encoding="utf-8")
        logging.info(f"Interactive HTML saved to {html_file}")
    except Exception as exc:
        logging.error(f"Failed to save HTML: {exc}")
        html_file = None

    return zoomed_file_jpeg, full_file_jpeg, html_file


def build_band_snapshot(df_original_truncated, df_new):
    """Build the shared report summary payload for supported callers."""
    latest_cumulative_pct_change = df_new["cumulative_pct_change"].iloc[-1]
    reg_line = df_original_truncated["regression_line"].iloc[-1]

    return {
        "current_band": get_regression_band(latest_cumulative_pct_change, df_original_truncated),
        "current_pct": latest_cumulative_pct_change,
        "regression_line": reg_line,
        "bands": {
            "+4σ": df_original_truncated["regression_upper_band_4"].iloc[-1],
            "+3σ": df_original_truncated["regression_upper_band_3"].iloc[-1],
            "+2σ": df_original_truncated["regression_upper_band_2"].iloc[-1],
            "+1σ": df_original_truncated["regression_upper_band_1"].iloc[-1],
            "avg": reg_line,
            "-1σ": df_original_truncated["regression_lower_band_1"].iloc[-1],
            "-2σ": df_original_truncated["regression_lower_band_2"].iloc[-1],
            "-3σ": df_original_truncated["regression_lower_band_3"].iloc[-1],
            "-4σ": df_original_truncated["regression_lower_band_4"].iloc[-1],
        },
        "latest_price": df_new.iloc[-1]["adj_close"],
        "latest_date": df_new.iloc[-1]["index"],
    }


def generate_comparison_report(
    symbol,
    source,
    df_original,
    df_original_truncated,
    df_new,
    output_dir,
    sma_window,
    plot_bands=False,
    plot_bollinger_bands=False,
    original_start=None,
    original_end=None,
    new_start=None,
    data_freshness=None,
):
    """Generate report artifacts and the stable summary payload."""
    data_freshness = data_freshness or {}
    zoomed_jpeg_path, full_jpeg_path, html_path = plot_comparison(
        symbol,
        df_original,
        df_original_truncated,
        df_new,
        output_dir,
        sma_window,
        source,
        plot_bands=plot_bands,
        plot_bollinger_bands=plot_bollinger_bands,
        original_start=original_start or "2016-11-08",
        original_end=original_end or "2020-11-03",
        new_start=new_start or "2024-11-05",
        data_freshness=data_freshness,
    )

    report = build_band_snapshot(df_original_truncated, df_new)
    report.update(
        {
            "zoomed_jpeg_path": zoomed_jpeg_path,
            "full_jpeg_path": full_jpeg_path,
            "html_path": html_path,
            "data_freshness": data_freshness,
            "freshness_warning": data_freshness.get("warning"),
            "latest_data_age_days": data_freshness.get("age_days"),
            "max_data_age_days": data_freshness.get("max_age_days"),
            "freshness_checked_at": data_freshness.get("checked_at"),
        }
    )
    return report
