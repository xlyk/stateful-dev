# Stateful Dev Milestone 01 — Foundation

> **For Hermes:** Use the `stateful-cron-development` skill. Execute one `## Task N:` item per run with strict RED/GREEN/REFACTOR.

**Goal:** Bootstrap a tested Python CLI package without implementing stateful behavior yet.

**Architecture:** Use a `src/stateful_dev` package, Typer CLI entry point, pytest tests, and Ruff linting. Keep all behavior minimal and test-first.

**Tech Stack:** Python 3.11+, uv, Typer, pytest, Ruff.

---

## Task 1: Bootstrap package metadata with a failing CLI import test

**Objective:** Create the Python package skeleton and prove the CLI module exists through a failing test first.

**Files:**
- Create: `pyproject.toml`
- Create: `src/stateful_dev/__init__.py`
- Create: `src/stateful_dev/cli.py`
- Create: `tests/test_cli.py`

**RED command:** `uv run pytest tests/test_cli.py::test_cli_app_importable -q`

**Expected RED:** FAIL because `stateful_dev.cli` does not exist.

**GREEN guidance:** Add minimal package metadata, dependencies (`typer`), dev dependencies (`pytest`, `ruff`), and define `app = typer.Typer(...)` in `src/stateful_dev/cli.py`.

**Verification gates:**
- Focused: `uv run pytest tests/test_cli.py::test_cli_app_importable -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`
- Smoke: `uv run stateful-dev --help`

**Commit:** `feat: bootstrap stateful-dev cli package`

## Task 2: Add a version command

**Objective:** Expose `stateful-dev version` with the package version.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify: `tests/test_cli.py`

**RED command:** `uv run pytest tests/test_cli.py::test_version_command_prints_version -q`

**Expected RED:** FAIL because the `version` command is missing or returns a non-zero exit code.

**GREEN guidance:** Use `typer.testing.CliRunner` in the test. Implement the smallest `version` command that prints the package version string.

**Verification gates:**
- Focused: `uv run pytest tests/test_cli.py::test_version_command_prints_version -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add version command`

## Task 3: Add common JSON output helpers

**Objective:** Establish a deterministic JSON response helper for future commands.

**Files:**
- Create: `src/stateful_dev/output.py`
- Create: `tests/test_output.py`

**RED command:** `uv run pytest tests/test_output.py::test_json_output_is_sorted_and_newline_terminated -q`

**Expected RED:** FAIL because `stateful_dev.output` does not exist.

**GREEN guidance:** Implement a `to_json(data: object) -> str` helper using sorted keys and a trailing newline.

**Verification gates:**
- Focused: `uv run pytest tests/test_output.py::test_json_output_is_sorted_and_newline_terminated -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add deterministic json output helper`
