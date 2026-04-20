# Phase 3: Alert Reliability - Pattern Map

**Mapped:** 2026-04-19
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `alert_pipeline.py` | utility | notification | `main.py`, `email_template.py`, `send_gmail.py` | role-match |
| `alert_state.py` | utility | state-management | `service_config.py`, `main.py` | role-match |
| `main.py` | controller | request-response | `main.py` | exact |
| `send_test_email.py` | wrapper | request-forwarding | `send_test_email.py` | exact |
| `README.md` | documentation | operator-guidance | `README.md` | exact |
| `tests/test_alert_pipeline.py` | test | verification | `tests/test_report_pipeline.py`, `tests/test_send_gmail_config.py` | role-match |
| `tests/test_alert_state.py` | test | verification | `tests/test_service_config.py` | role-match |
| `tests/test_main_cli.py` | test | verification | `tests/test_main_cli.py` | exact |

## Pattern Assignments

### `alert_pipeline.py` (utility, notification)

**Analogs:** `main.py`, `email_template.py`, `send_gmail.py`

**Current payload and delivery logic in `main.py`:**
```python
def _format_period_context(...):
    ...

def _build_inline_images(zoomed_jpeg_path, full_jpeg_path):
    ...

def _send_band_email(...):
    html_body, text_body = build_email_content(...)
    inline_images = _build_inline_images(...)
    return send_email(...)
```

**Current rendering and transport boundaries:**
```python
html_body, text_body = build_email_content(...)
success, message = send_email(
    to_addrs=email_recipients,
    subject=subject,
    body=None,
    html_body=html_body,
    text_body=text_body,
    inline_images=inline_images,
)
```

**Phase 3 pattern:** extract one shared alert module that assembles rendered payloads, inline image metadata, and transport calls for both live and test email paths. Keep `email_template.py` as the renderer and `send_gmail.py` as the SMTP boundary; the new module should only normalize inputs, subjects, and inline-asset handling around those existing contracts.

Use small top-level helpers and concrete dict/tuple returns, matching the current script style instead of introducing classes.

---

### `alert_state.py` (utility, state-management)

**Analogs:** `service_config.py`, `main.py`

**Current process-local alert memory in `main.py`:**
```python
previous_band = None

if previous_band is None:
    previous_band = current_band
elif current_band != previous_band:
    ...
    previous_band = current_band
```

**Existing JSON/path handling style in `service_config.py`:**
```python
def _read_json_object(path):
    ...

def _coerce_path(path_value):
    return Path(path_value).expanduser()
```

**Phase 3 pattern:** introduce a root-level helper module that owns alert-state file resolution, JSON load/save, and transition bookkeeping behind explicit functions. Follow the same guard-clause and actionable-error style as `service_config.py`, but keep the stored schema lightweight and single-operator. Prefer atomic write semantics with `Path` helpers and temp-file replacement over in-place mutation.

---

### `main.py` (controller, request-response)

**Analog:** `main.py`

**Current controller seams:**
```python
def send_test_email_now(...):
    ...

def main_loop(...):
    ...

def main(argv=None):
    ...
```

**Phase 3 controller pattern:**
- Keep `main.py` as the single supported operator entrypoint.
- Move alert-payload composition and persisted-state bookkeeping into helper modules, leaving `main.py` to orchestrate commands, loops, and operator-facing logging.
- Add any one-shot live verification surface as a flag on the existing `run` command rather than creating a second orchestration script.

---

### `send_test_email.py` (wrapper, request-forwarding)

**Analog:** `send_test_email.py`

**Current wrapper shape:**
```python
def main():
    return main_entry(["test-email", *sys.argv[1:]])
```

**Phase 3 pattern:** keep this file thin. If it remains in the repo, it should stay a direct forwarder to `main.py test-email` and never regain its own analysis, template, or SMTP logic.

---

### Tests (`tests/test_alert_pipeline.py`, `tests/test_alert_state.py`, `tests/test_main_cli.py`)

**Analogs:** `tests/test_service_config.py`, `tests/test_report_pipeline.py`, `tests/test_main_cli.py`

**Current test style:**
```python
import tempfile
import unittest
from unittest import mock
```

**Phase 3 test pattern:**
- Use stdlib `unittest`, `tempfile`, and `unittest.mock`.
- Test alert payload and state helpers with small synthetic report dictionaries and temp files instead of real SMTP or `asset_prices` calls.
- Keep CLI tests focused on routing, exit codes, and “did or did not call the delivery helper” assertions.

---

## Planning Guidance

- Preserve the current email HTML/text rendering and band interpretation semantics; Phase 3 is about delivery reliability, not email redesign.
- Keep persisted state project-local and runtime-oriented, not in committed config or in-memory globals.
- Build explicit live/test verification around the existing `main.py` CLI surface so later service-manager work can reuse it.
- Remove or keep thin any stale helper scripts; do not let `send_test_email.py` drift back into a second implementation path.
