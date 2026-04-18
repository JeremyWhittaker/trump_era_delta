---
phase: 01-configuration-foundation
plan: 02
subsystem: cli
tags: [cli, preflight, bootstrap, runtime]
requires:
  - phase: 01-configuration-foundation
    provides: Shared config and Gmail secret loader from 01-01
provides:
  - Unified main.py subcommand surface
  - Shared preflight/import report for config and asset_prices readiness
  - Import-safe CLI entrypoint that does not require the analysis stack for help or config checks
affects: [main.py, service_bootstrap.py, tests/test_main_cli.py]
tech-stack:
  added: []
  patterns: [lazy analysis imports, config-driven CLI bootstrap]
key-files:
  created: [service_bootstrap.py]
  modified: [main.py, tests/test_main_cli.py]
key-decisions:
  - "Moved asset_prices import resolution into service_bootstrap.load_asset_prices_reader instead of importing it at module load."
  - "Made pandas, numpy, and plotly lazy imports so help and preflight commands work without the analysis stack installed."
patterns-established:
  - "CLI commands load config first, build a structured preflight report, and refuse to enter runtime paths when the report is not clean."
  - "show-config renders the merged config through redact_service_config so secret values never reach stdout."
requirements-completed: [SRVC-01, OPER-02]
duration: 7min
completed: 2026-04-17
---

# Phase 1: Configuration Foundation Summary

**`main.py` now exposes validated `check`, `run`, `test-email`, and `show-config` commands over a shared preflight/bootstrap contract instead of relying on import-time globals and one-off flags.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-17T19:31:34-07:00
- **Completed:** 2026-04-18T02:38:06Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `service_bootstrap.py` with structured preflight reporting and runtime `asset_prices` import resolution.
- Rebuilt `main.py` around subcommands so `check`, `show-config`, and `--help` work without importing `asset_prices`, `pandas`, or `plotly` at module load.
- Routed `run` and `test-email` through the same preflight path so they stop before the monitoring loop or one-shot send when config is invalid.
- Added CLI tests for help output, preflight gating, and redacted config rendering.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add shared preflight and runtime import helpers** - `f45e36f` (`feat`)
2. **Task 2: Rebuild `main.py` around the validated subcommand surface** - `9bb67d1` (`test`), `7cb419c` (`feat`)

**Plan metadata:** recorded in this summary commit

## Files Created/Modified

- `service_bootstrap.py` - Shared runtime import helper and structured preflight report builder
- `main.py` - Unified subcommand CLI, lazy analysis imports, config-driven runtime settings, and preflight gating
- `tests/test_main_cli.py` - Unit coverage for bootstrap reporting and CLI command behavior

## Decisions Made

- Kept the analysis math and email-rendering logic in place, but moved runtime wiring and dependency loading behind new bootstrap helpers.
- Treated missing `python` and missing analysis dependencies on this machine as evidence that CLI commands must stay import-safe and lightweight.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed import-time dependency on the analysis stack**
- **Found during:** Task 2 (validated subcommand surface)
- **Issue:** `main.py` could not be imported on this machine because `pandas` was missing, which broke `--help`, `show-config`, and all CLI tests before any command logic ran.
- **Fix:** Moved `pandas`, `numpy`, and `plotly` imports behind `_load_analysis_dependencies()` and shifted `asset_prices` resolution into `service_bootstrap.load_asset_prices_reader(...)`.
- **Files modified:** `main.py`, `service_bootstrap.py`
- **Verification:** `python3 -m unittest tests.test_main_cli -v`, `python3 main.py --help`, `python3 main.py check --help`
- **Committed in:** `7cb419c`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix stayed within Phase 1 scope and made the new CLI usable on a partially configured machine, which matches the operator workflow this phase is establishing.

## Issues Encountered

- The local machine currently lacks `asset_prices`, recipients, and Gmail secrets, so the real `check --json` command was verified against expected failure output rather than a clean pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The monitor now has a stable CLI entrypoint for live runs, no-send preflight, config inspection, and one-shot test-email execution.
- Phase 01-03 can migrate `send_gmail.py`, `send_test_email.py`, and the README onto the new config-backed command surface.

---
*Phase: 01-configuration-foundation*
*Completed: 2026-04-17*
