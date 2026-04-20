import argparse
import json
import logging
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from shutil import copyfile

from alert_pipeline import build_alert_payload, send_alert_email
from alert_state import (
    evaluate_transition,
    load_alert_state,
    record_delivery_result,
    resolve_alert_state_path,
    save_alert_state,
)
from analysis_core import load_price_history
from analysis_core import prepare_analysis_frames as _prepare_analysis_frames
from report_pipeline import generate_comparison_report
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

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

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
    if not html_output_path:
        return Path(".")

    html_output = Path(html_output_path).expanduser()
    return html_output.parent if html_output.parent != Path("") else Path(".")


def _check_analysis_dependencies():
    try:
        _load_analysis_dependencies()
    except ModuleNotFoundError as exc:
        return (
            "Missing Python dependency for analysis commands: "
            f"{exc.name}. Install the project requirements before running check, run, report, or test-email."
        )

    return None


def _build_analysis_window(original_start, new_start, new_end):
    pd_module, _, _ = _load_analysis_dependencies()
    earliest_start = min(
        pd_module.to_datetime(original_start), pd_module.to_datetime(new_start)
    ).strftime("%Y-%m-%d")
    parsed_end = pd_module.to_datetime(new_end) if new_end else None
    end_date = parsed_end.strftime("%Y-%m-%d") if parsed_end is not None else None
    return earliest_start, end_date


def _copy_generated_html(html_path, html_output_path):
    if not html_path or not html_output_path:
        return

    source = Path(html_path).expanduser()
    target = Path(html_output_path).expanduser()
    if source.resolve() == target.resolve():
        return

    try:
        copyfile(source, target)
        logging.info(f"Updated HTML file at {target}")
    except Exception as exc:
        logging.error(f"Failed to update HTML file at {target}: {exc}")


def _validate_report_artifacts(report):
    zoomed_jpeg_path = report.get("zoomed_jpeg_path")
    html_path = report.get("html_path")
    full_jpeg_path = report.get("full_jpeg_path")

    if not zoomed_jpeg_path or not Path(zoomed_jpeg_path).exists():
        raise ValueError("Failed to generate zoomed chart.")
    if not html_path or not Path(html_path).exists():
        raise ValueError("Failed to generate HTML report.")
    if full_jpeg_path and not Path(full_jpeg_path).exists():
        logging.warning("Failed to generate full-term chart. Continuing with zoomed output only.")


def _run_analysis_report(
    symbol,
    source,
    original_start,
    original_end,
    new_start,
    new_end,
    sma_window,
    plot_bands,
    plot_bollinger_bands,
    html_output_path,
    data_dir,
    data_type,
    read_symbol_data_fn,
):
    earliest_start, end_date = _build_analysis_window(original_start, new_start, new_end)

    df = load_price_history(
        symbol,
        source,
        start_date=earliest_start,
        end_date=end_date,
        data_type=data_type,
        data_dir=data_dir,
        read_symbol_data_fn=read_symbol_data_fn,
    )
    if df.empty:
        raise ValueError(f"No data available for {symbol}.")

    latest_data_date = df["index"].max()
    adjusted_new_end = min(latest_data_date, datetime.now(timezone.utc))

    df_original, df_new, df_original_truncated = _prepare_analysis_frames(
        df,
        symbol,
        original_start,
        original_end,
        new_start,
        adjusted_new_end,
        sma_window,
        plot_bollinger_bands,
    )

    output_dir = _resolve_output_dir(html_output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = generate_comparison_report(
        symbol,
        source,
        df_original,
        df_original_truncated,
        df_new,
        output_dir,
        sma_window,
        plot_bands=plot_bands,
        plot_bollinger_bands=plot_bollinger_bands,
        original_start=original_start,
        original_end=original_end,
        new_start=new_start,
    )
    _validate_report_artifacts(report)
    _copy_generated_html(report.get("html_path"), html_output_path)

    return {
        "reference_frame": df_original,
        "current_frame": df_new,
        "reference_truncated_frame": df_original_truncated,
        "report": report,
    }
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
    """Run one analysis cycle and send a test email with the current chart."""
    logging.info(f"Generating test email for {symbol}...")

    try:
        analysis_result = _run_analysis_report(
            symbol=symbol,
            source=source,
            original_start=original_start,
            original_end=original_end,
            new_start=new_start,
            new_end=new_end,
            sma_window=sma_window,
            plot_bands=plot_bands,
            plot_bollinger_bands=plot_bollinger_bands,
            html_output_path=html_output_path,
            data_dir=data_dir,
            data_type=data_type,
            read_symbol_data_fn=read_symbol_data_fn,
        )
    except ValueError as exc:
        logging.error(str(exc))
        return False

    report = analysis_result["report"]
    payload = build_alert_payload(
        symbol=symbol,
        source=source,
        previous_band=report["current_band"],
        report=report,
        days_original=len(analysis_result["reference_frame"]),
        days_new=len(analysis_result["current_frame"]),
        sma_window=sma_window,
        check_frequency=check_frequency,
        original_start=original_start,
        original_end=original_end,
        new_start=new_start,
        delivery_mode="test",
    )

    success, message = send_alert_email(
        recipients=email_recipients,
        payload=payload,
    )

    if success:
        logging.info(f"Test email sent successfully to {email_recipients}")
    else:
        logging.error(f"Failed to send test email: {message}")

    return success


def run_report_once(
    symbol,
    source,
    original_start,
    original_end,
    new_start,
    new_end,
    sma_window,
    plot_bands,
    plot_bollinger_bands,
    html_output_path,
    data_dir,
    data_type,
    read_symbol_data_fn,
):
    """Generate the supported no-email report artifacts exactly once."""
    try:
        analysis_result = _run_analysis_report(
            symbol=symbol,
            source=source,
            original_start=original_start,
            original_end=original_end,
            new_start=new_start,
            new_end=new_end,
            sma_window=sma_window,
            plot_bands=plot_bands,
            plot_bollinger_bands=plot_bollinger_bands,
            html_output_path=html_output_path,
            data_dir=data_dir,
            data_type=data_type,
            read_symbol_data_fn=read_symbol_data_fn,
        )
    except ValueError as exc:
        logging.error(str(exc))
        return False

    report = analysis_result["report"]
    logging.info(
        "Generated no-email report for %s | band=%s | html=%s | zoomed=%s",
        symbol,
        report["current_band"],
        report["html_path"],
        report["zoomed_jpeg_path"],
    )
    return True


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
    log_path,
    alert_state_path,
    data_dir,
    data_type,
    read_symbol_data_fn,
):
    """Run the long-lived monitor loop using the shared analysis/report pipeline."""
    state_path = resolve_alert_state_path(
        log_path=log_path,
        configured_path=alert_state_path,
    )
    try:
        state = load_alert_state(state_path)
    except ValueError as exc:
        logging.error(f"Fatal alert state error: {exc}")
        return False

    while True:
        try:
            now = datetime.now(timezone.utc)
            logging.info(
                "Running analysis for %s at %s",
                symbol,
                now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            )

            analysis_result = _run_analysis_report(
                symbol=symbol,
                source=source,
                original_start=original_start,
                original_end=original_end,
                new_start=new_start,
                new_end=new_end,
                sma_window=sma_window,
                plot_bands=plot_bands,
                plot_bollinger_bands=plot_bollinger_bands,
                html_output_path=html_output_path,
                data_dir=data_dir,
                data_type=data_type,
                read_symbol_data_fn=read_symbol_data_fn,
            )
            report = analysis_result["report"]
            current_band = report["current_band"]
            observed_at = now.isoformat()
            transition_result = evaluate_transition(state, current_band, observed_at)
            state = transition_result["state"]
            save_alert_state(state_path, state)
            transition = transition_result["transition"]

            if transition and transition_result["action"] in {
                "new_transition",
                "retry_pending",
            }:
                logging.info(
                    "Regression band changed from %s to %s.",
                    transition["from_band"],
                    transition["to_band"],
                )
                if email_notifications:
                    payload = build_alert_payload(
                        symbol=symbol,
                        source=source,
                        previous_band=transition["from_band"],
                        report=report,
                        days_original=len(analysis_result["reference_frame"]),
                        days_new=len(analysis_result["current_frame"]),
                        sma_window=sma_window,
                        check_frequency=check_frequency,
                        original_start=original_start,
                        original_end=original_end,
                        new_start=new_start,
                        delivery_mode="live",
                    )
                    success, message = send_alert_email(
                        recipients=email_recipients,
                        payload=payload,
                    )
                    state = record_delivery_result(
                        state,
                        transition,
                        delivered=success,
                        error_message=None if success else message,
                    )
                    save_alert_state(state_path, state)
                    if success:
                        logging.info("Professional HTML email sent successfully.")
                    else:
                        logging.error(f"Failed to send email: {message}")
        except ValueError as exc:
            logging.error(f"Fatal analysis error: {exc}")
            return False
        except Exception as exc:
            logging.error(f"Error during analysis: {exc}")

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

    report_parser = subparsers.add_parser(
        "report",
        help="Generate one no-email report cycle after preflight validation succeeds.",
    )
    _add_shared_cli_options(report_parser)

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
    if secret_source and gmail_config and not gmail_error:
        metadata["secret_source"] = secret_source
        config.setdefault("_metadata", {})["secret_source"] = secret_source

    validation_config = _prepare_validation_config(
        config,
        force_alert_readiness=force_alert_readiness,
    )
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
        "alert_state_path": runtime.get("alert_state_path"),
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
        _config, _metadata, _gmail_config, report, _config_error, _gmail_error = _load_command_context(
            args,
            require_gmail=True,
            force_alert_readiness=True,
        )
        dependency_error = _check_analysis_dependencies()
        if dependency_error and dependency_error not in report["errors"]:
            report["errors"].append(dependency_error)
            report["ok"] = False
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
        print(json.dumps(rendered, indent=2, sort_keys=True))
        return 0

    require_gmail = args.command == "test-email"
    force_alert_readiness = args.command in {"check", "test-email"}

    config, _metadata, _gmail_config, report, _config_error, _gmail_error = _load_command_context(
        args,
        require_gmail=require_gmail,
        force_alert_readiness=force_alert_readiness,
    )

    if args.command == "run" and config.get("alerts", {}).get("enabled"):
        config, _metadata, _gmail_config, report, _config_error, _gmail_error = _load_command_context(
            args,
            require_gmail=True,
            force_alert_readiness=False,
        )

    dependency_error = _check_analysis_dependencies()
    if dependency_error and dependency_error not in report["errors"]:
        report["errors"].append(dependency_error)
        report["ok"] = False

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
        return 0 if main_loop(**runtime_settings) is not False else 1

    if args.command == "report":
        return (
            0
            if run_report_once(
                symbol=runtime_settings["symbol"],
                source=runtime_settings["source"],
                original_start=runtime_settings["original_start"],
                original_end=runtime_settings["original_end"],
                new_start=runtime_settings["new_start"],
                new_end=runtime_settings["new_end"],
                sma_window=runtime_settings["sma_window"],
                plot_bands=runtime_settings["plot_bands"],
                plot_bollinger_bands=runtime_settings["plot_bollinger_bands"],
                html_output_path=runtime_settings["html_output_path"],
                data_dir=runtime_settings["data_dir"],
                data_type=runtime_settings["data_type"],
                read_symbol_data_fn=runtime_settings["read_symbol_data_fn"],
            )
            else 1
        )

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


_configure_logging()


if __name__ == "__main__":
    sys.exit(main())
