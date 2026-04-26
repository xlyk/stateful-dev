# Poseidon HITL Milestone 05 — Contracts and Storage

> **For Hermes:** Use the `stateful-cron-development` skill. Execute one `## Task N:` item per run with strict RED/GREEN/REFACTOR.

**Goal:** Add the local library contracts and durable storage primitives for the Poseidon operator-inbox pattern: `HITLRequest → OperatorEvent → WorkerResume`.

**Architecture:** Keep this as normal tested Python package code first. The Mac mini worker will use client helpers; Poseidon will use the same request/event models and SQLite schema. Do not add network or Discord behavior in this milestone.

**Tech Stack:** Python 3.11+, dataclasses, sqlite3, pytest, Ruff.

**Todoist project:** Poseidon HITL Ingress Gateway (`6gV83p5xWjGwpHm9`).

---

## Task 1: Define HITL request and operator event models

**Objective:** Create typed, JSON-serializable models for HITL requests and operator events.

**Files:**
- Create: `src/stateful_dev/hitl_models.py`
- Create: `tests/test_hitl_models.py`

**RED command:** `uv run pytest tests/test_hitl_models.py::test_hitl_request_round_trips_required_fields -q`

**Expected RED:** FAIL because `stateful_dev.hitl_models` does not exist.

**GREEN guidance:** Add dataclasses or lightweight typed structures for `HITLRequest`, `OperatorEvent`, and `WorkerResume`. Required fields include request/event ids, node, worker, project, state path hash, item id, type, status, question, allowed actions, constraints, payload, actor id, timestamps, and fallback context. Include `to_dict` / `from_dict` helpers and validation errors for missing required fields.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_models.py::test_hitl_request_round_trips_required_fields -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: define hitl request contracts`

## Task 2: Add SQLite schema and migration helper

**Objective:** Create a repeatable SQLite schema for Poseidon operator-inbox storage.

**Files:**
- Create: `src/stateful_dev/hitl_store.py`
- Modify: `tests/test_hitl_models.py` or create `tests/test_hitl_store.py`

**RED command:** `uv run pytest tests/test_hitl_store.py::test_init_store_creates_request_and_event_tables -q`

**Expected RED:** FAIL because no HITL store exists.

**GREEN guidance:** Implement `init_store(path)` using stdlib `sqlite3`. Tables must include `hitl_requests`, `operator_events`, `discord_messages`, and `audit_log`. Use `CREATE TABLE IF NOT EXISTS`. Store JSON payloads as text. Do not require external database packages.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_store.py::test_init_store_creates_request_and_event_tables -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add hitl sqlite storage schema`

## Task 3: Persist and load HITL requests

**Objective:** Store incoming HITL requests durably and reload them by id.

**Files:**
- Modify: `src/stateful_dev/hitl_store.py`
- Modify: `tests/test_hitl_store.py`

**RED command:** `uv run pytest tests/test_hitl_store.py::test_store_and_load_hitl_request -q`

**Expected RED:** FAIL because request persistence is missing.

**GREEN guidance:** Add `put_request`, `get_request`, and `list_open_requests` helpers. Preserve request payload exactly except for deterministic JSON formatting. Reject duplicate request ids unless the stored payload is identical and idempotent.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_store.py::test_store_and_load_hitl_request -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: persist hitl requests`

## Task 4: Persist pending operator events with one-time consumption

**Objective:** Add pending-event storage and atomic consume semantics for Mac mini polling.

**Files:**
- Modify: `src/stateful_dev/hitl_store.py`
- Modify: `tests/test_hitl_store.py`

**RED command:** `uv run pytest tests/test_hitl_store.py::test_operator_event_can_be_consumed_once -q`

**Expected RED:** FAIL because operator event persistence and consumption are missing.

**GREEN guidance:** Add `put_operator_event`, `list_pending_events(node, worker=None, request_id=None)`, and `consume_event(event_id, node)`. Consumption must be one-time and node-scoped. Duplicate consume returns a clear false/exception result without mutating audit history incorrectly.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_store.py::test_operator_event_can_be_consumed_once -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add hitl event consumption`

## Task 5: Add expiry, cancellation, and audit records

**Objective:** Make stale HITL requests safe and auditable.

**Files:**
- Modify: `src/stateful_dev/hitl_store.py`
- Modify: `tests/test_hitl_store.py`

**RED command:** `uv run pytest tests/test_hitl_store.py::test_expired_request_does_not_return_pending_events -q`

**Expected RED:** FAIL because expiry/cancellation behavior is missing.

**GREEN guidance:** Add request statuses `open`, `answered`, `consumed`, `cancelled`, and `expired`. Add audit-log writes for request creation, event creation, consume, cancel, and expiry. Pending event queries must not return events for expired/cancelled requests.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_store.py::test_expired_request_does_not_return_pending_events -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: audit hitl request lifecycle`
