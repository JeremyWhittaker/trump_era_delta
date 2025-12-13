"""
Professional HTML email template builder for Compare Timeframes alerts.
Styled after the AAII dashboard design with inline CSS for email compatibility.
"""
from typing import Dict, Optional, Tuple


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """
    Convert a hex color to rgba() format for email client compatibility.
    Many email clients (especially Outlook) don't support 8-digit hex colors.

    Args:
        hex_color: Hex color string like "#27ae60"
        alpha: Opacity value between 0.0 and 1.0

    Returns:
        rgba() string like "rgba(39, 174, 96, 0.12)"
    """
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def get_band_color(band: int) -> Tuple[str, str]:
    """
    Get color scheme for a regression band.
    Returns (background_color, text_color).
    """
    if band >= 3:
        return "#27ae60", "#ffffff"  # Strong positive - green
    elif band >= 1:
        return "#2ecc71", "#ffffff"  # Positive - light green
    elif band == 0:
        return "#95a5a6", "#ffffff"  # Neutral - gray
    elif band >= -2:
        return "#e67e22", "#ffffff"  # Negative - orange
    else:
        return "#e74c3c", "#ffffff"  # Strong negative - red


def format_band_label(band: int) -> str:
    """Format a band number into a readable label."""
    if band == 0:
        return "Regression Line"
    elif band > 0:
        return f"+{band}σ"
    else:
        return f"{band}σ"


def build_band_ladder_html(bands: Dict[str, float], current_pct: float, current_band: int) -> str:
    """
    Build the band ladder table HTML showing all sigma levels.

    Args:
        bands: Dict with keys like '+4σ', '+3σ', ..., 'avg', '-1σ', ..., '-4σ'
        current_pct: Current cumulative percent change value
        current_band: Current band level (-4 to +4)
    """
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

        # Highlight row if current band
        row_style = ""
        if is_current:
            bg_color, _ = get_band_color(current_band)
            row_style = f'background-color: {hex_to_rgba(bg_color, 0.12)};'

        rows.append(f'''
            <tr style="{row_style}">
                <td style="padding: 8px 12px; border-bottom: 1px solid #ecf0f1; font-weight: {'700' if is_current else '400'};">{label}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #ecf0f1; text-align: right; font-family: monospace;">{value:.4f}</td>
            </tr>
        ''')

        # Insert current value between appropriate bands
        if not current_inserted and i < len(band_order) - 1:
            next_label = band_order[i + 1]
            next_value = bands.get(next_label, 0)
            if value >= current_pct > next_value:
                current_row_bg = hex_to_rgba("#3498db", 0.12)
                rows.append(f'''
                    <tr style="background-color: {current_row_bg};">
                        <td style="padding: 8px 12px; border-bottom: 1px solid #ecf0f1; font-weight: 700; color: #3498db;">Current</td>
                        <td style="padding: 8px 12px; border-bottom: 1px solid #ecf0f1; text-align: right; font-family: monospace; font-weight: 700; color: #3498db;">{current_pct:.4f}</td>
                    </tr>
                ''')
                current_inserted = True

    # Handle edge case where current is above +4σ or below -4σ
    current_row_bg = hex_to_rgba("#3498db", 0.12)
    if not current_inserted:
        if current_pct > bands.get('+4σ', 0):
            rows.insert(0, f'''
                <tr style="background-color: {current_row_bg};">
                    <td style="padding: 8px 12px; border-bottom: 1px solid #ecf0f1; font-weight: 700; color: #3498db;">Current</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #ecf0f1; text-align: right; font-family: monospace; font-weight: 700; color: #3498db;">{current_pct:.4f}</td>
                </tr>
            ''')
        else:
            rows.append(f'''
                <tr style="background-color: {current_row_bg};">
                    <td style="padding: 8px 12px; border-bottom: 1px solid #ecf0f1; font-weight: 700; color: #3498db;">Current</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #ecf0f1; text-align: right; font-family: monospace; font-weight: 700; color: #3498db;">{current_pct:.4f}</td>
                </tr>
            ''')

    return ''.join(rows)


def calculate_distance_to_next_band(current_pct: float, bands: Dict[str, float], current_band: int) -> Tuple[str, float]:
    """
    Calculate the distance to the next significant band threshold.
    Returns (direction_label, distance_value).
    """
    if current_band >= 0:
        # Above regression line - calculate distance to next upper band
        next_band = current_band + 1
        if next_band <= 4:
            target_key = f'+{next_band}σ'
            target_value = bands.get(target_key, 0)
            distance = target_value - current_pct
            return f"to +{next_band}σ", distance
        else:
            return "above +4σ", 0
    else:
        # Below regression line - calculate distance to next lower band
        next_band = current_band - 1
        if next_band >= -4:
            target_key = f'{next_band}σ'
            target_value = bands.get(target_key, 0)
            distance = current_pct - target_value
            return f"to {next_band}σ", distance
        else:
            return "below -4σ", 0


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
    html_link: Optional[str] = None
) -> Tuple[str, str]:
    """
    Build professional HTML email content and plain text fallback.

    Args:
        symbol: Asset symbol (e.g., "VOO")
        source: Data source (e.g., "alpaca")
        timestamp_utc: Timestamp string in UTC
        latest_price: Current asset price
        previous_band: Previous regression band (-4 to +4)
        current_band: Current regression band (-4 to +4)
        current_pct: Current cumulative percent change
        regression_line: Current regression line value
        bands: Dict with band values (+4σ, +3σ, ..., avg, -1σ, ..., -4σ)
        days_original: Number of days in original reference period
        days_new: Number of days in new comparison period
        sma_window: SMA window size used
        check_frequency: How often the analysis runs (minutes)
        html_link: Optional URL to interactive HTML chart

    Returns:
        Tuple of (html_body, text_body)
    """
    # Get colors for the status pill
    pill_bg, pill_text = get_band_color(current_band)
    prev_label = format_band_label(previous_band)
    curr_label = format_band_label(current_band)

    # Calculate distance to next band
    direction, distance = calculate_distance_to_next_band(current_pct, bands, current_band)

    # Determine status callout style based on direction of change
    if current_band > previous_band:
        status_bg = "#d5f4e6"  # Green tint - moving up
        status_border = "#27ae60"
        status_icon = "📈"
    elif current_band < previous_band:
        status_bg = "#fadbd8"  # Red tint - moving down
        status_border = "#e74c3c"
        status_icon = "📉"
    else:
        status_bg = "#fff3cd"  # Yellow tint - no change
        status_border = "#ff9800"
        status_icon = "➡️"

    # Build the band ladder
    band_ladder_html = build_band_ladder_html(bands, current_pct, current_band)

    # Build the HTML email
    html_body = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compare Timeframes Alert - {symbol}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #ecf0f1; font-family: Arial, sans-serif;">
    <div style="max-width: 680px; margin: 20px auto; padding: 20px; background-color: #f8f9fa; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06);">

        <!-- Header -->
        <h1 style="margin: 0 0 10px; padding-bottom: 10px; border-bottom: 3px solid #3498db; font-size: 22px; color: #2c3e50;">
            {status_icon} Compare Timeframes Alert — {symbol} ({source})
        </h1>
        <p style="margin: 0 0 16px; color: #555; font-size: 14px;">
            As of <strong>{timestamp_utc}</strong>, latest price <strong>${latest_price:.2f}</strong>
        </p>

        <!-- Status Alert Box -->
        <div style="background: {status_bg}; border-left: 4px solid {status_border}; padding: 14px; border-radius: 8px; margin-bottom: 16px;">
            <div style="font-size: 15px; color: #2c3e50;">
                <strong>Band Change Detected:</strong> Moved from <strong>{prev_label}</strong> to
                <span style="background: {pill_bg}; color: {pill_text}; padding: 4px 12px; border-radius: 999px; font-size: 13px; font-weight: 600; margin-left: 4px; display: inline-block;">
                    {curr_label}
                </span>
            </div>
        </div>

        <!-- Key Metrics Grid -->
        <div style="margin-bottom: 16px;">
            <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                <!-- Cumulative % Change -->
                <div style="flex: 1; min-width: 140px; background: #fff; padding: 14px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                    <div style="font-size: 11px; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px;">Cumulative % Change</div>
                    <div style="font-size: 20px; font-weight: 700; color: #2c3e50; margin-top: 4px;">{current_pct:.4f}</div>
                </div>

                <!-- Regression Line -->
                <div style="flex: 1; min-width: 140px; background: #fff; padding: 14px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                    <div style="font-size: 11px; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px;">Regression Line</div>
                    <div style="font-size: 20px; font-weight: 700; color: #2c3e50; margin-top: 4px;">{regression_line:.4f}</div>
                </div>

                <!-- Distance to Next Band -->
                <div style="flex: 1; min-width: 140px; background: #fff; padding: 14px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                    <div style="font-size: 11px; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px;">Distance {direction}</div>
                    <div style="font-size: 20px; font-weight: 700; color: #2c3e50; margin-top: 4px;">{distance:.4f}</div>
                </div>
            </div>
        </div>

        <!-- Secondary Metrics -->
        <div style="margin-bottom: 16px;">
            <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                <div style="flex: 1; min-width: 100px; background: #fff; padding: 12px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                    <div style="font-size: 10px; color: #7f8c8d; text-transform: uppercase;">Reference Days</div>
                    <div style="font-size: 16px; font-weight: 600; color: #34495e; margin-top: 2px;">{days_original}</div>
                </div>
                <div style="flex: 1; min-width: 100px; background: #fff; padding: 12px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                    <div style="font-size: 10px; color: #7f8c8d; text-transform: uppercase;">Current Days</div>
                    <div style="font-size: 16px; font-weight: 600; color: #34495e; margin-top: 2px;">{days_new}</div>
                </div>
                <div style="flex: 1; min-width: 100px; background: #fff; padding: 12px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                    <div style="font-size: 10px; color: #7f8c8d; text-transform: uppercase;">SMA Window</div>
                    <div style="font-size: 16px; font-weight: 600; color: #34495e; margin-top: 2px;">{sma_window}</div>
                </div>
                <div style="flex: 1; min-width: 100px; background: #fff; padding: 12px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
                    <div style="font-size: 10px; color: #7f8c8d; text-transform: uppercase;">Data Source</div>
                    <div style="font-size: 16px; font-weight: 600; color: #34495e; margin-top: 2px;">{source.title()}</div>
                </div>
            </div>
        </div>

        <!-- Band Ladder Table -->
        <div style="background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 16px;">
            <h3 style="margin: 0 0 12px; color: #34495e; font-size: 15px; border-bottom: 2px solid #9b59b6; padding-bottom: 8px;">
                Band Ladder
            </h3>
            <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse; font-size: 13px; color: #2c3e50;">
                <thead>
                    <tr style="background-color: #ecf0f1;">
                        <th style="padding: 10px 12px; text-align: left; font-weight: 600; border-bottom: 2px solid #bdc3c7;">Band</th>
                        <th style="padding: 10px 12px; text-align: right; font-weight: 600; border-bottom: 2px solid #bdc3c7;">Value</th>
                    </tr>
                </thead>
                <tbody>
                    {band_ladder_html}
                </tbody>
            </table>
        </div>

        <!-- Chart Section -->
        <div style="background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); text-align: center; margin-bottom: 16px;">
            <h3 style="margin: 0 0 12px; color: #34495e; font-size: 15px; border-bottom: 2px solid #3498db; padding-bottom: 8px; text-align: left;">
                Regression Analysis Chart
            </h3>
            <img src="cid:chart" alt="Cumulative percent change chart showing regression bands and current position" style="max-width: 100%; border-radius: 6px; border: 1px solid #ecf0f1;"/>
            <p style="margin: 10px 0 0; font-size: 12px; color: #7f8c8d;">
                Zoomed view: Current period vs reference regression bands
            </p>
        </div>

        <!-- Footer -->
        <div style="border-top: 1px solid #ecf0f1; padding-top: 14px; margin-top: 8px;">
            <p style="margin: 0; font-size: 12px; color: #7f8c8d;">
                Next analysis check in <strong>{check_frequency} minutes</strong>.
                {f'<a href="{html_link}" style="color: #3498db; text-decoration: none;">View Interactive Chart</a>' if html_link else ''}
            </p>
            <p style="margin: 8px 0 0; font-size: 11px; color: #95a5a6;">
                This is an automated alert from the Compare Timeframes Analysis System.
            </p>
        </div>
    </div>
</body>
</html>'''

    # Build plain text fallback
    text_body = f"""Compare Timeframes Alert - {symbol} ({source})
{'=' * 50}

BAND CHANGE DETECTED
From: {prev_label}  ->  To: {curr_label}

As of: {timestamp_utc}
Latest Price: ${latest_price:.2f}

KEY METRICS
-----------
Cumulative % Change: {current_pct:.4f}
Regression Line: {regression_line:.4f}
Distance {direction}: {distance:.4f}

ANALYSIS PARAMETERS
-------------------
Reference Period: {days_original} days
Current Period: {days_new} days
SMA Window: {sma_window}
Data Source: {source.title()}

BAND LADDER
-----------
+4σ: {bands.get('+4σ', 0):.4f}
+3σ: {bands.get('+3σ', 0):.4f}
+2σ: {bands.get('+2σ', 0):.4f}
+1σ: {bands.get('+1σ', 0):.4f}
avg: {bands.get('avg', 0):.4f}
-1σ: {bands.get('-1σ', 0):.4f}
-2σ: {bands.get('-2σ', 0):.4f}
-3σ: {bands.get('-3σ', 0):.4f}
-4σ: {bands.get('-4σ', 0):.4f}

** Current Value: {current_pct:.4f} **

{f'Interactive Chart: {html_link}' if html_link else ''}

Next check in {check_frequency} minutes.
---
Automated alert from Compare Timeframes Analysis System
"""

    return html_body, text_body
