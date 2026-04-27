# Stateful Dev Milestone 02 — Plan Parsing and State Validation

> **For Hermes:** Use the `stateful-dev-cron` skill. Execute one `## Task N:` item per run with strict RED/GREEN/REFACTOR, and use `stateful-dev-helper` for state mutation and validation.

**Goal:** Parse milestone plan files into stable work items and validate durable state files.

**Architecture:** Keep parsing and state validation in pure functions under `src/stateful_dev/`. CLI commands should be thin wrappers over tested library functions.

**Tech Stack:** Python 3.11+, pathlib, dataclasses or typed dicts, pytest, Typer.

---

## Task 1: Parse task headings from a plan file

**Objective:** Extract `## Task N:` blocks from markdown while preserving title and body text.

**Files:**
- Create: `src/stateful_dev/plan_parser.py`
- Create: `tests/test_plan_parser.py`

**RED command:** `uv run pytest tests/test_plan_parser.py::test_parse_task_headings_with_bodies -q`

**Expected RED:** FAIL because `stateful_dev.plan_parser` does not exist.

**GREEN guidance:** Implement `parse_plan_tasks(path: Path) -> list[PlanTask]`. Match only headings shaped like `## Task <number>:`. Include heading text, title, body, and plan path.

**Verification gates:**
- Focused: `uv run pytest tests/test_plan_parser.py::test_parse_task_headings_with_bodies -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: parse milestone plan tasks`

## Task 2: Generate stable item IDs

**Objective:** Derive stable item IDs from plan filename and task heading without using list indexes alone.

**Files:**
- Modify: `src/stateful_dev/plan_parser.py`
- Modify: `tests/test_plan_parser.py`

**RED command:** `uv run pytest tests/test_plan_parser.py::test_item_ids_are_stable_slugs -q`

**Expected RED:** FAIL because parsed tasks do not expose stable IDs.

**GREEN guidance:** Use a slug from the plan stem plus `T<number>-<title-slug>`. Normalize whitespace and punctuation. Keep IDs deterministic across runs.

**Verification gates:**
- Focused: `uv run pytest tests/test_plan_parser.py::test_item_ids_are_stable_slugs -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: generate stable plan item ids`

## Task 3: Validate state schema and counts

**Objective:** Detect malformed durable state files and count drift.

**Files:**
- Create: `src/stateful_dev/state.py`
- Create: `tests/test_state.py`

**RED command:** `uv run pytest tests/test_state.py::test_validate_state_recomputes_counts_and_reports_drift -q`

**Expected RED:** FAIL because `stateful_dev.state` does not exist.

**GREEN guidance:** Implement `validate_state(data: dict) -> ValidationResult`. Check required top-level keys, item IDs, item statuses, duplicate IDs, and recomputed counts.

**Verification gates:**
- Focused: `uv run pytest tests/test_state.py::test_validate_state_recomputes_counts_and_reports_drift -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: validate state schema and counts`

## Task 4: Add `doctor` CLI command

**Objective:** Provide a CLI command that validates a state file and emits deterministic JSON.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify: `src/stateful_dev/state.py`
- Create: `tests/test_doctor_cli.py`

**RED command:** `uv run pytest tests/test_doctor_cli.py::test_doctor_reports_invalid_state_json -q`

**Expected RED:** FAIL because the `doctor` command is missing.

**GREEN guidance:** Add `stateful-dev doctor --state path/to/state.json --json`. Exit non-zero for invalid state and include `ok`, `errors`, `warnings`, and recomputed `counts` fields.

**Verification gates:**
- Focused: `uv run pytest tests/test_doctor_cli.py::test_doctor_reports_invalid_state_json -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add state doctor command`
