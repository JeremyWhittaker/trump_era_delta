# Codebase Concerns

**Analysis Date:** 2026-04-17

## Tech Debt

**Shared analysis logic is duplicated across entrypoints:**
- Issue: Data loading, date slicing, cumulative-return calculation, day alignment, and regression-band preparation are implemented separately in `main.py`, `predict_prophet.py`, and `send_test_email.py` instead of behind one shared API.
- Files: `main.py`, `predict_prophet.py`, `send_test_email.py`
- Impact: Small interface changes break secondary scripts, and bug fixes must be copied into multiple places. The broken `plot_comparison` call in `send_test_email.py` shows the current drift.
- Fix approach: Extract a shared analysis module that returns a stable result object for the monitoring loop, forecast script, and test-email path.

**Alert delivery state is process-local only:**
- Issue: The last-seen regression band lives only in the `previous_band` variable inside `main_loop`, with no persisted state, no delivery ledger, and no replay-safe idempotency key.
- Files: `main.py`
- Impact: Restarting the process drops alert state, suppresses the first alert after startup, and leaves no audit trail of which transitions were delivered.
- Fix approach: Persist the last observed band and last delivered alert to disk or a small datastore, then load it before entering the loop.

**Generated runtime artifacts are unmanaged:**
- Issue: The service writes `main.log` and repeated chart outputs into `./plots`, but the repository root currently has no `.gitignore` even though `README.md` documents one.
- Files: `main.py`, `predict_prophet.py`, `README.md`
- Impact: Long-running instances accumulate logs and images in the repo working tree, making accidental commits and disk growth likely.
- Fix approach: Add a real `.gitignore`, move runtime artifacts to a dedicated data directory, and rotate or cap logs.

**Return math is labeled as cumulative return while using additive percent changes:**
- Issue: The main analysis computes `pct_change().fillna(0).cumsum()` and treats the result as cumulative return instead of compounded return.
- Files: `main.py`, `predict_prophet.py`, `README.md`
- Impact: Over long windows the reported performance and regression thresholds drift away from true compounded performance, which changes alert semantics.
- Fix approach: Decide whether the metric is an additive regime score or a true cumulative return, then rename it or switch to compounded math consistently across code and docs.

## Known Bugs

**`send_test_email.py` cannot unpack the current plot API:**
- Symptoms: Running the script raises an unpacking error because it expects two return values from `plot_comparison`.
- Files: `send_test_email.py`, `main.py`
- Trigger: Execute `python3 send_test_email.py`.
- Workaround: Use `main.py --send_test_email` instead of `send_test_email.py` until the helper script is updated.

**`send_test_email.py` attaches the wrong inline image CID for the HTML template:**
- Symptoms: Even after fixing the unpacking error, the generated HTML references `cid:chart_zoomed` and `cid:chart_full` while the script only attaches `cid:chart`, so the chart images do not render correctly.
- Files: `send_test_email.py`, `email_template.py`
- Trigger: Execute `python3 send_test_email.py` after patching the tuple unpacking.
- Workaround: Use `main.py --send_test_email`, which attaches the CIDs expected by `build_email_content`.

**`predict_prophet.py` is not reproducible from `requirements.txt`:**
- Symptoms: A fresh environment built from `requirements.txt` cannot import `Prophet`.
- Files: `predict_prophet.py`, `requirements.txt`
- Trigger: Install dependencies from `requirements.txt` and then run `python3 predict_prophet.py ...`.
- Workaround: Manually install `prophet` and its native build requirements outside the repo manifest.

**CLI flags that look optional are effectively always enabled:**
- Symptoms: `--plot_bands` and `--email_notifications` are declared with `action='store_true'` and `default=True`, so there is no CLI path that disables them.
- Files: `main.py`
- Trigger: Run `python3 main.py` expecting omitted flags to leave plotting or email disabled.
- Workaround: Edit the defaults in code; there is no negative flag such as `--no-email-notifications`.

## Security Considerations

**Real recipient addresses are committed in the repository:**
- Risk: The checked-in recipient list contains live email addresses, and the monitoring loop reads them automatically when `--email_recipients` is omitted.
- Files: `email_recipients.txt`, `main.py`
- Current mitigation: SMTP credentials are stored outside the repo in `~/.gmail_send/.env`.
- Recommendations: Replace `email_recipients.txt` with a sample file, load real recipients from local config or environment, and keep the committed file address-free.

**The standalone test-mail script hard-codes a personal recipient:**
- Risk: Any machine with valid Gmail credentials can send an unsolicited test alert to the hard-coded address.
- Files: `send_test_email.py`
- Current mitigation: None inside the script.
- Recommendations: Require an explicit `--to` argument for test sends and refuse to run if no recipient is provided.

**The monitor swallows all exceptions and keeps running:**
- Risk: Authentication failures, schema breaks, import failures after startup, or template/render errors are logged but do not fail the process, so an external supervisor can see a healthy service while alerts are effectively dead.
- Files: `main.py`
- Current mitigation: Log messages to stdout and `main.log`.
- Recommendations: Separate transient and fatal errors, fail fast on repeated fatal conditions, and expose a health signal that indicates whether the last successful analysis completed.

**The external reader is imported from an arbitrary filesystem path inserted into `sys.path`:**
- Risk: The process imports `lib.read_utils` from whatever `ASSET_PRICES_REPO` path is configured, without version pinning or package-level trust boundaries.
- Files: `main.py`, `predict_prophet.py`
- Current mitigation: Import-time failure if the module is missing.
- Recommendations: Package the dependency, pin a version, and validate that the configured path points to the expected project before import.

## Performance Bottlenecks

**The full historical dataset is reloaded on every polling cycle:**
- Problem: Each loop reads data from the earliest configured date through the current end date rather than caching or appending new rows.
- Files: `main.py`, `predict_prophet.py`
- Cause: `load_data` is called with the full range on every run, and no incremental state is stored between iterations.
- Improvement path: Cache the cleaned historical frame in memory, append only new observations, or precompute the fixed reference-period baseline once at startup.

**Chart rendering runs even when no alert is sent:**
- Problem: The loop generates two high-resolution JPEGs and one HTML report before it knows whether the regression band changed.
- Files: `main.py`
- Cause: `plot_comparison` is executed ahead of change detection and writes all artifacts on every cycle.
- Improvement path: Compute the band transition first, then render charts only on a band change or on a scheduled snapshot interval.

**Runtime storage grows without any retention policy:**
- Problem: Continuous writes to `main.log` and `./plots` have no pruning, rotation, or retention cap.
- Files: `main.py`, `predict_prophet.py`
- Cause: The service appends logs forever and overwrites or recreates plot outputs in the repo workspace.
- Improvement path: Add log rotation, move plots outside the repo, and delete stale artifacts on a fixed schedule.

## Fragile Areas

**`send_test_email.py` is coupled to internal details of `main.py` and `email_template.py`:**
- Files: `send_test_email.py`, `main.py`, `email_template.py`
- Why fragile: The script depends on `plot_comparison` return arity and the exact inline-image CID names expected by the HTML template, and both contracts are implicit.
- Safe modification: Treat plotting and email-body generation as one shared interface rather than reassembling them manually in helper scripts.
- Test coverage: No smoke test covers this entrypoint.

**The period-alignment and band-selection path has no guardrails around edge cases:**
- Files: `main.py`, `predict_prophet.py`
- Why fragile: Date parsing, timezone localization, truncation to matched trading days, regression fitting, and band classification are hand-wired across several functions with no invariant checks beyond empty-frame handling.
- Safe modification: Add explicit guards for overlong comparison windows, invalid ranges, and missing regression columns before changing any band logic.
- Test coverage: No automated tests exercise band boundaries, date alignment, or timezone handling.

**Mail composition relies on string conventions instead of typed contracts:**
- Files: `send_gmail.py`, `email_template.py`, `main.py`
- Why fragile: Inline image CIDs, HTML sections, and text fallbacks are linked by string literals, so template changes can break rendering without any compile-time signal.
- Safe modification: Introduce a structured payload for template outputs and validate required inline assets before calling SMTP send.
- Test coverage: No snapshot or integration tests cover rendered email content.

## Scaling Limits

**The current-vs-reference comparison has a hard horizon:**
- Current capacity: The comparison is only coherent while `len(df_new)` is less than or equal to the available reference-period history in `df_original`.
- Limit: `df_original_truncated = df_original.iloc[:num_days_new]` silently truncates the reference side; once the current period outlasts the original term, the monitor has no same-length historical baseline to compare against.
- Scaling path: Stop with an explicit operator error when the current period exceeds the reference window, or redesign the model around normalized calendar regimes instead of a fixed single term.

**Operational history retention is bounded only by local disk:**
- Current capacity: Log and plot retention are effectively infinite until the host filesystem fills up.
- Limit: `main.log` and generated plots live in the repo workspace with no lifecycle management.
- Scaling path: Add artifact retention, move outputs to a managed runtime directory, and monitor disk use as part of deployment.

## Dependencies at Risk

**Sibling `asset_prices` repository:**
- Risk: The project depends on a local checkout outside this repo and imports it by path instead of through a versioned package boundary.
- Impact: Startup fails if the path changes, the external repo is missing, or `lib.read_utils` changes its API or schema expectations.
- Migration plan: Publish `asset_prices` as an installable package or wrap the external reader behind a local adapter with a pinned contract.

**`prophet`:**
- Risk: `predict_prophet.py` imports `Prophet`, but `requirements.txt` does not install it and the package is nontrivial to build in minimal environments.
- Impact: The forecast entrypoint is not reproducible from the repository's documented install path.
- Migration plan: Add a supported dependency lock and install notes, or remove the script until the forecast path is maintained.

## Missing Critical Features

**No automated test suite or smoke-check harness:**
- Problem: There is no `pytest` or `unittest` coverage for the core analysis pipeline, email rendering, or CLI entrypoints.
- Blocks: Safe refactoring of regression logic, plotting, and notification flow.

**No persisted alert history or idempotency mechanism:**
- Problem: The service does not record which band transitions have been delivered.
- Blocks: Reliable restart behavior, operator auditing, and replay-safe notifications.

**No operator-safe dry-run mode for the main monitor:**
- Problem: The current CLI exposes only always-on `store_true` flags for band plotting and email notifications.
- Blocks: Running chart generation or data validation in production environments without risking outbound mail.

## Test Coverage Gaps

**Regression and band math are untested:**
- What's not tested: `calculate_cumulative_pct_change`, `calculate_regression_bands`, and `get_regression_band`, including date filters, timezone alignment, and band-boundary behavior.
- Files: `main.py`, `predict_prophet.py`
- Risk: Statistical regressions can change alert behavior without detection.
- Priority: High

**Email rendering and SMTP payload assembly are untested:**
- What's not tested: `build_email_content`, inline image CID consistency, recipient loading, and multipart message generation.
- Files: `email_template.py`, `send_gmail.py`, `main.py`
- Risk: Production alerts can render without charts, with broken HTML, or with malformed MIME structure.
- Priority: High

**CLI entrypoints have no smoke coverage:**
- What's not tested: `main.py --send_test_email`, the continuous monitoring entrypoint in `main.py`, `predict_prophet.py`, and `send_test_email.py`.
- Files: `main.py`, `predict_prophet.py`, `send_test_email.py`
- Risk: Script-level breakage ships unnoticed, as shown by the stale `send_test_email.py` contract.
- Priority: High

---

*Concerns audit: 2026-04-17*
