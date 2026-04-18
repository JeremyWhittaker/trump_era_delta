# Phase 1: Configuration Foundation - Pattern Map

**Mapped:** 2026-04-17
**Files analyzed:** 8
**Analogs found:** 7 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `config/service.json` | config | file-I/O | `main.py` | partial |
| `config/service.local.json` | config | file-I/O | `main.py` | partial |
| `.env.local` | config | file-I/O | `send_gmail.py` | partial |
| `.gitignore` | config | file-I/O | none | no-analog |
| `service_config.py` (implied new helper) | utility | file-I/O | `send_gmail.py` | role-match |
| `main.py` | controller | request-response | `main.py` | exact |
| `send_gmail.py` | service | request-response | `send_gmail.py` | exact |
| `send_test_email.py` (if retained as thin wrapper) | utility | request-response | `main.py` | partial |

## Pattern Assignments

### `config/service.json` and `config/service.local.json` (config, file-I/O)

**Analog:** `main.py` (partial; current runtime settings are split across env constants, recipient loading, and CLI flags)

**Seed field inventory** (`main.py` lines 26-28, 43-60, 1323-1349):
```python
ASSET_PRICES_REPO = Path(os.getenv("ASSET_PRICES_REPO", "/home/shared/algos/asset_prices"))
ASSET_PRICES_DATA_DIR = Path(os.getenv("ASSET_PRICES_DATA_DIR", ASSET_PRICES_REPO / "data"))
DEFAULT_DATA_TYPE = os.getenv("ASSET_PRICES_DATA_TYPE", "adjusted")
EMAIL_RECIPIENTS_FILE = Path(__file__).parent / 'email_recipients.txt'

def load_email_recipients():
    if not EMAIL_RECIPIENTS_FILE.exists():
        logging.warning(f"Email recipients file not found: {EMAIL_RECIPIENTS_FILE}")
        return []
    ...

parser = argparse.ArgumentParser(...)
parser.add_argument('--symbol', type=str, default="VOO", ...)
parser.add_argument('--source', type=str, choices=['yfinance', 'alpaca'], default="alpaca", ...)
parser.add_argument('--original_start', type=str, default="2016-11-08", ...)
parser.add_argument('--original_end', type=str, default="2020-11-03", ...)
parser.add_argument('--new_start', type=str, default="2024-11-05", ...)
parser.add_argument('--new_end', type=str, default=datetime.today().strftime('%Y-%m-%d'), ...)
parser.add_argument('--sma_window', type=int, default=100, ...)
parser.add_argument('--email_notifications', action='store_true', default=True, ...)
parser.add_argument('--email_recipients', nargs='+', default=None, ...)
parser.add_argument('--check_frequency', type=int, default=15, ...)
parser.add_argument('--html_output_path', type=str, default='./plots/index.html', ...)
```

Use the existing env/CLI surface as the schema source for JSON keys. There is no structured-config analog in the repo yet, so planner should lift these settings into JSON instead of inventing a parallel vocabulary.

Keep `service.json` for committed defaults and `service.local.json` for non-secret machine overrides. Keep Gmail secrets out of both files.

---

### `.env.local` (config, file-I/O)

**Analog:** `send_gmail.py`

**Secret key contract** (`send_gmail.py` lines 5-8, 27-49):
```python
Configuration:
  Create ~/.gmail_send/.env with:
    GMAIL_ADDRESS=your_email@gmail.com
    GMAIL_APP_PASSWORD=your_app_password

env_file = os.path.expanduser("~/.gmail_send/.env")
if not os.path.exists(env_file):
    return None, "Gmail not configured. Create ~/.gmail_send/.env with GMAIL_ADDRESS and GMAIL_APP_PASSWORD"

config = {}
with open(env_file, "r") as f:
    for line in f:
        ...
        if key == "GMAIL_ADDRESS":
            config["email"] = value
        elif key == "GMAIL_APP_PASSWORD":
            config["app_password"] = value

if "email" not in config or "app_password" not in config:
    return None, "Gmail configuration incomplete. Need GMAIL_ADDRESS and GMAIL_APP_PASSWORD in ~/.gmail_send/.env"
```

Keep the same key names during migration. The path changes from the legacy home-directory file to project-local `.env.local`, but the credential contract should stay compatible.

---

### `service_config.py` (implied new helper; utility, file-I/O)

**Analog:** `send_gmail.py`

**Imports and loader pattern** (`send_gmail.py` lines 15-24, 27-49):
```python
import sys
import os
import smtplib
import logging
from pathlib import Path

def load_config():
    env_file = os.path.expanduser("~/.gmail_send/.env")
    if not os.path.exists(env_file):
        return None, "Gmail not configured..."

    config = {}
    with open(env_file, "r") as f:
        for line in f:
            ...

    if "email" not in config or "app_password" not in config:
        return None, "Gmail configuration incomplete..."

    return config, None
```

**Path validation and guard-clause pattern** (`main.py` lines 30-40, 46-60):
```python
if str(ASSET_PRICES_REPO) not in sys.path:
    sys.path.insert(0, str(ASSET_PRICES_REPO))

try:
    from lib.read_utils import read_symbol_data
except ImportError as exc:
    raise ImportError(
        f"Unable to import lib.read_utils from {ASSET_PRICES_REPO}. "
        "Set ASSET_PRICES_REPO/ASSET_PRICES_DATA_DIR to point at the asset_prices project."
    ) from exc

if not EMAIL_RECIPIENTS_FILE.exists():
    logging.warning(f"Email recipients file not found: {EMAIL_RECIPIENTS_FILE}")
    return []
```

Copy the small top-level function style, manual file parsing, and actionable operator-facing error messages. Prefer a loader/validator that returns validated config data plus explicit error text instead of introducing a class-heavy config system.

---

### `main.py` (controller, request-response)

**Analog:** `main.py`

**CLI dispatch pattern** (`main.py` lines 1322-1388):
```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare an asset's historical performance with indicators.")
    parser.add_argument('--symbol', type=str, default="VOO", ...)
    ...
    parser.add_argument('--send_test_email', action='store_true',
                        help="Send a test email with current chart and exit ...")

    args = parser.parse_args()
    email_recipients = args.email_recipients if args.email_recipients else load_email_recipients()

    if args.send_test_email:
        success = send_test_email_now(...)
        sys.exit(0 if success else 1)
    else:
        main_loop(...)
```

Keep `argparse` at the bottom of the file, explicit dispatch, and explicit exit codes. Phase 1 should replace boolean-flag branching with `check`, `run`, `test-email`, and `show-config` subcommands, but it should still look like this module rather than a framework CLI.

**One-shot command pattern** (`main.py` lines 966-1111):
```python
def send_test_email_now(...):
    df = load_data(...)
    if df.empty:
        logging.error(f"No data available for {symbol}. Cannot send test email.")
        return False
    ...
    success, message = send_email(
        to_addrs=email_recipients,
        subject=subject,
        body=None,
        html_body=html_body,
        text_body=text_body,
        inline_images=inline_images
    )

    if success:
        logging.info(f"Test email sent successfully to {email_recipients}")
    else:
        logging.error(f"Failed to send test email: {message}")

    return success
```

Use this shape for `test-email` and likely `check`: perform one full operation, return a boolean/result, and let the CLI decide the exit code.

**Run-loop boundary pattern** (`main.py` lines 1124-1320):
```python
while True:
    try:
        now = datetime.now(timezone.utc)
        logging.info(f"Running analysis for {symbol} at {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        df = load_data(...)
        if df.empty:
            logging.warning(f"No data available for {symbol}. Skipping analysis.")
            continue
        ...
    except Exception as e:
        logging.error(f"Error during analysis: {e}")

    logging.info(f"Sleeping for {check_frequency} minutes before the next check...")
    time.sleep(check_frequency * 60)
```

Preflight must happen before entering this loop. Keep the broad exception handling only around the long-running `run` path, not around `check` or `show-config`.

---

### `send_gmail.py` (service, request-response)

**Analog:** `send_gmail.py`

**Service contract** (`send_gmail.py` lines 52-75, 151-165):
```python
def send_email(to_addrs, subject, body, is_html=False, attachments=None,
               html_body=None, text_body=None, inline_images=None):
    config, error = load_config()
    if error:
        return False, error
    ...
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(config["email"], config["app_password"])
        ...
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication failed. Check your app password: {e}"
    except Exception as e:
        return False, f"Failed to send email: {e}"
```

Keep the `(success, message)` contract. Phase 1 bootstrap and `check` can use the same pattern for Gmail-readiness validation without throwing raw tracebacks at the operator.

**MIME assembly pattern** (`send_gmail.py` lines 80-106):
```python
msg = MIMEMultipart('related')
msg["From"] = config["email"]
msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
msg["Subject"] = subject

msg_alternative = MIMEMultipart('alternative')
msg.attach(msg_alternative)
msg_alternative.attach(MIMEText(text_fallback, 'plain', 'utf-8'))
msg_alternative.attach(MIMEText(html_body, 'html', 'utf-8'))
```

Phase 1 should not disturb the existing email payload shape while changing config/bootstrap behavior.

---

### `send_test_email.py` (if retained as thin wrapper; utility, request-response)

**Analog:** `main.py` rather than the current helper internals

**Delegation pattern to copy** (`main.py` lines 1357-1372):
```python
if args.send_test_email:
    success = send_test_email_now(
        symbol=args.symbol,
        source=args.source,
        ...
        email_recipients=email_recipients,
        html_output_path=args.html_output_path
    )
    sys.exit(0 if success else 1)
```

If `send_test_email.py` survives Phase 1, keep it as a trivial wrapper around the unified CLI or shared function only. Do not copy its current manual analysis/plot/email assembly; that script is already known-broken and drifted from `main.py`.

## Shared Patterns

### Guard Clauses And Operator Errors

**Source:** `main.py` lines 34-40, 48-60; `send_gmail.py` lines 29-31, 46-49
**Apply to:** `service_config.py`, `main.py`, `send_gmail.py`
```python
if not EMAIL_RECIPIENTS_FILE.exists():
    logging.warning(f"Email recipients file not found: {EMAIL_RECIPIENTS_FILE}")
    return []

if not os.path.exists(env_file):
    return None, "Gmail not configured..."

if "email" not in config or "app_password" not in config:
    return None, "Gmail configuration incomplete..."
```

### Status Tuple For External I/O

**Source:** `send_gmail.py` lines 73-75, 151-165
**Apply to:** Gmail readiness checks and `test-email` dispatch
```python
config, error = load_config()
if error:
    return False, error

return True, "Email sent successfully"
return False, f"Authentication failed. Check your app password: {e}"
return False, f"Failed to send email: {e}"
```

### Logging And Exit Codes

**Source:** `main.py` lines 15-23, 1357-1372; `send_gmail.py` lines 238-245
**Apply to:** `main.py`, retained wrappers
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("main.log"), logging.StreamHandler()]
)

sys.exit(0 if success else 1)
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.gitignore` | config | file-I/O | The repository currently has no `.gitignore`; derive entries from the phase decisions and `.planning/codebase/CONCERNS.md` (`.env.local`, `config/service.local.json`, `main.log`, `plots/`). |

## Metadata

**Analog search scope:** root-level runtime modules (`main.py`, `send_gmail.py`, `send_test_email.py`) plus phase and codebase reference docs
**Files scanned:** 5 runtime modules, 8 planning refs
**Most recent analog preference:** `main.py` is the newest active entrypoint (2025-12-19), so prefer its conventions over older helper scripts
**Pattern extraction date:** 2026-04-17
