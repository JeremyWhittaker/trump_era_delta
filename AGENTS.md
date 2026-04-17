<!-- GSD:project-start source:PROJECT.md -->
## Project

- `Trump Era Delta` is a headless local market-monitoring service that compares a current market period against a historical presidential-term benchmark and alerts the operator when regression-band transitions occur.
- Current milestone: refactor the brownfield script set into a maintainable local service with project-local configuration and working email alerts.
- Core value: the monitor must run reliably on this machine and send trustworthy alert emails when the market crosses meaningful bands.
- Keep this milestone focused on the service runtime, shared analysis pipeline, alert delivery, and operator workflow.
- Out of scope for this milestone: web UI, cloud deployment, multi-user admin flows, and full productionization of the experimental forecast path.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

- Primary runtime: Python 3.8+ with `pandas`, `numpy`, `plotly`, `kaleido`, and Gmail SMTP helpers.
- External dependency: local sibling `asset_prices` repository loaded through `ASSET_PRICES_REPO` / `ASSET_PRICES_DATA_DIR`.
- Current runtime shape: root-level Python modules (`main.py`, `send_gmail.py`, `email_template.py`, `predict_prophet.py`, `send_test_email.py`) with no package layout.
- Operational focus for this milestone: project-local config, local service management, persisted alert state, and safe runtime artifact handling.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

- Follow existing Python naming: root-level `snake_case.py` files, `snake_case` functions and variables, `UPPER_SNAKE_CASE` for constants.
- Prefer top-level functions and incremental module extraction over introducing a large class hierarchy.
- Keep imports grouped by standard library, third-party, and local modules, but avoid broad formatting rewrites because no formatter is configured.
- Use guard clauses for invalid runtime state and actionable operator-facing errors at CLI and service boundaries.
- Keep secrets out of the repo; prefer project-local non-secret config plus machine-local secret inputs.
- When refactoring, converge all supported entrypoints on shared analysis and alert contracts instead of patching one script at a time.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

- Current architecture is a script-oriented modular monolith: `main.py` owns orchestration, analysis, plotting, and alert triggering.
- `email_template.py` renders alert content and `send_gmail.py` delivers SMTP mail; `send_test_email.py` and `predict_prophet.py` currently duplicate parts of the main pipeline.
- Runtime state is mostly in-memory DataFrames plus local filesystem artifacts such as charts and logs.
- Refactor work should preserve the local-service shape while extracting shared analysis, plotting, config, and alert modules behind stable contracts.
- Pay attention to existing fragile areas: duplicated analysis logic, process-local alert state, broken test-email behavior, and unmanaged runtime artifacts.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `$gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `$gsd-debug` for investigation and bug fixing
- `$gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `$gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` — do not edit manually.
<!-- GSD:profile-end -->
