# Roadmap: Trump Era Delta

## Overview

This roadmap turns the current script-oriented market monitor into a maintainable local service with project-local configuration, a shared analysis pipeline, and reliable email alert operations. The work starts by making configuration and bootstrap behavior predictable, then consolidates the duplicated analysis code, hardens alert delivery, installs the monitor as a local service, and ends with smoke verification plus operator handoff.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Configuration Foundation** - Establish project-local config, bootstrap validation, and a clean operator entrypoint
- [ ] **Phase 2: Shared Analysis Core** - Extract the common data, band, and report-generation pipeline out of the current scripts
- [ ] **Phase 3: Alert Reliability** - Make test and live email delivery operational and restart-safe
- [ ] **Phase 4: Local Service Operations** - Package the monitor as a managed local service with clean runtime storage
- [ ] **Phase 5: Verification And Handoff** - Add smoke checks and operator docs so the service can be trusted and maintained

## Phase Details

### Phase 1: Configuration Foundation
**Goal**: Move runtime settings into project-local config, define the secret contract, and provide a single validated bootstrap path for the monitor.
**Depends on**: Nothing (first phase)
**Requirements**: [CONF-01, CONF-02, CONF-03, SRVC-01, OPER-02]
**Success Criteria** (what must be TRUE):
  1. Operator can configure non-secret service settings from files inside the repo without editing Python code.
  2. The startup command validates missing config, missing secrets, and invalid paths before entering the monitoring loop.
  3. Recipients and alert-related settings are read from configuration instead of hard-coded defaults or stale scripts.
  4. Operator can run a no-send validation command to confirm configuration before enabling live emails.
**Plans**: 3/3 plans executed

Plans:
- [x] 01-01: Design the project-local config layout, secret loading rules, and runtime directory contract
- [x] 01-02: Implement a validated bootstrap/CLI entrypoint that loads config and performs preflight checks
- [x] 01-03: Migrate recipient handling and alert-related settings into the new configuration flow

### Phase 2: Shared Analysis Core
**Goal**: Replace duplicated script logic with shared analysis/report modules used by every supported runtime path.
**Depends on**: Phase 1
**Requirements**: [ANLY-01, ANLY-02, ANLY-03]
**Success Criteria** (what must be TRUE):
  1. Market-data loading, period alignment, regression-band calculation, and chart generation are implemented behind one shared service contract.
  2. The monitor and verification commands both execute through the shared analysis path instead of keeping separate copies of the logic.
  3. Missing `asset_prices` dependencies or schema problems fail with actionable operator errors.
  4. Operator can generate the current comparison report from the refactored code without patching helper scripts.
**Plans**: 3 plans

Plans:
- [ ] 02-01: Extract shared data-loading and analysis helpers from `main.py`, `predict_prophet.py`, and `send_test_email.py`
- [ ] 02-02: Extract report and chart generation into reusable functions with a stable result contract
- [ ] 02-03: Rewire supported commands to use the shared analysis core and remove stale call patterns

### Phase 3: Alert Reliability
**Goal**: Restore the test-email path, harden live delivery, and persist alert state so restarts do not create noisy or missing alerts.
**Depends on**: Phase 2
**Requirements**: [ALRT-01, ALRT-02, ALRT-03, ALRT-04]
**Success Criteria** (what must be TRUE):
  1. Operator can trigger a test email and receive it at the configured recipient list.
  2. Live alert emails are sent when the monitored band changes and include the expected rendered summary plus inline charts.
  3. The alert subsystem records enough state to avoid duplicate transition alerts after restart.
  4. Broken helper paths such as the current `send_test_email.py` contract drift are removed or repaired.
**Plans**: 3 plans

Plans:
- [ ] 03-01: Normalize email payload generation and inline-asset handling across test and live alert flows
- [ ] 03-02: Implement persisted alert-state storage and restart-safe transition logic
- [ ] 03-03: Add explicit test-email and live-alert verification commands over the shared pipeline

### Phase 4: Local Service Operations
**Goal**: Install the monitor as a managed local service with reliable restart behavior and clean runtime artifact handling.
**Depends on**: Phase 3
**Requirements**: [SRVC-02, SRVC-03, OPER-01]
**Success Criteria** (what must be TRUE):
  1. Operator can install, start, stop, restart, inspect, and enable the service through documented local service-manager commands.
  2. Logs and generated artifacts are written to dedicated runtime paths that do not clutter tracked source files.
  3. Service restart behavior preserves alert state and resumes monitoring safely after failures.
**Plans**: 3 plans

Plans:
- [ ] 04-01: Define the runtime directory layout, logging behavior, and artifact retention approach
- [ ] 04-02: Create the local service unit and supporting scripts for managed execution
- [ ] 04-03: Validate restart behavior and runtime-path cleanliness under the service workflow

### Phase 5: Verification And Handoff
**Goal**: Leave the project with repeatable smoke checks and operator documentation so the local service can be configured, tested, and trusted.
**Depends on**: Phase 4
**Requirements**: [OPER-03, OPER-04]
**Success Criteria** (what must be TRUE):
  1. The project has a repeatable smoke-check path that exercises config loading, analysis, chart generation, and email delivery.
  2. The README and operator guidance explain how to install, configure, test, start, and enable the service locally.
  3. A new operator can follow the documented workflow without patching source files or guessing runtime behavior.
**Plans**: 2 plans

Plans:
- [ ] 05-01: Add smoke tests or scripted verification commands for the service-critical runtime paths
- [ ] 05-02: Update operator documentation and handoff material for local installation and email verification

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Configuration Foundation | 3/3 | In Progress |   |
| 2. Shared Analysis Core | 0/3 | Not started | - |
| 3. Alert Reliability | 0/3 | Not started | - |
| 4. Local Service Operations | 0/3 | Not started | - |
| 5. Verification And Handoff | 0/2 | Not started | - |
