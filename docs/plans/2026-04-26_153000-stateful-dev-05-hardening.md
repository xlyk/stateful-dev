# Milestone 05 — Stateful Dev hardening

This milestone addresses the completion-audit gaps found after the initial `stateful-dev` worker completed its planned milestones.

Worker profile: use `stateful-dev-cron`, strict TDD, one item per run, commits allowed after gates, pushes disabled unless the operator explicitly approves. Use `stateful-dev-helper` for state mutation and validation.

## Task 1: Harden CLI state writes with locking and atomic replace

Objective: make `stateful-dev init` and `stateful-dev transition` safe for durable worker state.

Files:
- `src/stateful_dev/cli.py`
- `src/stateful_dev/locking.py`
- `tests/test_cli.py`
- `tests/test_locking.py`

RED command:

```bash
uv run pytest -q tests/test_cli.py tests/test_locking.py
```

Expected RED: new tests fail because CLI writes directly without acquiring locks, `init` overwrites existing state without an explicit force flag, or state writes are not atomic.

GREEN guidance:
- Add a shared atomic JSON write helper that writes to a sibling temp file and uses `Path.replace`.
- Make CLI write paths acquire the state lock before mutating state.
- Make `init` fail if the target state already exists unless a `--force` option is passed.
- Preserve current command output shapes.

Verification gates:

```bash
uv run pytest -q tests/test_cli.py tests/test_locking.py
uv run pytest -q
uv run ruff check .
```

Commit: `fix: harden state write safety`

## Task 2: Strengthen state schema validation and RED/GREEN evidence semantics

Objective: make `doctor` and transition guards reject malformed state and bogus evidence.

Files:
- `src/stateful_dev/state.py`
- `src/stateful_dev/transitions.py`
- `tests/test_state.py`
- `tests/test_transitions.py`
- `tests/test_doctor_cli.py`

RED command:

```bash
uv run pytest -q tests/test_state.py tests/test_transitions.py tests/test_doctor_cli.py
```

Expected RED: new tests fail because malformed top-level/item field types pass validation, or `focused_red_result` text that clearly indicates success can be accepted as RED evidence.

GREEN guidance:
- Validate required top-level and item field types, not only key presence.
- Keep errors specific enough for `doctor --json` to be actionable.
- Add conservative evidence-result checks for transition evidence. Reject obvious success strings for RED evidence and obvious failure strings for GREEN/full-suite evidence.
- Do not overfit to one test runner; keep checks simple and documented.

Verification gates:

```bash
uv run pytest -q tests/test_state.py tests/test_transitions.py tests/test_doctor_cli.py
uv run pytest -q
uv run ruff check .
```

Commit: `fix: validate state and evidence semantics`

## Task 3: Fix plugin manifest, package readiness, and disposable smoke docs

Objective: make the advertised plugin/tools and smoke flow match what users can actually run.

Files:
- `plugins/stateful-dev/plugin.yaml`
- `plugins/stateful-dev/tools.py`
- `pyproject.toml`
- `docs/usage.md`
- `README.md`
- `tests/test_plugin_layout.py`
- `tests/test_docs.py`
- `tests/test_smoke_flow.py`

RED command:

```bash
uv run pytest -q tests/test_plugin_layout.py tests/test_docs.py tests/test_smoke_flow.py
```

Expected RED: new tests fail because the manifest omits `stateful_dev_report`, packaging/docs do not clearly cover plugin installation, or the documented smoke flow validates the project-local state path instead of a disposable temp state.

GREEN guidance:
- Align `plugin.yaml` with registered tools.
- Add tests that compare manifest tool names with Python registration names.
- Clarify whether the plugin is path-enabled or packaged, and document the exact supported setup.
- Rewrite the smoke flow so every command uses a disposable `/tmp` state path and exercises `init`, `doctor`, `transition`, and `report` safely.

Verification gates:

```bash
uv run pytest -q tests/test_plugin_layout.py tests/test_docs.py tests/test_smoke_flow.py
uv run pytest -q
uv run ruff check .
```

Commit: `docs: fix plugin and smoke-flow readiness`
