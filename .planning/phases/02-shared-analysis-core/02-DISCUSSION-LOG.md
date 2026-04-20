# Phase 2: Shared Analysis Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 02-shared-analysis-core
**Areas discussed:** Forecast integration, One-shot report workflow, Output compatibility, Failure policy

---

## Forecast integration

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Prophet fully separate | Leave forecast code duplicated and refactor only the monitor path | |
| Share prep helpers, keep Prophet modeling isolated | Reuse shared loading/alignment/report helpers without pulling the experimental forecasting model into the supported core | ✓ |
| Fully absorb Prophet into the shared core | Treat forecasting as a first-class supported workflow now | |

**User's choice:** Accepted the recommended approach.
**Notes:** Forecasting remains experimental in this milestone. Shared prep is desired; forecast productionization is not.

---

## One-shot report workflow

| Option | Description | Selected |
|--------|-------------|----------|
| Internal refactor only | Extract shared helpers but do not expose a new operator command | |
| Add a supported no-email report command | Make the shared core directly usable for chart/report generation without sending email | ✓ |
| Keep report generation tied to `test-email` and `run` | Avoid a new supported command surface in Phase 2 | |

**User's choice:** Accepted the recommended approach.
**Notes:** The shared core should be directly callable through the supported `main.py` CLI, not only indirectly through alert paths.

---

## Output compatibility

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve semantics exactly, minimal cleanup only | Keep the same statistical meaning and alert-facing behavior while extracting the core | ✓ |
| Allow moderate chart/report cleanup | Keep methodology but take visible liberties with output presentation during extraction | |
| Redesign charts and methodology while refactoring | Use the refactor to change presentation and interpretation at the same time | |

**User's choice:** Accepted the recommended approach.
**Notes:** Phase 2 is a structural refactor, not a methodology or visual redesign phase.

---

## Failure policy

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-fail supported commands on invalid data/dependencies | Surface clear operator errors for service, test, and report commands | ✓ |
| Produce partial output where possible | Try to keep commands running even with incomplete or invalid analysis inputs | |
| Mixed policy across all commands | Decide case-by-case without a strict default | |

**User's choice:** Accepted the recommended approach.
**Notes:** Best-effort behavior is reserved for explicitly experimental workflows only.

---

## the agent's Discretion

- Exact shared module names and file boundaries
- Exact result-contract shape for the shared analysis/report helpers
- Exact CLI name for the one-shot no-email report command

## Deferred Ideas

- Full Prophet productionization remains deferred to v2.
- Alert-state persistence remains Phase 3 work.
- Local service-manager packaging remains Phase 4 work.
