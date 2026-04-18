import json
import sys
from pathlib import Path

from service_config import validate_service_config


def load_asset_prices_reader(repo_path):
    repo_path = Path(repo_path).expanduser()
    if not repo_path.is_dir():
        return None, f"Configured asset_prices repo path does not exist: {repo_path}"

    if str(repo_path) not in sys.path:
        sys.path.insert(0, str(repo_path))

    sys.modules.pop("lib.read_utils", None)
    sys.modules.pop("lib", None)

    try:
        from lib.read_utils import read_symbol_data
    except ImportError as exc:
        return None, f"Unable to import lib.read_utils.read_symbol_data from {repo_path}: {exc}"

    return read_symbol_data, None


def build_preflight_report(config, metadata, gmail_config=None, require_gmail=False):
    metadata = metadata or {}
    errors = []
    warnings = []

    if not config:
        errors.append("Service config could not be loaded.")
    else:
        errors.extend(validate_service_config(config, gmail_config=gmail_config, require_gmail=require_gmail))
        repo_path = config.get("asset_prices", {}).get("repo_path")
        if repo_path and not any(issue.startswith("asset_prices.repo_path") for issue in errors):
            _reader, import_error = load_asset_prices_reader(repo_path)
            if import_error:
                errors.append(import_error)

    report = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "secret_source": metadata.get("secret_source"),
        "paths": {
            "config_path": metadata.get("config_path"),
            "local_config_path": metadata.get("local_config_path"),
            "asset_prices_repo": config.get("asset_prices", {}).get("repo_path") if config else None,
            "asset_prices_data_dir": config.get("asset_prices", {}).get("data_dir") if config else None,
            "html_output_path": config.get("runtime", {}).get("html_output_path") if config else None,
            "log_path": config.get("runtime", {}).get("log_path") if config else None,
        },
    }

    return report


def print_preflight_report(report, as_json=False):
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    status = "PASS" if report.get("ok") else "FAIL"
    print(f"Preflight {status}")

    if report.get("secret_source"):
        print(f"Secret source: {report['secret_source']}")

    paths = report.get("paths", {})
    if paths:
        print(f"Config path: {paths.get('config_path')}")
        print(f"Local config path: {paths.get('local_config_path')}")

    if report.get("errors"):
        print("Errors:")
        for error in report["errors"]:
            print(f"- {error}")

    if report.get("warnings"):
        print("Warnings:")
        for warning in report["warnings"]:
            print(f"- {warning}")
