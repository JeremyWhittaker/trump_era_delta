# Requirements: Trump Era Delta

**Defined:** 2026-04-17
**Core Value:** The monitor runs reliably on this machine and delivers trustworthy email alerts when the market crosses meaningful regression bands.

## v1 Requirements

### Configuration

- [x] **CONF-01**: Operator can store non-secret service settings in a project-local config file committed with the repo.
- [x] **CONF-02**: Operator can keep machine-specific secrets out of committed source while the service documents and validates the required secret inputs.
- [x] **CONF-03**: Operator can manage alert recipients from project-local configuration without editing Python code.

### Service Runtime

- [x] **SRVC-01**: Operator can start the monitor from one documented command that validates configuration before entering the monitoring loop.
- [ ] **SRVC-02**: Operator can install and run the monitor as a local background service with documented start, stop, restart, status, and enable commands.
- [ ] **SRVC-03**: Service can restart on failure and resume monitoring with previously persisted alert state.

### Analysis Pipeline

- [ ] **ANLY-01**: Service can load benchmark and current-period market data from the configured local `asset_prices` paths and fail with a clear operator error if the dependency is unavailable.
- [ ] **ANLY-02**: The monitor, test-alert path, and verification commands use the same shared analysis pipeline for data preparation, band calculation, and chart generation.
- [ ] **ANLY-03**: Operator can generate the current comparison report and charts from the refactored service code without manually patching scripts.

### Alerts

- [ ] **ALRT-01**: Operator can send a test alert email to configured recipients and receive it successfully.
- [ ] **ALRT-02**: Service sends a live alert when the monitored regression band changes.
- [ ] **ALRT-03**: Alert emails include the expected rendered summary and inline charts.
- [ ] **ALRT-04**: Service persists last observed and last delivered alert state so restarts do not emit duplicate transition alerts.

### Operations

- [ ] **OPER-01**: Service writes logs and generated artifacts to dedicated runtime paths that do not dirty the source tree.
- [x] **OPER-02**: Operator can run a no-send verification or config-check command before enabling live emails.
- [ ] **OPER-03**: Project includes a smoke-test path that verifies config loading, analysis, chart generation, and email delivery end to end.
- [ ] **OPER-04**: Operator can follow repo documentation to install, configure, test, and enable the service locally without reverse-engineering the scripts.

## v2 Requirements

### Forecasting

- **FCST-01**: The Prophet forecasting workflow is reproducible from the documented install path and maintained as a supported command.

### Integrations

- **INTG-01**: The external `asset_prices` dependency is packaged or wrapped behind a stable local adapter contract.

### Observability

- **OBSV-01**: The service exposes structured health or metrics output for external monitoring tools.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web dashboard or site UI | The user explicitly wants a headless local service for this milestone |
| Cloud or hosted deployment | Local-machine service setup is the immediate target |
| Multi-user auth or admin controls | This is a single-operator workflow |
| Productionizing the experimental forecasting path | Service reliability and alert delivery take priority |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONF-01 | Phase 1 | Complete |
| CONF-02 | Phase 1 | Complete |
| CONF-03 | Phase 1 | Complete |
| SRVC-01 | Phase 1 | Complete |
| OPER-02 | Phase 1 | Complete |
| ANLY-01 | Phase 2 | Pending |
| ANLY-02 | Phase 2 | Pending |
| ANLY-03 | Phase 2 | Pending |
| ALRT-01 | Phase 3 | Pending |
| ALRT-02 | Phase 3 | Pending |
| ALRT-03 | Phase 3 | Pending |
| ALRT-04 | Phase 3 | Pending |
| SRVC-02 | Phase 4 | Pending |
| SRVC-03 | Phase 4 | Pending |
| OPER-01 | Phase 4 | Pending |
| OPER-03 | Phase 5 | Pending |
| OPER-04 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-17*
*Last updated: 2026-04-17 after Phase 1 completion*
