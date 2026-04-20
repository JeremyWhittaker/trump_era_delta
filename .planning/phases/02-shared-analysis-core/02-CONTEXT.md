# Phase 2: Shared Analysis Core - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace duplicated analysis and report-generation logic with shared modules used by the supported runtime paths. This phase covers shared data loading, period alignment, regression-band preparation, chart/report assembly, and a supported one-shot report workflow. It does not yet make alert delivery restart-safe, install the service under a manager, or productionize the experimental Prophet path.

</domain>

<decisions>
## Implementation Decisions

### Forecast integration
- **D-01:** The shared core should own reusable data-loading, period-slicing/alignment, and report/chart preparation helpers that can be used by both the monitor and the forecast script.
- **D-02:** `predict_prophet.py` should reuse those shared helpers where they fit, but Prophet-specific modeling and forecast-only visualization stay isolated from the shared core in this phase.
- **D-03:** Full forecast productionization remains out of scope for this phase.

### One-shot report workflow
- **D-04:** Phase 2 should add a supported no-email one-shot report/charts path instead of keeping shared analysis reachable only through `run` and `test-email`.
- **D-05:** That one-shot path must live under the `main.py` command surface introduced in Phase 1 and use the same config/bootstrap contract.

### Output compatibility
- **D-06:** Preserve the current statistical behavior, band classification semantics, and alert-facing meaning while extracting the shared core.
- **D-07:** Output cleanup in this phase should be minimal and refactor-driven; this is not a chart redesign or methodology-change phase.

### Failure policy
- **D-08:** Supported service/test/report commands must hard-fail with clear operator-facing errors when `asset_prices`, date windows, or required data are invalid or incomplete.
- **D-09:** Best-effort or partial-output behavior is acceptable only for explicitly experimental paths such as Prophet exploration, not for the supported service commands.

### the agent's Discretion
- Exact module boundaries, filenames, and helper names for the shared analysis core
- Exact shape of the shared result contract, as long as it is stable across supported commands
- Exact name of the new one-shot report subcommand, as long as it stays under `main.py` and is clearly no-email

</decisions>

<specifics>
## Specific Ideas

- The user accepted the recommended defaults for all discussed Phase 2 gray areas.
- Current duplication is concentrated in `main.py` and `predict_prophet.py`; `send_test_email.py` is already a thin wrapper and should stay thin.
- The shared core should become the only supported path for data preparation, regression-band math, and chart/report generation across operator-facing commands.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and carry-forward constraints
- `.planning/PROJECT.md` — milestone constraints, headless-service goal, and current state after Phase 1
- `.planning/REQUIREMENTS.md` — Phase 2 requirements `ANLY-01`, `ANLY-02`, and `ANLY-03`
- `.planning/ROADMAP.md` — Phase 2 goal, success criteria, and plan breakdown (`02-01`, `02-02`, `02-03`)
- `.planning/STATE.md` — current blockers and active project position
- `.planning/phases/01-configuration-foundation/01-CONTEXT.md` — locked Phase 1 decisions around config, secrets, CLI surface, and preflight behavior that Phase 2 must preserve
- `.planning/phases/01-configuration-foundation/01-VERIFICATION.md` — verified Phase 1 behavior that shared-core work must not regress

### Existing code and architecture
- `.planning/codebase/CONCERNS.md` — duplicated analysis logic, fragile entrypoints, and hard-fail expectations that motivate this phase
- `.planning/codebase/CONVENTIONS.md` — root-level module/function conventions and existing error/logging patterns
- `.planning/codebase/STRUCTURE.md` — current entrypoints and where shared modules can be introduced
- `.planning/codebase/STACK.md` — runtime and dependency constraints, including `asset_prices`, `pandas`, `plotly`, and `kaleido`

### Current runtime paths
- `main.py` — current supported analysis, band, plotting, and runtime orchestration path
- `predict_prophet.py` — duplicate data-loading/alignment/plotting path that should partially converge on the shared core
- `send_test_email.py` — thin wrapper contract that should remain thin
- `email_template.py` — current report/email rendering contract whose inputs and semantics should remain stable through this refactor

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `main.py::load_data(...)` — already adapted to the `asset_prices` reader contract and usable as a starting point for shared input loading
- `main.py::calculate_cumulative_pct_change(...)`, `calculate_regression_bands(...)`, and `get_regression_band(...)` — current statistical core that should move behind a shared contract
- `main.py::_prepare_analysis_frames(...)` — recent helper that already groups part of the reusable analysis path
- `main.py::plot_comparison(...)` — current supported chart/report artifact generator
- `predict_prophet.py::load_data(...)`, `prepare_aligned_data(...)`, and `plot_comparison(...)` — duplicate logic and naming drift that show where convergence is needed
- `service_config.py` / `service_bootstrap.py` — Phase 1 bootstrap/config contract that all new commands should continue using

### Established Patterns
- Supported operator workflows now live under `main.py`; helper scripts should stay thin wrappers instead of growing new logic.
- The repository still prefers root-level `snake_case.py` modules and top-level functions rather than a large package tree.
- The supported runtime path now expects strict preflight before analysis commands run, and lazy imports are already in place for the analysis stack.
- Error handling in supported runtime paths should be explicit and operator-facing, not silent best-effort behavior.

### Integration Points
- `main.py::main_loop(...)` and `main.py::send_test_email_now(...)` should call shared analysis/report helpers instead of assembling the pipeline inline.
- `main.py` should gain a supported one-shot no-email report command over the same shared core.
- `predict_prophet.py` should import shared loaders/alignment/report-prep helpers, then layer Prophet-specific work on top.
- `email_template.py` should continue receiving semantically equivalent statistical inputs until the later alert-focused phase intentionally revisits payload generation.

</code_context>

<deferred>
## Deferred Ideas

- Full Prophet productionization remains deferred to v2.
- Persisted alert state and restart-safe alert delivery belong to Phase 3.
- Managed service installation, restart policy, and runtime directory operations belong to Phase 4.

</deferred>

---
*Phase: 02-shared-analysis-core*
*Context gathered: 2026-04-19*
