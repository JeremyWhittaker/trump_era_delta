# Phase 3: Alert Reliability - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Make test and live email delivery operational and restart-safe. This phase covers real SMTP verification, shared test/live alert payload wiring, persisted alert state, and retry/idempotency behavior for regression-band transitions. It does not install the service under a manager, redesign the email format, or add the end-to-end smoke harness from the later verification phase.

</domain>

<decisions>
## Implementation Decisions

### Test-email verification
- **D-01:** `main.py test-email` remains the operator acceptance path and must send a real email through the same SMTP path used by live alerts.
- **D-02:** Test-email uses the configured recipient list from project config by default; Phase 3 does not introduce a separate hard-coded verification address.
- **D-03:** Test-email should reuse the same rendered HTML/text body and inline-chart contract as live alerts, with only explicit test labeling in the subject or surrounding metadata.

### Alert state persistence
- **D-04:** Alert state must persist in project-local runtime storage, not in memory and not in committed config.
- **D-05:** Persist both the last observed band and the last successfully delivered transition metadata so restart behavior can distinguish "already sent" from "observed but not delivered."

### Delivery and restart semantics
- **D-06:** A live alert counts as delivered only after SMTP success; failed sends remain pending and must not advance the delivered-state marker.
- **D-07:** On restart, the service must not re-send already delivered transitions, but it should resume any pending undelivered transition once a valid analysis cycle runs again.
- **D-08:** Phase 3 should prefer deterministic local retry behavior over best-effort fire-and-forget or blanket process crashes on a single send failure.

### Payload compatibility
- **D-09:** Test and live alert paths should converge on one normalized payload builder and inline-image contract instead of keeping separate composition branches.
- **D-10:** Preserve the current chart, band, and interpretation semantics from Phase 2; Phase 3 is a delivery-reliability phase, not a methodology or template redesign.

### the agent's Discretion
- Exact runtime file name, on-disk schema, and atomic-write strategy for persisted alert state
- Exact retry cadence and whether retry bookkeeping is keyed by band number alone or by a richer transition identifier
- Whether the persisted state lives in JSON or another lightweight local format, as long as it remains single-operator and restart-safe

</decisions>

<specifics>
## Specific Ideas

- The user's operational acceptance check remains concrete: "If I get the email I'll know it's working."
- The project is still headless, local-machine-first, and config-driven from inside the repo.
- Phase 2 already added `main.py report`; Phase 3 should build on the shared analysis/report path instead of branching away from it.
- The user asked to proceed without extra back-and-forth, so the recommended defaults above were selected directly for this phase discussion.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and carry-forward constraints
- `.planning/PROJECT.md` — current milestone constraints, acceptance signal, and active focus after Phase 2
- `.planning/REQUIREMENTS.md` — Phase 3 requirements `ALRT-01`, `ALRT-02`, `ALRT-03`, and `ALRT-04`
- `.planning/ROADMAP.md` — Phase 3 goal, success criteria, and planned work breakdown
- `.planning/STATE.md` — current blockers and active phase position
- `.planning/phases/01-configuration-foundation/01-CONTEXT.md` — locked config, secret, and CLI-entrypoint decisions that Phase 3 must preserve
- `.planning/phases/02-shared-analysis-core/02-CONTEXT.md` — locked shared-core and failure-policy decisions that Phase 3 must build on
- `.planning/phases/02-shared-analysis-core/02-VERIFICATION.md` — verified Phase 2 behavior and current shared-core evidence

### Existing code and architecture
- `.planning/codebase/CONCERNS.md` — alert-state fragility, email payload risks, and current restart/idempotency gaps that motivate this phase
- `.planning/codebase/CONVENTIONS.md` — root-level module/function conventions and current error/logging style
- `.planning/codebase/STRUCTURE.md` — entrypoint layout and where shared/local runtime code fits
- `.planning/codebase/STACK.md` — runtime and dependency constraints, including SMTP, Plotly, and the `asset_prices` dependency

### Current runtime paths
- `main.py` — supported `run`, `report`, and `test-email` paths plus the current in-loop alert trigger behavior
- `send_gmail.py` — SMTP send contract and multipart/inline-image handling
- `email_template.py` — HTML/text alert payload builder and current inline-image expectations
- `report_pipeline.py` — shared report artifact contract that Phase 3 should reuse instead of replacing
- `analysis_core.py` — shared analysis contract that must stay authoritative for test/live alert flows
- `service_config.py` — current alert config and recipient validation rules
- `requirements.txt` — declared Python runtime dependencies that should stay aligned with any alert-reliability work

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `main.py::_send_band_email(...)` — existing shared helper for HTML/text payload generation and SMTP sending that can become the single alert-delivery path
- `main.py::send_test_email_now(...)` — current one-shot test-email path already routed through the shared analysis/report core
- `main.py::main_loop(...)` — current live alert trigger point, still driven by in-memory `previous_band`
- `send_gmail.py::send_email(...)` — stable `(success, message)` SMTP contract with inline-image support
- `email_template.py::build_email_content(...)` — current HTML/text payload builder that both test and live paths should share
- `service_config.py` validation for `alerts.enabled` and `alerts.recipients` — existing config contract that should remain authoritative

### Established Patterns
- Supported operator workflows now live under `main.py`; Phase 3 should not create a new primary alert-entry script.
- Shared analysis/report generation already lives in `analysis_core.py` and `report_pipeline.py`; alert work should reuse those contracts rather than duplicating data prep.
- SMTP delivery is already modeled as success/failure tuples, which fits persisted retry bookkeeping without changing the mail transport API.
- Operator-facing supported commands still prefer strict failures and explicit log messages over silent degraded behavior.

### Integration Points
- Replace `previous_band`-only process memory in `main_loop(...)` with persisted state loaded before the loop and updated after observation/delivery milestones.
- Keep `send_test_email_now(...)` on the same payload and inline-image builder as live alerts so test-email proves the real path.
- Thread persisted delivery state through `_send_band_email(...)` or its immediate caller so successful sends and failures can update disk state deterministically.
- Keep `report_pipeline.py` and `email_template.py` as the shared chart/payload sources for both test and live alerts instead of adding separate test-only formatting.

</code_context>

<deferred>
## Deferred Ideas

- Managed background-service installation, restart policy, and runtime directory operations remain Phase 4 work.
- Smoke-test harnesses and operator handoff material remain Phase 5 work.
- Forecast productionization remains deferred to v2.

</deferred>

---
*Phase: 03-alert-reliability*
*Context gathered: 2026-04-19*
