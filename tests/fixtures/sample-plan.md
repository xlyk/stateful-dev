# Sample Milestone

> Use the `stateful-cron-development` skill for this disposable fixture.

## Task 1: Prove disposable flow

**Objective:** Exercise state creation, validation, transitions, and reporting without real worker state.

**RED command:** `uv run pytest tests/test_smoke_flow.py::test_disposable_state_flow -q`

**Expected RED:** FAIL until the smoke flow exists.

**GREEN guidance:** Use temporary state and recorded evidence only.
