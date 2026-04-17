# Coding Conventions

**Analysis Date:** 2026-04-17

## Naming Patterns

**Files:**
- Use root-level `snake_case.py` module names such as `main.py`, `send_gmail.py`, `email_template.py`, `predict_prophet.py`, and `send_test_email.py`.
- Keep single-purpose modules at the repository root. The current codebase does not use packages, nested modules, or `__init__.py` exports.

**Functions:**
- Use `snake_case` for all functions, with verb-first names for behavior (`load_data`, `calculate_regression_bands`, `plot_comparison`, `build_email_content`, `send_email`).
- Prefer top-level functions over classes. All reusable behavior currently lives in module-level functions in `main.py`, `email_template.py`, `send_gmail.py`, and `predict_prophet.py`.
- Long orchestration helpers are acceptable in this codebase when they mirror a CLI workflow, as seen in `main.py` (`send_test_email_now`, `main_loop`) and `send_gmail.py` (`main`).

**Variables:**
- Use `snake_case` for local variables and parameters (`current_band`, `html_output_path`, `email_recipients`, `latest_cumulative_pct_change`).
- Use `UPPER_SNAKE_CASE` only for module constants and environment-derived configuration such as `ASSET_PRICES_REPO`, `ASSET_PRICES_DATA_DIR`, `DEFAULT_DATA_TYPE`, and `EMAIL_RECIPIENTS_FILE` in `main.py`.
- Keep temporary DataFrame names short and semantic (`df`, `df_new`, `df_original`, `df_original_truncated`) in data-processing paths.

**Types:**
- Add type hints only where the surrounding module already uses them. `email_template.py` uses typed signatures (`Dict[str, float]`, `Optional[str]`, `Tuple[str, str]`); `main.py`, `send_gmail.py`, and `predict_prophet.py` are largely untyped.
- Do not introduce dataclasses, protocols, or custom type aliases unless the target module is already moving toward stronger typing.

## Code Style

**Formatting:**
- Tool used: Not detected. No `pyproject.toml`, `ruff`, `black`, `isort`, `flake8`, or formatter config files are present in the repository root.
- Key settings: Manual formatting only.
- Use 4-space indentation and keep function bodies visually segmented with blank lines and section comments, matching `main.py` and `send_gmail.py`.
- Match the file’s existing quote style instead of normalizing globally. The codebase mixes single and double quotes within the same module (`main.py`, `email_template.py`, `send_gmail.py`).
- Preserve multi-line call formatting with one argument per line when signatures are long, as used in `main.py` and `send_test_email.py`.

**Linting:**
- Tool used: Not detected.
- Key rules: The effective style is enforced by code review and local discipline rather than tooling.
- Avoid large-scale formatting rewrites in existing files. Follow surrounding style because there is no automated formatter to reconcile differences.

## Import Organization

**Order:**
1. Standard library imports at the top of the module (`os`, `sys`, `argparse`, `logging`, `time`, `datetime`, `pathlib`, `shutil`, `smtplib`, `email.*`).
2. Third-party imports next or interleaved manually (`pandas`, `numpy`, `plotly`, `prophet`).
3. Local project imports last in the import block (`from send_gmail import send_email`, `from email_template import build_email_content`, `from main import ...`).

**Path Aliases:**
- None. Modules import each other by direct filename from the repository root.
- External repo access is handled by mutating `sys.path` to include `ASSET_PRICES_REPO` before importing `lib.read_utils.read_symbol_data` in `main.py` and `predict_prophet.py`.

**Guidance:**
- There is no enforced import sorter. Keep new imports adjacent to the existing groups in the file you touch rather than reordering the entire block.

## Error Handling

**Patterns:**
- Use guard clauses for expected invalid states:
  - Missing files return safe defaults in `main.py` (`load_email_recipients` returns `[]`).
  - Empty datasets trigger warnings or `ValueError` in `main.py` and `predict_prophet.py`.
  - Missing Gmail config returns `(None, error_message)` in `send_gmail.py`.
- Raise explicit exceptions for unrecoverable data-contract failures:
  - `ImportError` when `asset_prices` cannot be imported in `main.py` and `predict_prophet.py`.
  - `ValueError` when required columns or date-range data are missing in `main.py` and `predict_prophet.py`.
- Return `(success, message)` tuples for SMTP operations in `send_gmail.py`, and let CLI callers decide whether to `print`, `logging.error`, or `sys.exit(1)`.
- Use broad `except Exception as e` only at CLI or loop boundaries where the process must continue running, as in `main.py`’s monitoring loop and `send_gmail.py`’s SMTP send block.

## Logging

**Framework:** `logging` in long-running/production paths, `print` in ad hoc CLI smoke scripts.

**Patterns:**
- Configure root logging with `logging.basicConfig(...)` near the top of executable modules:
  - `main.py` logs to both `main.log` and stderr/stdout via `StreamHandler`.
  - `predict_prophet.py` logs to the console only.
- Use `logging.info` for lifecycle checkpoints, `logging.warning` for recoverable issues, and `logging.error` for failures.
- Use `print(...)` for lightweight operator-facing status output in `send_gmail.py` and `send_test_email.py`.
- Prefer f-strings for all log and print messages.

## Comments

**When to Comment:**
- Add a short module docstring at the top of standalone utility modules such as `email_template.py`, `send_gmail.py`, and `send_test_email.py`.
- Add function docstrings for reusable functions; most top-level functions in `main.py`, `email_template.py`, `send_gmail.py`, and `predict_prophet.py` follow this pattern.
- Use block comments to mark execution phases inside long procedural functions, especially data prep, band calculation, plotting, and email assembly in `main.py` and `email_template.py`.
- Keep inline comments pragmatic and local to the code they clarify (`# Skip empty lines and comments`, `# Build bands dictionary for template`, `# Sleep for the specified check frequency`).

**JSDoc/TSDoc:**
- Not applicable. This repository is Python-only.

## Function Design

**Size:** Top-level helpers range from compact pure utilities in `email_template.py` to large orchestration functions in `main.py`. Match the surrounding module:
- Keep pure formatting and calculation helpers small and single-purpose.
- Accept longer procedural functions when coordinating CLI flow, plotting, file writes, and email delivery.

**Parameters:**
- Pass explicit primitive parameters instead of packaging config into objects. `main.py` and `send_test_email.py` use long parameter lists rather than configuration classes.
- Use keyword arguments for readability at call sites when a function takes many related values, especially in `build_email_content(...)` and `main_loop(...)` call chains.

**Return Values:**
- Pure helpers return transformed data (`DataFrame`, formatted strings, tuples of HTML/text).
- I/O helpers often return status tuples instead of raising on all failures (`send_gmail.py`).
- Plotting helpers return file paths or path tuples for downstream use (`main.py`, `predict_prophet.py`).

## Module Design

**Exports:**
- There is no explicit export surface. Any top-level function can be imported directly from its module, as shown by `send_test_email.py` importing from `main.py`, `email_template.py`, and `send_gmail.py`.
- Keep new reusable code in importable top-level functions instead of embedding it only inside `if __name__ == "__main__":` blocks.

**Barrel Files:**
- Not used. There are no package-level re-export modules.

**CLI Pattern:**
- Executable modules end with `if __name__ == "__main__":`, define arguments with `argparse`, and invoke a top-level orchestration function.
- Follow the existing split:
  - `main.py`: production monitor and one-shot test-email entrypoint.
  - `send_gmail.py`: standalone SMTP CLI.
  - `predict_prophet.py`: experimental forecast CLI.
  - `send_test_email.py`: manual smoke-test script with hard-coded defaults.

---

*Convention analysis: 2026-04-17*
