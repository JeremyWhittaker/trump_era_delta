from datetime import datetime, timezone
from pathlib import Path

from email_template import build_email_content
from send_gmail import send_email


def _format_period_context(original_start, original_end, new_start):
    original_start_label = datetime.strptime(original_start, "%Y-%m-%d").strftime("%b %Y")
    original_end_label = datetime.strptime(original_end, "%Y-%m-%d").strftime("%b %Y")
    new_start_label = datetime.strptime(new_start, "%Y-%m-%d").strftime("%b %Y")
    return {
        "reference_start": original_start_label,
        "reference_end": original_end_label,
        "current_start": new_start_label,
    }


def _format_band_label(band):
    return f"{'+' if band > 0 else ''}{band}σ"


def _format_timestamp_utc(latest_date):
    if latest_date.tzinfo is None:
        latest_date = latest_date.replace(tzinfo=timezone.utc)
    else:
        latest_date = latest_date.astimezone(timezone.utc)
    return latest_date.strftime("%Y-%m-%d %H:%M:%S UTC")


def _build_inline_images(zoomed_jpeg_path, full_jpeg_path):
    with open(zoomed_jpeg_path, "rb") as handle:
        zoomed_chart_bytes = handle.read()

    inline_images = [
        {
            "cid": "chart_zoomed",
            "content": zoomed_chart_bytes,
            "subtype": "jpeg",
        }
    ]

    if full_jpeg_path and Path(full_jpeg_path).exists():
        with open(full_jpeg_path, "rb") as handle:
            full_chart_bytes = handle.read()
        inline_images.append(
            {
                "cid": "chart_full",
                "content": full_chart_bytes,
                "subtype": "jpeg",
            }
        )

    return inline_images


def _build_subject(symbol, report, delivery_mode):
    band_label = _format_band_label(report["current_band"])
    if delivery_mode == "live":
        return f"Regression Band Alert: {symbol} -> {band_label}"
    if delivery_mode == "test":
        return f"TEST EMAIL: {symbol} @ {band_label} ({report['current_pct']:+.2%})"
    raise ValueError(f"Unsupported delivery mode: {delivery_mode}")


def build_alert_payload(
    *,
    symbol,
    source,
    previous_band,
    report,
    days_original,
    days_new,
    sma_window,
    check_frequency,
    original_start,
    original_end,
    new_start,
    delivery_mode,
):
    period_context = _format_period_context(original_start, original_end, new_start)
    timestamp_utc = _format_timestamp_utc(report["latest_date"])

    html_body, text_body = build_email_content(
        symbol=symbol,
        source=source,
        timestamp_utc=timestamp_utc,
        latest_price=report["latest_price"],
        previous_band=previous_band,
        current_band=report["current_band"],
        current_pct=report["current_pct"],
        regression_line=report["regression_line"],
        bands=report["bands"],
        days_original=days_original,
        days_new=days_new,
        sma_window=sma_window,
        check_frequency=check_frequency,
        reference_period_name="Trump First Term",
        reference_start=period_context["reference_start"],
        reference_end=period_context["reference_end"],
        current_period_name="Trump Second Term",
        current_start=period_context["current_start"],
        html_link=None,
    )

    return {
        "subject": _build_subject(symbol, report, delivery_mode),
        "html_body": html_body,
        "text_body": text_body,
        "inline_images": _build_inline_images(
            report["zoomed_jpeg_path"],
            report.get("full_jpeg_path"),
        ),
    }


def send_alert_email(*, recipients, payload):
    return send_email(
        to_addrs=recipients,
        subject=payload["subject"],
        body=None,
        html_body=payload["html_body"],
        text_body=payload["text_body"],
        inline_images=payload["inline_images"],
    )
