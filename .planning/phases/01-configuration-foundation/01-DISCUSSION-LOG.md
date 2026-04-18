# Phase 1: Configuration Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 1-configuration-foundation
**Areas discussed:** Config layout, Secret loading, Operator commands, Validation behavior

---

## Config layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single committed config file | Keep all non-secret config in one repo file with minimal layering | |
| Committed defaults + local override file | Use a committed shared config plus a gitignored machine-specific override file | ✓ |
| Multiple purpose-specific files | Split recipients, runtime, and paths into several separate files immediately | |

**User's choice:** Approved recommended default: committed `config/service.json` plus gitignored `config/service.local.json`
**Notes:** The user wants config in the project and explicitly delegated the exact handling approach.

---

## Secret loading

| Option | Description | Selected |
|--------|-------------|----------|
| Environment only | Require all secrets to be passed through shell or service environment variables | |
| Project-local secret file + compatibility fallback | Prefer a gitignored project-local `.env.local` and temporarily support the current home-directory secret file | ✓ |
| Keep home-directory secret file only | Preserve the current `~/.gmail_send/.env` contract as the long-term approach | |

**User's choice:** Approved recommended default: project-local `.env.local` with temporary fallback to `~/.gmail_send/.env`
**Notes:** This keeps secrets out of git while allowing day-1 migration without breaking the current machine.

---

## Operator commands

| Option | Description | Selected |
|--------|-------------|----------|
| One unified CLI in `main.py` | Consolidate `check`, `run`, `test-email`, and `show-config` under one operator entrypoint | ✓ |
| New dedicated CLI file | Build a separate command entrypoint and keep `main.py` narrowly focused | |
| Keep multiple scripts | Continue treating `main.py`, `send_gmail.py`, and `send_test_email.py` as separate primary entrypoints | |

**User's choice:** Approved recommended default: one unified CLI surface in `main.py`
**Notes:** The goal is a service that is easy to run and maintain locally; minimizing operator entrypoints supports that.

---

## Validation behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Strict preflight + fail-fast run | `check` validates everything without sending mail; `run` refuses to start on invalid config or dependencies | ✓ |
| Warning-heavy startup | Start the service even with partial configuration and let runtime warnings surface problems | |
| Mixed mode with soft-fail alerts | Allow degraded startup and only fail when a live alert is attempted | |

**User's choice:** Approved recommended default: strict `check` preflight and fail-fast `run`
**Notes:** The user’s acceptance signal is receiving the alert email, so the startup path must guarantee the alert pipeline is viable before entering service mode.

---

## the agent's Discretion

- Exact field names and schema layout inside the new config files
- Exact precedence order among defaults, local overrides, env overrides, and compatibility fallback
- Whether legacy helper scripts become wrappers or are removed after the unified CLI stabilizes

## Deferred Ideas

None.
