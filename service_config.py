import json
import os
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "service.json"
DEFAULT_LOCAL_CONFIG_PATH = PROJECT_ROOT / "config" / "service.local.json"
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
COMPAT_ENV_FILE = PROJECT_ROOT / ".env.local"
LEGACY_GMAIL_ENV_FILE = Path.home() / ".gmail_send" / ".env"

PASSWORD_KEYS = {"GMAIL_APP_PASSWORD", "app_password", "password"}
REQUIRED_SECTIONS = ("asset_prices", "monitor", "alerts", "runtime")


def _coerce_path(path_value):
    return Path(path_value).expanduser()


def _resolve_project_path(path_value):
    path = _coerce_path(path_value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _read_json_object(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None, f"Config file not found: {path}"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON in {path}: {exc}"

    if not isinstance(data, dict):
        return None, f"Config file must contain a JSON object: {path}"

    return data, None


def _deep_merge(base, override):
    merged = deepcopy(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)

    return merged


def _read_env_values(path):
    values = {}

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def _read_recipients_file(path):
    recipients = []

    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            recipients.append(line)

    return recipients


def _get_legacy_env_path(env):
    home = env.get("HOME")
    if home:
        return Path(home).expanduser() / ".gmail_send" / ".env"
    return LEGACY_GMAIL_ENV_FILE


def _has_nonempty_value(value):
    return bool(str(value or "").strip())


def _has_direct_gmail_env(env):
    return _has_nonempty_value(env.get("GMAIL_ADDRESS")) and _has_nonempty_value(
        env.get("GMAIL_APP_PASSWORD")
    )


def _parse_date(value, label, issues):
    if not value:
        issues.append(f"Missing required date value for {label}.")
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        issues.append(f"Invalid date for {label}: {value}. Expected YYYY-MM-DD.")
        return None


def _sanitize_value(value):
    if isinstance(value, dict):
        sanitized = {}
        for key, nested_value in value.items():
            if key in PASSWORD_KEYS or "password" in key.lower():
                continue
            if key.startswith("_"):
                continue
            sanitized[key] = _sanitize_value(nested_value)
        return sanitized

    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]

    return value


def load_service_config(config_path=None, local_config_path=None, env=None):
    env = dict(os.environ if env is None else env)
    config_path = _coerce_path(config_path or DEFAULT_CONFIG_PATH)
    local_config_path = _coerce_path(local_config_path or DEFAULT_LOCAL_CONFIG_PATH)
    default_local_resolved = DEFAULT_LOCAL_CONFIG_PATH.resolve(strict=False)
    local_config_is_default = local_config_path.resolve(strict=False) == default_local_resolved

    metadata = {
        "config_path": str(config_path),
        "local_config_path": str(local_config_path),
        "config_exists": config_path.exists(),
        "local_config_exists": local_config_path.exists(),
        "local_config_is_default": local_config_is_default,
        "env_overrides": [],
        "secret_source": "environment" if _has_direct_gmail_env(env) else None,
    }

    base_config, error = _read_json_object(config_path)
    if error:
        return None, metadata, error

    local_config = {}
    if local_config_path.exists():
        local_config, error = _read_json_object(local_config_path)
        if error:
            return None, metadata, error

    merged = _deep_merge(base_config, local_config)

    asset_prices = merged.setdefault("asset_prices", {})
    if env.get("ASSET_PRICES_REPO"):
        asset_prices["repo_path"] = env["ASSET_PRICES_REPO"]
        metadata["env_overrides"].append("ASSET_PRICES_REPO")
    if env.get("ASSET_PRICES_DATA_DIR"):
        asset_prices["data_dir"] = env["ASSET_PRICES_DATA_DIR"]
        metadata["env_overrides"].append("ASSET_PRICES_DATA_DIR")
    if env.get("ASSET_PRICES_DATA_TYPE"):
        asset_prices["data_type"] = env["ASSET_PRICES_DATA_TYPE"]
        metadata["env_overrides"].append("ASSET_PRICES_DATA_TYPE")

    monitor = merged.setdefault("monitor", {})
    if monitor.get("new_end") == "today":
        monitor["new_end"] = date.today().isoformat()

    alerts = merged.setdefault("alerts", {})
    recipients_file_value = alerts.get("recipients_file")
    if recipients_file_value:
        recipients_path = _resolve_project_path(recipients_file_value)
        metadata["recipients_file_path"] = str(recipients_path)
        metadata["recipients_file_exists"] = recipients_path.exists()

        if recipients_path.exists():
            alerts["recipients"] = _read_recipients_file(recipients_path)
            metadata["recipients_source"] = str(recipients_path)
        else:
            alerts.setdefault("recipients", [])

    merged["_metadata"] = deepcopy(metadata)
    return merged, metadata, None


def load_gmail_secret_config(env_file=None, env=None):
    env = dict(os.environ if env is None else env)
    if _has_direct_gmail_env(env):
        return {
            "email": str(env["GMAIL_ADDRESS"]).strip(),
            "app_password": str(env["GMAIL_APP_PASSWORD"]).strip(),
        }, "environment", None

    legacy_path = _get_legacy_env_path(env)
    sources = (
        [_coerce_path(env_file)]
        if env_file
        else [DEFAULT_ENV_FILE, COMPAT_ENV_FILE, legacy_path]
    )

    for source in sources:
        if not source.exists():
            continue

        values = _read_env_values(source)
        email = values.get("GMAIL_ADDRESS", "").strip()
        app_password = values.get("GMAIL_APP_PASSWORD", "").strip()
        if not email or not app_password:
            return None, str(source), (
                f"Gmail configuration incomplete in {source}. "
                "Need non-empty GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
            )

        return {
            "email": email,
            "app_password": app_password,
        }, str(source), None

    return None, None, (
        f"Gmail not configured. Create {DEFAULT_ENV_FILE} with GMAIL_ADDRESS and "
        f"GMAIL_APP_PASSWORD, or use compatibility fallback {COMPAT_ENV_FILE}, "
        f"or legacy fallback {legacy_path}."
    )


def validate_service_config(config, gmail_config=None, require_gmail=False):
    issues = []

    if not isinstance(config, dict):
        return ["Service config could not be loaded."]

    metadata = config.get("_metadata", {})

    for section in REQUIRED_SECTIONS:
        if section not in config or not isinstance(config[section], dict):
            issues.append(f"Missing required config section: {section}.")

    if (
        metadata
        and not metadata.get("local_config_exists", False)
        and not metadata.get("local_config_is_default", False)
    ):
        issues.append(
            f"Local override file is missing: {metadata.get('local_config_path', DEFAULT_LOCAL_CONFIG_PATH)}."
        )

    asset_prices = config.get("asset_prices", {})
    repo_path = asset_prices.get("repo_path")
    data_dir = asset_prices.get("data_dir")
    if not repo_path or not Path(repo_path).expanduser().is_dir():
        issues.append(f"asset_prices.repo_path does not exist or is not a directory: {repo_path}.")
    if not data_dir or not Path(data_dir).expanduser().is_dir():
        issues.append(f"asset_prices.data_dir does not exist or is not a directory: {data_dir}.")

    monitor = config.get("monitor", {})
    original_start = _parse_date(monitor.get("original_start"), "monitor.original_start", issues)
    original_end = _parse_date(monitor.get("original_end"), "monitor.original_end", issues)
    new_start = _parse_date(monitor.get("new_start"), "monitor.new_start", issues)
    new_end = _parse_date(monitor.get("new_end"), "monitor.new_end", issues)

    if original_start and original_end and original_start > original_end:
        issues.append("monitor.original_start must be on or before monitor.original_end.")
    if new_start and new_end and new_start > new_end:
        issues.append("monitor.new_start must be on or before monitor.new_end.")

    alerts = config.get("alerts", {})
    recipients = alerts.get("recipients", [])
    recipients_file = alerts.get("recipients_file")
    recipients_file_path = metadata.get("recipients_file_path")
    recipients_file_exists = metadata.get("recipients_file_exists")

    if recipients_file and recipients_file_path and not recipients_file_exists:
        issues.append(f"alerts.recipients_file does not exist: {recipients_file_path}.")

    if alerts.get("enabled"):
        if not isinstance(recipients, list) or not any(str(item).strip() for item in recipients):
            issues.append("alerts.recipients must include at least one address when alerts.enabled is true.")

    if require_gmail:
        if not gmail_config:
            issues.append("Gmail credentials are required for this command.")
        else:
            if not gmail_config.get("email"):
                issues.append("Gmail config is missing the sender address.")
            if not gmail_config.get("app_password"):
                issues.append("Gmail config is missing the app password.")

    return issues


def redact_service_config(config, metadata=None):
    safe_config = _sanitize_value(config or {})
    safe_metadata = _sanitize_value(metadata or safe_config.pop("metadata", None) or {})

    if safe_metadata:
        safe_config["metadata"] = safe_metadata

    return safe_config
