# Sample Milestone

> Use the `stateful-dev-cron` skill for this disposable fixture, and use `stateful-dev-helper` for state mutation and validation.

## Task 1: Prove disposable flow

**Objective:** Exercise state creation, validation, transitions, and reporting without real worker state.

**RED command:** `uv run pytest tests/test_smoke_flow.py::test_disposable_state_flow -q`

**Expected RED:** FAIL until the smoke flow exists.

**GREEN guidance:** Use temporary state and recorded evidence only.
