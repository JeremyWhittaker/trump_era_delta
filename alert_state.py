import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ALERT_STATE = {
    "last_observed_band": None,
    "pending_transition": None,
    "last_delivered_transition": None,
    "pending_monthly_update": None,
    "last_monthly_update": None,
    "last_error": None,
}


def _default_state():
    return deepcopy(DEFAULT_ALERT_STATE)


def _coerce_band(value, label):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Alert state {label} must be an integer band.")
    return value


def _normalize_transition(value, label):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"Alert state {label} must be an object.")

    transition = {
        "from_band": _coerce_band(value.get("from_band"), f"{label}.from_band"),
        "to_band": _coerce_band(value.get("to_band"), f"{label}.to_band"),
        "observed_at": value.get("observed_at"),
    }
    if transition["from_band"] is None or transition["to_band"] is None:
        raise ValueError(
            f"Alert state {label} must include integer from_band and to_band values."
        )
    if not isinstance(transition["observed_at"], str) or not transition["observed_at"].strip():
        raise ValueError(
            f"Alert state {label} must include a non-empty observed_at timestamp."
        )

    for key in ("delivered_at", "last_attempt_at", "last_error"):
        if key in value and value[key] is not None:
            if not isinstance(value[key], str):
                raise ValueError(f"Alert state {label}.{key} must be a string when present.")
            transition[key] = value[key]

    return transition


def _normalize_monthly_update(value, label):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"Alert state {label} must be an object.")

    month = value.get("month")
    if not isinstance(month, str) or not month.strip():
        raise ValueError(f"Alert state {label} must include a non-empty month value.")

    observed_at = value.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise ValueError(
            f"Alert state {label} must include a non-empty observed_at timestamp."
        )

    monthly_update = {
        "month": month.strip(),
        "observed_at": observed_at,
    }

    for key in ("delivered_at", "last_attempt_at", "last_error"):
        if key in value and value[key] is not None:
            if not isinstance(value[key], str):
                raise ValueError(f"Alert state {label}.{key} must be a string when present.")
            monthly_update[key] = value[key]

    return monthly_update


def _normalize_state(state):
    if not isinstance(state, dict):
        raise ValueError("Alert state file must contain a JSON object.")

    normalized = _default_state()
    normalized["last_observed_band"] = _coerce_band(
        state.get("last_observed_band"),
        "last_observed_band",
    )
    normalized["pending_transition"] = _normalize_transition(
        state.get("pending_transition"),
        "pending_transition",
    )
    normalized["last_delivered_transition"] = _normalize_transition(
        state.get("last_delivered_transition"),
        "last_delivered_transition",
    )
    normalized["pending_monthly_update"] = _normalize_monthly_update(
        state.get("pending_monthly_update"),
        "pending_monthly_update",
    )
    normalized["last_monthly_update"] = _normalize_monthly_update(
        state.get("last_monthly_update"),
        "last_monthly_update",
    )

    last_error = state.get("last_error")
    if last_error is not None and not isinstance(last_error, str):
        raise ValueError("Alert state last_error must be a string when present.")
    normalized["last_error"] = last_error

    return normalized


def _parse_observed_at(observed_at):
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise ValueError("Alert state observed_at must be a non-empty timestamp.")

    normalized = observed_at.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Alert state observed_at is not a valid ISO timestamp: {observed_at}") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_alert_state_path(log_path=None, configured_path=None):
    if configured_path:
        return Path(configured_path).expanduser()

    if log_path:
        log_file = Path(log_path).expanduser()
        return log_file.parent / "alert_state.json"

    return Path("runtime") / "alert_state.json"


def load_alert_state(path):
    path = Path(path).expanduser()
    if not path.exists():
        return _default_state()

    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw_state = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in alert state file {path}: {exc}") from exc

    return _normalize_state(raw_state)


def save_alert_state(path, state):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_state(state)

    temp_path = path.with_name(f".{path.name}.tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2, sort_keys=True)
        handle.write("\n")

    temp_path.replace(path)
    return path


def evaluate_transition(state, current_band, observed_at):
    normalized = _normalize_state(state)
    updated = deepcopy(normalized)
    updated["last_observed_band"] = _coerce_band(current_band, "current_band")

    previous_band = normalized["last_observed_band"]
    pending_transition = normalized["pending_transition"]

    if previous_band is None:
        return {"action": "observe_only", "transition": None, "state": updated}

    if pending_transition and current_band == pending_transition["to_band"]:
        updated["pending_transition"] = deepcopy(pending_transition)
        return {
            "action": "retry_pending",
            "transition": deepcopy(pending_transition),
            "state": updated,
        }

    if current_band == previous_band:
        return {"action": "no_change", "transition": None, "state": updated}

    transition = {
        "from_band": previous_band,
        "to_band": current_band,
        "observed_at": observed_at,
    }
    updated["pending_transition"] = deepcopy(transition)
    return {"action": "new_transition", "transition": transition, "state": updated}


def record_delivery_result(state, transition, delivered, error_message=None):
    normalized = _normalize_state(state)
    updated = deepcopy(normalized)

    if delivered:
        delivered_transition = deepcopy(transition)
        delivered_transition["delivered_at"] = datetime.now(timezone.utc).isoformat()
        updated["pending_transition"] = None
        updated["last_delivered_transition"] = delivered_transition
        updated["last_error"] = None
        return updated

    pending_transition = deepcopy(transition)
    pending_transition["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
    if error_message:
        pending_transition["last_error"] = error_message
    updated["pending_transition"] = pending_transition
    updated["last_error"] = error_message
    return updated


def evaluate_monthly_update(state, observed_at):
    normalized = _normalize_state(state)
    updated = deepcopy(normalized)
    observed_dt = _parse_observed_at(observed_at)
    month_key = observed_dt.strftime("%Y-%m")

    if observed_dt.day != 1:
        return {"action": "not_due", "monthly_update": None, "state": updated}

    last_monthly_update = normalized["last_monthly_update"]
    if last_monthly_update and last_monthly_update["month"] == month_key:
        return {"action": "already_delivered", "monthly_update": None, "state": updated}

    pending_monthly_update = normalized["pending_monthly_update"]
    if pending_monthly_update and pending_monthly_update["month"] == month_key:
        updated["pending_monthly_update"] = deepcopy(pending_monthly_update)
        return {
            "action": "retry_pending",
            "monthly_update": deepcopy(pending_monthly_update),
            "state": updated,
        }

    monthly_update = {
        "month": month_key,
        "observed_at": observed_at,
    }
    updated["pending_monthly_update"] = deepcopy(monthly_update)
    return {
        "action": "new_monthly_update",
        "monthly_update": monthly_update,
        "state": updated,
    }


def record_monthly_update_result(state, monthly_update, delivered, error_message=None):
    normalized = _normalize_state(state)
    updated = deepcopy(normalized)

    if delivered:
        delivered_update = deepcopy(monthly_update)
        delivered_update["delivered_at"] = datetime.now(timezone.utc).isoformat()
        updated["pending_monthly_update"] = None
        updated["last_monthly_update"] = delivered_update
        updated["last_error"] = None
        return updated

    pending_update = deepcopy(monthly_update)
    pending_update["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
    if error_message:
        pending_update["last_error"] = error_message
    updated["pending_monthly_update"] = pending_update
    updated["last_error"] = error_message
    return updated
