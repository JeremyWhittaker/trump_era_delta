# Phase 1: Configuration Foundation - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Move runtime settings into project-local config, define the secret contract, and provide a single validated bootstrap path for the monitor. This phase clarifies how the service is configured and started; it does not add new monitoring capabilities or UI.

</domain>

<decisions>
## Implementation Decisions

### Configuration layout
- **D-01:** Store shared non-secret defaults in a committed `config/service.json`.
- **D-02:** Store machine-specific overrides in a gitignored `config/service.local.json`.
- **D-03:** Move recipient management into the new config flow instead of relying on the root `email_recipients.txt` file as the primary source of truth.

### Secret handling
- **D-04:** Use a gitignored project-local `.env.local` as the preferred secret source for Gmail credentials.
- **D-05:** Keep temporary compatibility with the existing `~/.gmail_send/.env` contract during the migration so the service can be brought up without breaking the current machine setup.

### Operator command surface
- **D-06:** Consolidate operator workflows onto a single CLI surface in `main.py` rather than continuing with several equal-status scripts.
- **D-07:** The Phase 1 command surface must support `check`, `run`, `test-email`, and `show-config`.

### Validation behavior
- **D-08:** `check` is a strict no-send preflight that validates config, required paths, recipients, and Gmail readiness.
- **D-09:** `run` must fail fast on invalid config, missing `asset_prices`, unreadable recipients, or broken Gmail configuration when alerts are enabled.
- **D-10:** The service should only enter the monitoring loop when the configured alert path is viable for the chosen settings.

### the agent's Discretion
- Exact JSON schema details and field names inside `config/service.json` and `config/service.local.json`
- Exact precedence order between committed defaults, local overrides, environment overrides, and legacy compatibility fallbacks
- Whether legacy helper scripts remain as thin wrappers during migration or are retired once the unified CLI is stable
- Exact formatting and verbosity of preflight output for `check` and `show-config`

</decisions>

<specifics>
## Specific Ideas

- "I want to get it up and running turn it into a service and make sure the email alerts are working."
- "Headless" and "local machine here as a service" are fixed constraints for this milestone.
- "If I get the email I'll know it's working" is the acceptance check for alert verification.
- "The config can live in this project you decide on the best way to handle everything" grants flexibility on format while keeping project-local config as a requirement.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/PROJECT.md` — project-level constraints, core value, and the decision to keep the milestone headless and local-service-first
- `.planning/REQUIREMENTS.md` — Phase 1 requirements `CONF-01`, `CONF-02`, `CONF-03`, `SRVC-01`, and `OPER-02`
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, and current plan breakdown
- `.planning/STATE.md` — current blockers and current phase position

### Existing codebase constraints
- `.planning/codebase/CONCERNS.md` — existing config debt, broken test-email path, process-local alert state, and operational risks that motivate this phase
- `.planning/codebase/CONVENTIONS.md` — root-level Python module and CLI conventions to preserve during refactor
- `.planning/codebase/STRUCTURE.md` — current script layout and where new shared runtime code can be introduced
- `.planning/codebase/STACK.md` — runtime, dependency, and deployment constraints for the local service

### Current runtime entrypoints
- `main.py` — current monitor CLI, environment-derived config constants, recipient loading, test-email path, and monitor loop
- `send_gmail.py` — current Gmail secret loading and SMTP delivery contract that Phase 1 must adapt

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `main.py::load_email_recipients()` — current file-based recipient loader that can be replaced or adapted behind the new config layer
- `main.py` `argparse` entrypoint — current single-file CLI shape that can evolve into the unified command surface
- `send_gmail.py::load_config()` — existing Gmail credential loading logic to migrate behind the new secret contract
- `send_gmail.py::send_email()` — stable SMTP delivery function that should remain callable from the refactored bootstrap path

### Established Patterns
- The codebase is still a flat root-level Python script layout; Phase 1 should preserve a pragmatic module structure rather than introducing a large framework or package tree all at once.
- Runtime configuration is currently env-driven in `main.py` and file-driven in both `main.py` and `send_gmail.py`; the new config system needs to bridge both patterns cleanly.
- CLI orchestration currently lives in top-level functions and `argparse`, so a unified CLI built from that pattern will fit the existing codebase.
- SMTP operations currently return `(success, message)` tuples in `send_gmail.py`; validation and bootstrap logic should respect that contract unless there is a deliberate refactor.

### Integration Points
- `ASSET_PRICES_REPO`, `ASSET_PRICES_DATA_DIR`, and `ASSET_PRICES_DATA_TYPE` in `main.py` define the data dependency that Phase 1 preflight must validate
- `EMAIL_RECIPIENTS_FILE` and `load_email_recipients()` in `main.py` are the current configuration bridge for recipients
- `send_test_email_now(...)` and `main_loop(...)` in `main.py` are the first runtime paths that should consume the new bootstrap/config contract
- `send_gmail.py::load_config()` is the compatibility point for supporting both `.env.local` and the legacy home-directory secret file during migration

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---
*Phase: 01-configuration-foundation*
*Context gathered: 2026-04-17*
