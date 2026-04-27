# Stateful Dev Milestone 03 — Transitions, Locking, and Reports

> **For Hermes:** Use the `stateful-dev-cron` skill. Execute one `## Task N:` item per run with strict RED/GREEN/REFACTOR, and use `stateful-dev-helper` for state mutation and validation.

**Goal:** Enforce legal state transitions, add atomic lock handling, record evidence, and render compact reports.

**Architecture:** Implement a small transition engine over JSON state. Make all illegal transitions explicit errors. Use atomic lock directories rather than advisory text-only locks.

**Tech Stack:** Python 3.11+, pathlib, json, pytest, Typer.

---

## Task 1: Enforce legal item transitions

**Objective:** Prevent illegal status jumps such as `pending -> succeeded`.

**Files:**
- Create: `src/stateful_dev/transitions.py`
- Create: `tests/test_transitions.py`

**RED command:** `uv run pytest tests/test_transitions.py::test_pending_cannot_jump_to_succeeded -q`

**Expected RED:** FAIL because `stateful_dev.transitions` does not exist.

**GREEN guidance:** Implement `transition_item(state, item_id, target_status, evidence=None)`. Encode legal transitions from the skill. Return updated state or raise a typed error.

**Verification gates:**
- Focused: `uv run pytest tests/test_transitions.py::test_pending_cannot_jump_to_succeeded -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: enforce legal state transitions`

## Task 2: Require RED evidence before GREEN

**Objective:** Ensure `green_verified` and `succeeded` cannot be reached without recorded RED evidence unless an explicit operator exception is present.

**Files:**
- Modify: `src/stateful_dev/transitions.py`
- Modify: `tests/test_transitions.py`

**RED command:** `uv run pytest tests/test_transitions.py::test_green_requires_red_evidence -q`

**Expected RED:** FAIL because transition evidence is not enforced.

**GREEN guidance:** Require focused RED command/result fields before moving to `red_verified`; require RED before `green_verified`; require focused GREEN and full-suite evidence before `succeeded`.

**Verification gates:**
- Focused: `uv run pytest tests/test_transitions.py::test_green_requires_red_evidence -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: require transition evidence`

## Task 3: Add atomic lock handling

**Objective:** Use an atomic lock directory to prevent overlapping manual and scheduled runs.

**Files:**
- Create: `src/stateful_dev/locking.py`
- Create: `tests/test_locking.py`

**RED command:** `uv run pytest tests/test_locking.py::test_acquire_lock_refuses_fresh_existing_lock -q`

**Expected RED:** FAIL because `stateful_dev.locking` does not exist.

**GREEN guidance:** Implement `acquire_lock(state_dir, run_id, timeout_minutes)` and `release_lock(...)`. Store lock metadata in the lock directory. Treat stale locks as recoverable only after timeout.

**Verification gates:**
- Focused: `uv run pytest tests/test_locking.py::test_acquire_lock_refuses_fresh_existing_lock -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add atomic state lock handling`

## Task 4: Render compact status reports

**Objective:** Generate the plain-text reports expected by the stateful cron development skill.

**Files:**
- Create: `src/stateful_dev/reports.py`
- Create: `tests/test_reports.py`

**RED command:** `uv run pytest tests/test_reports.py::test_batch_report_includes_counts_state_and_next_action -q`

**Expected RED:** FAIL because `stateful_dev.reports` does not exist.

**GREEN guidance:** Implement `render_batch_report(state, run_summary) -> str` and `render_operator_handoff(...) -> str`. Match the concise plain-text shape in the skill.

**Verification gates:**
- Focused: `uv run pytest tests/test_reports.py::test_batch_report_includes_counts_state_and_next_action -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: render stateful worker reports`
