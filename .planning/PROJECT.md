# Trump Era Delta

## What This Is

Trump Era Delta is a headless local market-monitoring service that compares current market performance against a historical presidential-term benchmark and alerts the operator when the market crosses meaningful regression-band thresholds. This project is for a single operator running the service on this machine, with configuration stored in the repo and operational email alerts delivered through Gmail.

## Core Value

The monitor runs reliably on this machine and delivers trustworthy email alerts when the market crosses meaningful regression bands.

## Requirements

### Validated

- ✓ Load historical market data from the local `asset_prices` dependency and slice it by configured periods — existing
- ✓ Calculate cumulative performance series, regression bands, and current band classification for a configured symbol — existing
- ✓ Generate Plotly HTML and JPEG comparison artifacts for the monitored period — existing
- ✓ Compose HTML/text alert content and send Gmail-based notification emails — existing
- ✓ Run the monitor from a CLI entrypoint with configurable symbol, dates, source, and polling interval — existing
- ✓ Phase 1: Store non-secret runtime settings in committed `config/service.json` with optional local overrides in `config/service.local.json`
- ✓ Phase 1: Load Gmail secrets from `.env.local` with validation and redacted config inspection
- ✓ Phase 1: Use one validated CLI surface for `check`, `run`, `test-email`, and `show-config`
- ✓ Phase 1: Manage alert recipients from config instead of committed source files

### Active

- [ ] Refactor the script-oriented codebase into a maintainable local background service with a clear operator workflow.
- [ ] Make the alert pipeline operational end to end, including successful test-email delivery and restart-safe live alerting.
- [ ] Consolidate duplicated analysis, plotting, and email wiring into shared code that powers the monitor and verification paths.
- [ ] Add smoke-check and operator documentation paths so the service can be configured and trusted without source edits.

### Out of Scope

- Web dashboard or site UI — this milestone is explicitly headless and local-service-first
- Cloud or hosted deployment — the first target is this local machine as a service
- Multi-user auth, admin controls, or operator portal — this is a single-operator workflow
- Full productionization of the experimental Prophet forecasting path — service reliability and email delivery come first

## Context

The current repository is a brownfield Python codebase with a flat root-level script layout: `main.py` runs the monitor loop, `email_template.py` renders alerts, `send_gmail.py` sends Gmail SMTP mail, `send_test_email.py` is now a thin wrapper into the validated CLI, and `predict_prophet.py` is an experimental forecast script. Phase 1 completed the configuration foundation by moving settings into repo-local config files, defining the Gmail secret contract, and consolidating operator entrypoints under `main.py`. The codebase map in `.planning/codebase/` still shows duplicated analysis logic, process-local alert state, unmanaged runtime artifacts, and no automated smoke coverage.

The service depends on a sibling `asset_prices` repository for parquet-backed market data. Gmail delivery currently depends on credentials outside the repo, while recipient addresses and other runtime behavior are partially encoded in root-level files and CLI flags. The user’s success signal for this milestone is concrete: if a configured test alert email arrives, the email side is working.

## Constraints

- **Runtime**: Headless local service only — no web UI in this milestone
- **Deployment**: Local machine first — the service should run here under a standard service manager workflow
- **Configuration**: Non-secret config should live in this project — the operator should not need to edit Python code to run it
- **Secrets**: Credentials must stay out of committed source — Gmail secrets should remain machine-local or environment-based
- **Dependency**: Existing local `asset_prices` integration must keep working during the refactor — it is required for market data access

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Refactor toward a headless service rather than build a web UI | The user explicitly wants the project running locally as a service, and reliable operations matter more than a dashboard right now | Locked in Phase 1 roadmap and scope |
| Keep configuration centered in project-local files with secrets separated | The user wants config in the repo, but committed secrets would be unsafe | Implemented in Phase 1 via `config/service.json`, `config/service.local.json`, and `.env.local` |
| Treat receipt of a configured test email as the primary operational acceptance check | The user wants a direct proof that alerts work end to end | Still the acceptance rule for alert-reliability work |
| Focus the milestone on the monitor, alert path, and operator workflow before forecast productionization | The forecast script is experimental and not part of the requested service outcome | Confirmed by the Phase 1-5 roadmap |

## Current State

Phase 1 is complete. The project now has a validated configuration/bootstrap layer, redacted config inspection, strict no-send preflight, and a single CLI surface for live runs and test-email execution. The next priority is extracting the duplicated analysis/report path into shared code before making live alerts restart-safe and packaging the monitor as a managed local service.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-17 after Phase 1 completion*
