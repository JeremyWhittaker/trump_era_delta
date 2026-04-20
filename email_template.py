"""
Professional HTML email template builder for Compare Timeframes alerts.
Hedge fund-grade styling with executive summary and methodology explanation.
"""
from typing import Dict, Optional, Tuple


# Hedge Fund Color Palette
COLORS = {
    'navy': '#1a2332',
    'charcoal': '#2d3748',
    'slate': '#4a5568',
    'silver': '#a0aec0',
    'light_gray': '#e2e8f0',
    'off_white': '#f7fafc',
    'gold': '#d4af37',
    'gold_muted': '#b8960c',
    'positive': '#2d6a4f',      # Muted forest green
    'positive_light': '#d8f3dc',
    'negative': '#9b2c2c',      # Muted burgundy
    'negative_light': '#fed7d7',
    'neutral': '#718096',
    'accent_blue': '#2c5282',
}


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert hex color to rgba() for email client compatibility."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def get_band_color(band: int) -> Tuple[str, str]:
    """Get color scheme for a regression band. Returns (bg_color, text_color)."""
    if band >= 3:
        return COLORS['positive'], "#ffffff"
    elif band >= 1:
        return COLORS['positive'], "#ffffff"
    elif band == 0:
        return COLORS['neutral'], "#ffffff"
    elif band >= -2:
        return COLORS['gold_muted'], "#ffffff"
    else:
        return COLORS['negative'], "#ffffff"


def format_band_label(band: int) -> str:
    """Format a band number into a readable label."""
    if band == 0:
        return "Mean"
    elif band > 0:
        return f"+{band}σ"
    else:
        return f"{band}σ"


def get_band_interpretation(band: int) -> str:
    """Get interpretation text for a band level."""
    if band >= 3:
        return "Significantly outperforming historical pattern"
    elif band >= 2:
        return "Notably above historical trend"
    elif band >= 1:
        return "Moderately above historical average"
    elif band == 0:
        return "Tracking historical average"
    elif band >= -1:
        return "Moderately below historical average"
    elif band >= -2:
        return "Notably below historical trend"
    else:
        return "Significantly underperforming historical pattern"


def build_band_ladder_html(bands: Dict[str, float], current_pct: float, current_band: int) -> str:
    """Build the band ladder table with hedge fund styling."""
    band_order = ['+4σ', '+3σ', '+2σ', '+1σ', 'avg', '-1σ', '-2σ', '-3σ', '-4σ']

    rows = []
    current_inserted = False

    for i, label in enumerate(band_order):
        value = bands.get(label, 0)

        # Determine if this is the current band
        is_current = False
        if label == 'avg' and current_band == 0:
            is_current = True
        elif label.startswith('+') and label != 'avg':
            band_num = int(label[1])
            is_current = (current_band == band_num)
        elif label.startswith('-'):
            band_num = -int(label[1])
            is_current = (current_band == band_num)

        # Style based on position
        if label in ['+4σ', '+3σ']:
            label_color = COLORS['positive']
        elif label in ['+2σ', '+1σ']:
            label_color = COLORS['positive']
        elif label == 'avg':
            label_color = COLORS['slate']
        elif label in ['-1σ', '-2σ']:
            label_color = COLORS['gold_muted']
        else:
            label_color = COLORS['negative']

        row_bg = hex_to_rgba(COLORS['gold'], 0.08) if is_current else 'transparent'
        font_weight = '600' if is_current else '400'

        rows.append(f'''
            <tr style="background-color: {row_bg};">
                <td style="padding: 10px 16px; border-bottom: 1px solid {COLORS['light_gray']}; color: {label_color}; font-weight: {font_weight};">{label}</td>
                <td style="padding: 10px 16px; border-bottom: 1px solid {COLORS['light_gray']}; text-align: right; font-family: 'SF Mono', Consolas, monospace; color: {COLORS['charcoal']}; font-weight: {font_weight};">{value*100:.2f}%</td>
            </tr>
        ''')

        # Insert current value marker
        if not current_inserted and i < len(band_order) - 1:
            next_label = band_order[i + 1]
            next_value = bands.get(next_label, 0)
            if value >= current_pct > next_value:
                rows.append(f'''
                    <tr style="background-color: {hex_to_rgba(COLORS['gold'], 0.15)};">
                        <td style="padding: 10px 16px; border-bottom: 1px solid {COLORS['light_gray']}; font-weight: 700; color: {COLORS['gold_muted']};">► CURRENT</td>
                        <td style="padding: 10px 16px; border-bottom: 1px solid {COLORS['light_gray']}; text-align: right; font-family: 'SF Mono', Consolas, monospace; font-weight: 700; color: {COLORS['navy']};">{current_pct*100:.2f}%</td>
                    </tr>
                ''')
                current_inserted = True

    # Handle edge cases
    if not current_inserted:
        marker_row = f'''
            <tr style="background-color: {hex_to_rgba(COLORS['gold'], 0.15)};">
                <td style="padding: 10px 16px; border-bottom: 1px solid {COLORS['light_gray']}; font-weight: 700; color: {COLORS['gold_muted']};">► CURRENT</td>
                <td style="padding: 10px 16px; border-bottom: 1px solid {COLORS['light_gray']}; text-align: right; font-family: 'SF Mono', Consolas, monospace; font-weight: 700; color: {COLORS['navy']};">{current_pct*100:.2f}%</td>
            </tr>
        '''
        if current_pct > bands.get('+4σ', 0):
            rows.insert(0, marker_row)
        else:
            rows.append(marker_row)

    return ''.join(rows)


def calculate_distance_to_next_band(current_pct: float, bands: Dict[str, float], current_band: int) -> Tuple[str, float]:
    """Calculate distance to next band threshold."""
    if current_band >= 0:
        next_band = current_band + 1
        if next_band <= 4:
            target_key = f'+{next_band}σ'
            target_value = bands.get(target_key, 0)
            return f"+{next_band}σ", target_value - current_pct
        return "ceiling", 0
    else:
        next_band = current_band - 1
        if next_band >= -4:
            target_key = f'{next_band}σ'
            target_value = bands.get(target_key, 0)
            return f"{next_band}σ", current_pct - target_value
        return "floor", 0


def build_email_content(
    symbol: str,
    source: str,
    timestamp_utc: str,
    latest_price: float,
    previous_band: int,
    current_band: int,
    current_pct: float,
    regression_line: float,
    bands: Dict[str, float],
    days_original: int,
    days_new: int,
    sma_window: int,
    check_frequency: int,
    reference_period_name: str = "Trump First Term",
    reference_start: str = "Nov 2016",
    reference_end: str = "Nov 2020",
    current_period_name: str = "Current Period",
    current_start: str = "Nov 2024",
    html_link: Optional[str] = None
) -> Tuple[str, str]:
    """
    Build professional hedge fund-style HTML email with methodology explanation.
    """
    # Determine direction and styling
    band_change = current_band - previous_band
    if band_change > 0:
        direction_text = "UPGRADED"
        direction_color = COLORS['positive']
        alert_bg = COLORS['positive_light']
    elif band_change < 0:
        direction_text = "DOWNGRADED"
        direction_color = COLORS['negative']
        alert_bg = COLORS['negative_light']
    else:
        direction_text = "UNCHANGED"
        direction_color = COLORS['neutral']
        alert_bg = COLORS['light_gray']

    prev_label = format_band_label(previous_band)
    curr_label = format_band_label(current_band)
    interpretation = get_band_interpretation(current_band)

    # Calculate distance to next band
    next_band_label, distance = calculate_distance_to_next_band(current_pct, bands, current_band)

    # Build band ladder
    band_ladder_html = build_band_ladder_html(bands, current_pct, current_band)

    html_body = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Regime Analysis - {symbol}</title>
</head>
<body style="margin: 0; padding: 0; background-color: {COLORS['light_gray']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">

    <!-- Container -->
    <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff;">

        <!-- Header -->
        <div style="background: linear-gradient(135deg, {COLORS['navy']} 0%, {COLORS['charcoal']} 100%); padding: 32px 24px; text-align: center;">
            <h1 style="margin: 0 0 8px; font-size: 13px; font-weight: 500; letter-spacing: 2px; text-transform: uppercase; color: {COLORS['gold']};">
                Quantitative Market Analysis
            </h1>
            <h2 style="margin: 0; font-size: 28px; font-weight: 300; color: #ffffff; letter-spacing: -0.5px;">
                {symbol} Regime Signal
            </h2>
            <p style="margin: 12px 0 0; font-size: 13px; color: {COLORS['silver']};">
                {timestamp_utc} · {source.upper()} Data Feed
            </p>
        </div>

        <!-- Alert Banner -->
        <div style="background-color: {alert_bg}; border-left: 4px solid {direction_color}; padding: 20px 24px; margin: 0;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div>
                    <span style="font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {direction_color};">{direction_text}</span>
                    <div style="font-size: 18px; font-weight: 500; color: {COLORS['navy']}; margin-top: 4px;">
                        {prev_label} → <span style="color: {direction_color}; font-weight: 700;">{curr_label}</span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 11px; color: {COLORS['slate']}; text-transform: uppercase; letter-spacing: 0.5px;">Latest Price</div>
                    <div style="font-size: 24px; font-weight: 600; color: {COLORS['navy']};">${latest_price:.2f}</div>
                </div>
            </div>
        </div>

        <!-- Executive Summary -->
        <div style="padding: 24px; border-bottom: 1px solid {COLORS['light_gray']};">
            <h3 style="margin: 0 0 16px; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {COLORS['gold_muted']};">
                Executive Summary
            </h3>
            <p style="margin: 0 0 12px; font-size: 15px; line-height: 1.6; color: {COLORS['charcoal']};">
                <strong>{symbol}</strong> is currently trading at the <strong style="color: {direction_color};">{curr_label}</strong> level
                relative to its historical performance pattern from the <strong>{reference_period_name}</strong> ({reference_start} – {reference_end}).
            </p>
            <p style="margin: 0; font-size: 14px; line-height: 1.6; color: {COLORS['slate']};">
                <em>{interpretation}</em>
            </p>
        </div>

        <!-- What This Analysis Shows -->
        <div style="padding: 24px; background-color: {COLORS['off_white']}; border-bottom: 1px solid {COLORS['light_gray']};">
            <h3 style="margin: 0 0 16px; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {COLORS['gold_muted']};">
                What This Analysis Measures
            </h3>
            <p style="margin: 0 0 12px; font-size: 14px; line-height: 1.7; color: {COLORS['charcoal']};">
                This model compares the <strong>cumulative percentage change</strong> of {symbol} during two time periods:
            </p>
            <table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
                <tr>
                    <td style="padding: 12px 16px; background-color: #ffffff; border: 1px solid {COLORS['light_gray']}; border-radius: 4px 0 0 4px;">
                        <div style="font-size: 11px; color: {COLORS['slate']}; text-transform: uppercase; letter-spacing: 0.5px;">Reference Period</div>
                        <div style="font-size: 15px; font-weight: 600; color: {COLORS['navy']}; margin-top: 4px;">{reference_period_name}</div>
                        <div style="font-size: 13px; color: {COLORS['slate']}; margin-top: 2px;">{reference_start} – {reference_end}</div>
                        <div style="font-size: 12px; color: {COLORS['silver']}; margin-top: 4px;">{days_original} trading days</div>
                    </td>
                    <td style="padding: 12px 16px; background-color: #ffffff; border: 1px solid {COLORS['light_gray']}; border-left: none; border-radius: 0 4px 4px 0;">
                        <div style="font-size: 11px; color: {COLORS['slate']}; text-transform: uppercase; letter-spacing: 0.5px;">Current Period</div>
                        <div style="font-size: 15px; font-weight: 600; color: {COLORS['navy']}; margin-top: 4px;">{current_period_name}</div>
                        <div style="font-size: 13px; color: {COLORS['slate']}; margin-top: 2px;">{current_start} – Present</div>
                        <div style="font-size: 12px; color: {COLORS['silver']}; margin-top: 4px;">{days_new} trading days elapsed</div>
                    </td>
                </tr>
            </table>
            <p style="margin: 0; font-size: 13px; line-height: 1.6; color: {COLORS['slate']};">
                A <strong>linear regression</strong> is fitted to the reference period's cumulative returns, establishing
                the historical trend. Standard deviation bands (±1σ to ±4σ) define zones of normal vs. abnormal deviation.
                The current period's performance is then measured against these bands day-by-day.
            </p>
        </div>

        <!-- Band Ladder -->
        <div style="padding: 24px; border-bottom: 1px solid {COLORS['light_gray']};">
            <h3 style="margin: 0 0 4px; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {COLORS['gold_muted']};">
                Statistical Band Position
            </h3>
            <p style="margin: 0 0 16px; font-size: 13px; color: {COLORS['slate']};">
                Current position relative to historical standard deviation bands
            </p>
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <thead>
                    <tr style="background-color: {COLORS['navy']};">
                        <th style="padding: 12px 16px; text-align: left; font-weight: 500; color: #ffffff; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Band</th>
                        <th style="padding: 12px 16px; text-align: right; font-weight: 500; color: #ffffff; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">Threshold</th>
                    </tr>
                </thead>
                <tbody>
                    {band_ladder_html}
                </tbody>
            </table>
        </div>

        <!-- Zoomed Chart (Current Period Focus) -->
        <div style="padding: 24px; border-bottom: 1px solid {COLORS['light_gray']};">
            <h3 style="margin: 0 0 4px; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {COLORS['gold_muted']};">
                Current Period Detail
            </h3>
            <p style="margin: 0 0 16px; font-size: 13px; color: {COLORS['slate']};">
                Zoomed view: Day 0 to present ({days_new} trading days)
            </p>
            <div style="background-color: {COLORS['off_white']}; padding: 12px; border-radius: 4px; text-align: center;">
                <img src="cid:chart_zoomed" alt="Zoomed regression band analysis - current period" style="max-width: 100%; border-radius: 4px;"/>
            </div>
        </div>

        <!-- Full Term Chart -->
        <div style="padding: 24px; border-bottom: 1px solid {COLORS['light_gray']};">
            <h3 style="margin: 0 0 4px; font-size: 12px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {COLORS['gold_muted']};">
                Full Reference Period Context
            </h3>
            <p style="margin: 0 0 16px; font-size: 13px; color: {COLORS['slate']};">
                Complete {reference_period_name} ({days_original} trading days) with current overlay
            </p>
            <div style="background-color: {COLORS['off_white']}; padding: 12px; border-radius: 4px; text-align: center;">
                <img src="cid:chart_full" alt="Full term regression band analysis - complete reference period" style="max-width: 100%; border-radius: 4px;"/>
            </div>
        </div>

        <!-- Methodology Note -->
        <div style="padding: 24px; background-color: {COLORS['off_white']};">
            <h3 style="margin: 0 0 12px; font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: {COLORS['slate']};">
                Methodology Note
            </h3>
            <p style="margin: 0; font-size: 12px; line-height: 1.6; color: {COLORS['slate']};">
                This analysis uses ordinary least squares (OLS) regression on cumulative daily returns.
                Standard deviation bands are calculated from residuals around the trend line.
                Alerts trigger when the current period crosses from one σ-band to another.
                This is a <strong>descriptive tool</strong>, not a predictive model or trading signal.
            </p>
        </div>

        <!-- Footer -->
        <div style="background-color: {COLORS['navy']}; padding: 20px 24px; text-align: center;">
            <p style="margin: 0 0 8px; font-size: 12px; color: {COLORS['silver']};">
                Next analysis update in {check_frequency} minutes
                {f' · <a href="{html_link}" style="color: {COLORS["gold"]};">View Interactive Chart</a>' if html_link else ''}
            </p>
            <p style="margin: 0; font-size: 11px; color: {COLORS['slate']};">
                Compare Timeframes Analysis System · Automated Alert
            </p>
        </div>

    </div>
</body>
</html>'''

    # Plain text fallback
    text_body = f"""
================================================================================
QUANTITATIVE MARKET ANALYSIS: {symbol} REGIME SIGNAL
================================================================================

{direction_text}: {prev_label} → {curr_label}
Generated: {timestamp_utc}

EXECUTIVE SUMMARY
-----------------
{symbol} is currently trading at the {curr_label} level relative to its
historical performance pattern from the {reference_period_name} ({reference_start} – {reference_end}).

Assessment: {interpretation}

WHAT THIS ANALYSIS MEASURES
---------------------------
This model compares the cumulative percentage change of {symbol} during two periods:

  Reference Period: {reference_period_name}
    - Timeframe: {reference_start} – {reference_end}
    - Duration: {days_original} trading days

  Current Period: {current_period_name}
    - Start: {current_start}
    - Elapsed: {days_new} trading days

A linear regression is fitted to the reference period's cumulative returns,
establishing the historical trend. Standard deviation bands (±1σ to ±4σ)
define zones of normal vs. abnormal deviation.

STATISTICAL BANDS
-----------------
  +4σ:  {bands.get('+4σ', 0)*100:+.2f}%
  +3σ:  {bands.get('+3σ', 0)*100:+.2f}%
  +2σ:  {bands.get('+2σ', 0)*100:+.2f}%
  +1σ:  {bands.get('+1σ', 0)*100:+.2f}%
  avg:  {bands.get('avg', 0)*100:+.2f}%
  -1σ:  {bands.get('-1σ', 0)*100:+.2f}%
  -2σ:  {bands.get('-2σ', 0)*100:+.2f}%
  -3σ:  {bands.get('-3σ', 0)*100:+.2f}%
  -4σ:  {bands.get('-4σ', 0)*100:+.2f}%

  ► CURRENT: {current_pct*100:+.2f}%

{f'Interactive Chart: {html_link}' if html_link else ''}

--------------------------------------------------------------------------------
Compare Timeframes Analysis System · Next update in {check_frequency} minutes
This is a descriptive tool, not a predictive model or trading signal.
"""

    return html_body, text_body
