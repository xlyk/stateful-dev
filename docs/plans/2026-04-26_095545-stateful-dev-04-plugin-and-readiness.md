# Stateful Dev Milestone 04 — Hermes Plugin and Readiness

> **For Hermes:** Use the `stateful-cron-development` skill. Execute one `## Task N:` item per run with strict RED/GREEN/REFACTOR.

**Goal:** Add a local Hermes plugin wrapper after the CLI is tested, document installation, and prove the workflow with a disposable sample state.

**Architecture:** Keep the plugin thin. It imports the library functions and exposes structured tools. The CLI remains the canonical interface.

**Tech Stack:** Python 3.11+, Hermes local plugin layout, pytest, Ruff.

---

## Task 1: Add plugin skeleton tests

**Objective:** Define the expected plugin files and registration surface before creating plugin code.

**Files:**
- Create: `plugins/stateful-dev/plugin.yaml`
- Create: `plugins/stateful-dev/__init__.py`
- Create: `plugins/stateful-dev/schemas.py`
- Create: `plugins/stateful-dev/tools.py`
- Create: `tests/test_plugin_layout.py`

**RED command:** `uv run pytest tests/test_plugin_layout.py::test_plugin_exposes_register_function -q`

**Expected RED:** FAIL because the plugin skeleton does not exist.

**GREEN guidance:** Add a minimal modern Hermes plugin layout with `register(ctx)` and placeholder schema/tool registration for `stateful_dev_doctor` only.

**Verification gates:**
- Focused: `uv run pytest tests/test_plugin_layout.py::test_plugin_exposes_register_function -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add hermes plugin skeleton`

## Task 2: Wrap doctor and report commands as plugin tools

**Objective:** Expose tested library behavior through Hermes plugin tools without duplicating logic.

**Files:**
- Modify: `plugins/stateful-dev/schemas.py`
- Modify: `plugins/stateful-dev/tools.py`
- Create: `tests/test_plugin_tools.py`

**RED command:** `uv run pytest tests/test_plugin_tools.py::test_plugin_doctor_returns_json_payload -q`

**Expected RED:** FAIL because plugin tools do not call the library yet.

**GREEN guidance:** Add plugin wrappers for doctor and report rendering. Return JSON-serializable dicts. Keep command execution out of plugin tools.

**Verification gates:**
- Focused: `uv run pytest tests/test_plugin_tools.py::test_plugin_doctor_returns_json_payload -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: expose state doctor plugin tool`

## Task 3: Document local installation and worker usage

**Objective:** Give operators exact commands to install and use the CLI/plugin locally.

**Files:**
- Create: `docs/usage.md`
- Modify: `README.md`

**RED command:** `uv run pytest tests/test_docs.py::test_usage_docs_include_install_and_smoke_commands -q`

**Expected RED:** FAIL because docs coverage does not exist or docs omit required commands.

**GREEN guidance:** Add a docs test that checks for `uv tool install`, `hermes tools enable`, `stateful-dev doctor`, and a disposable smoke flow. Then write the docs.

**Verification gates:**
- Focused: `uv run pytest tests/test_docs.py::test_usage_docs_include_install_and_smoke_commands -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `docs: document local stateful-dev usage`

## Task 4: Add disposable sample state smoke test

**Objective:** Prove the CLI can initialize, validate, transition, and report over a disposable fixture without touching real worker state.

**Files:**
- Create: `tests/test_smoke_flow.py`
- Create: `tests/fixtures/sample-plan.md`

**RED command:** `uv run pytest tests/test_smoke_flow.py::test_disposable_state_flow -q`

**Expected RED:** FAIL because the composed flow is missing or incomplete.

**GREEN guidance:** Build a small smoke test that creates a temp plan, initializes state, validates it, marks an item through legal transitions with evidence, and renders a report.

**Verification gates:**
- Focused: `uv run pytest tests/test_smoke_flow.py::test_disposable_state_flow -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`
- Smoke: `uv run stateful-dev --help`

**Commit:** `test: add disposable state flow smoke proof`
