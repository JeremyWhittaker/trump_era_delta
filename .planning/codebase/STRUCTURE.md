# Codebase Structure

**Analysis Date:** 2026-04-17

## Directory Layout

```text
trump_era_delta/
├── .planning/             # GSD planning artifacts
│   └── codebase/          # Generated codebase map documents
├── README.md              # Usage, methodology, data, and deployment guide
├── requirements.txt       # Pinned Python dependencies
├── main.py                # Primary monitoring entry point and core analysis flow
├── email_template.py      # Alert HTML/text rendering helpers
├── send_gmail.py          # Gmail SMTP transport and standalone mail CLI
├── send_test_email.py     # Manual end-to-end alert verification script
├── predict_prophet.py     # Experimental forecasting entry point
└── email_recipients.txt   # Recipient list loaded by `main.py`
```

## Directory Purposes

**Repository Root:**
- Purpose: Hold every executable source module and committed project artifact in a flat layout.
- Contains: Root-level Python scripts, text configuration files, and documentation.
- Key files: `main.py`, `email_template.py`, `send_gmail.py`, `predict_prophet.py`, `send_test_email.py`, `requirements.txt`, `README.md`

**`.planning/`:**
- Purpose: Store planning and orchestration artifacts used by the GSD workflow.
- Contains: Generated analysis documents and other planning outputs.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, plus sibling mapper outputs such as `.planning/codebase/STACK.md`

**`.planning/codebase/`:**
- Purpose: Collect repository reference docs that later planning and execution steps can load directly.
- Contains: Markdown files such as `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/STACK.md`, and `.planning/codebase/INTEGRATIONS.md`
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`

## Key File Locations

**Entry Points:**
- `main.py`: Primary CLI and continuous monitoring loop.
- `predict_prophet.py`: Standalone forecast workflow using Prophet.
- `send_gmail.py`: Standalone SMTP mail-sender CLI.
- `send_test_email.py`: Manual verification script that exercises analysis, plotting, templating, and mail delivery together.

**Configuration:**
- `requirements.txt`: Python dependency lock by exact version pins.
- `README.md`: Runtime usage, environment expectations, and deployment notes.
- `email_recipients.txt`: Default email-recipient list loaded by `load_email_recipients()` in `main.py`.

**Core Logic:**
- `main.py`: Data loading, statistical transforms, band classification, chart generation, and production orchestration.
- `email_template.py`: Alert formatting helpers and `build_email_content(...)`.
- `send_gmail.py`: SMTP credential loading and MIME message assembly.

**Testing:**
- `send_test_email.py`: Current in-repo manual verification path.
- Not detected: A committed automated test directory such as `tests/`, `test/`, or `spec/`.

## Naming Conventions

**Files:**
- Root modules use lowercase snake_case filenames such as `email_template.py`, `predict_prophet.py`, and `send_test_email.py`.
- Text assets and config files stay in the root with descriptive lowercase names such as `requirements.txt` and `email_recipients.txt`.

**Directories:**
- Tooling and workflow directories use dot-prefixed names, as in `.planning/`.
- Runtime-generated output directories use lowercase plural nouns, as described for `plots/` in `README.md` and created by `main.py`, `predict_prophet.py`, and `send_test_email.py`.

## Where to Add New Code

**New Feature:**
- Primary code: If the feature extends the production monitor, add it to `main.py` first or extract it into a new root-level sibling module imported by `main.py`.
- Tests: No automated test location exists; current verification lives in `send_test_email.py`, so add manual verification there unless you introduce a dedicated test harness.

**New Component/Module:**
- Implementation: Add a new root-level snake_case module next to `email_template.py` and `send_gmail.py`; current imports are direct filename imports rather than package-relative imports.

**Utilities:**
- Shared helpers: Place reusable helpers in a new root-level module and import them from `main.py`, `predict_prophet.py`, or `send_test_email.py`; there is no existing `utils/` directory.

## Special Directories

**`.planning/`:**
- Purpose: Project planning workspace and generated reference documents.
- Generated: Yes
- Committed: Not detected

**`.planning/codebase/`:**
- Purpose: Repository-map documents consumed by later GSD commands.
- Generated: Yes
- Committed: Not detected

**`plots/`:**
- Purpose: Runtime output directory for HTML and JPEG chart artifacts written by `main.py`, `predict_prophet.py`, and `send_test_email.py`.
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-04-17*
