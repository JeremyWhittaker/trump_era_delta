---
phase: 01-configuration-foundation
reviewed: 2026-04-18T02:46:59Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - main.py
  - service_config.py
  - service_bootstrap.py
  - send_gmail.py
  - send_test_email.py
findings:
  critical: 0
  warning: 3
  info: 1
  total: 4
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-18T02:46:59Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the Phase 01 configuration and alert-delivery files in context with the phase summaries and the current CLI tests. The scoped unit tests pass, but the review still found three runtime correctness issues in config validation and alert execution, plus one cleanup item where a deprecated recipient path is still present in `main.py`.

## Warnings

### WR-01: Blank Gmail placeholders are accepted as a valid secret source

**File:** `service_config.py:164-174`, `main.py:1500-1504`
**Issue:** `load_gmail_secret_config(...)` only checks whether `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` keys exist in `.env.local`; blank values still count as success. `_load_command_context(...)` then records `secret_source` unconditionally, so a stub `.env.local` is reported as the active source even though the credentials are unusable. In practice this downgrades an actionable file-specific error into later generic validation messages and misleads operators about what actually loaded.
**Fix:**
```python
# service_config.py
email = values.get("GMAIL_ADDRESS", "").strip()
app_password = values.get("GMAIL_APP_PASSWORD", "").strip()
if not email or not app_password:
    return None, str(source), (
        f"Gmail configuration incomplete in {source}. "
        "Need non-empty GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
    )

return {"email": email, "app_password": app_password}, str(source), None

# main.py
if secret_source and gmail_config and not gmail_error:
    metadata["secret_source"] = secret_source
    config.setdefault("_metadata", {})["secret_source"] = secret_source
```

### WR-02: Optional local override file is treated as a hard runtime dependency

**File:** `service_config.py:123-126`, `service_config.py:197-200`
**Issue:** `load_service_config(...)` treats a missing default `config/service.local.json` as optional, but `validate_service_config(...)` later turns that absence into an error. That makes `check`, `run`, and `test-email` fail on a clean checkout even when the committed config plus environment overrides are otherwise sufficient. The loader and validator currently disagree about whether the local override file is optional.
**Fix:**
```python
# Only fail when the caller explicitly asked for a custom local config path.
if metadata and not metadata.get("local_config_exists", False):
    local_path = metadata.get("local_config_path", str(DEFAULT_LOCAL_CONFIG_PATH))
    if Path(local_path) != DEFAULT_LOCAL_CONFIG_PATH:
        issues.append(f"Local override file is missing: {local_path}.")
```

### WR-03: Alert generation assumes the truncated reference window is always non-empty

**File:** `main.py:1076-1119`, `main.py:1264-1314`
**Issue:** Both `send_test_email_now(...)` and `main_loop(...)` truncate the reference period to `num_days_new`, skip `calculate_regression_bands(...)` when the truncated frame is empty, and then immediately read `.iloc[-1]` and regression-band columns anyway. If the reference dataset is shorter than the current dataset or the configured date window returns partial data, `test-email` raises at runtime and `run` drops into a repeat-fail-sleep loop instead of surfacing a clear operator-facing error.
**Fix:**
```python
if len(df_original_truncated) < 2:
    message = (
        f"Reference period produced only {len(df_original_truncated)} row(s) "
        f"for {symbol}; cannot compute regression bands for {num_days_new} current-day rows."
    )
    logging.error(message)
    return False  # or raise ValueError(message) before entering the loop

df_original_truncated = calculate_regression_bands(df_original_truncated)
```

## Info

### IN-01: Deprecated file-based recipient loader is still present in `main.py`

**File:** `main.py:75-94`
**Issue:** `EMAIL_RECIPIENTS_FILE` and `load_email_recipients()` are no longer used by the config-backed alert flow described in phase `01-03`, but they still live in the main runtime module. Keeping the deprecated path around leaves two recipient sources in the codebase and increases the chance of future drift.
**Fix:** Remove the helper, or replace it with a thin adapter that reads `alerts.recipients` from the merged service config so there is only one supported recipient contract.

---

_Reviewed: 2026-04-18T02:46:59Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
