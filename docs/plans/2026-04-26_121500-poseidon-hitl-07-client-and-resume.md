# Poseidon HITL Milestone 07 — Mac Mini Client and Worker Resume

> **For Hermes:** Use the `stateful-cron-development` skill. Execute one `## Task N:` item per run with strict RED/GREEN/REFACTOR.

**Goal:** Add the Mac mini polling client and the safe parent-worker resume helpers for stateful-cron-development agents.

**Architecture:** Mac mini workers poll Poseidon. The parent worker validates and records an event before delegation. Subagents receive bounded context only after validation.

**Tech Stack:** Python 3.11+, urllib/request or injected transport, pytest, Ruff.

**Todoist project:** Poseidon HITL Ingress Gateway (`6gV83p5xWjGwpHm9`).

---

## Task 1: Build Poseidon polling client with injected transport

**Objective:** Give Mac mini workers a small client for request creation, pending-event polling, and event consumption.

**Files:**
- Create: `src/stateful_dev/hitl_client.py`
- Create: `tests/test_hitl_client.py`

**RED command:** `uv run pytest tests/test_hitl_client.py::test_client_polls_pending_events_with_node_token -q`

**Expected RED:** FAIL because `stateful_dev.hitl_client` does not exist.

**GREEN guidance:** Implement `PoseidonHitlClient` with injected transport for tests and a stdlib HTTP transport for runtime. Methods: `create_request`, `pending_events`, `consume_event`, and `health`. Include timeouts, no secret logging, and structured errors.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_client.py::test_client_polls_pending_events_with_node_token -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add poseidon hitl polling client`

## Task 2: Resolve local Poseidon config and node token safely

**Objective:** Load Poseidon base URL and Mac mini node token from local config/secret paths without exposing secrets.

**Files:**
- Modify: `src/stateful_dev/hitl_client.py`
- Modify: `tests/test_hitl_client.py`

**RED command:** `uv run pytest tests/test_hitl_client.py::test_client_config_loads_token_from_secret_file -q`

**Expected RED:** FAIL because runtime config resolution is missing.

**GREEN guidance:** Add `load_poseidon_config` that accepts explicit env/config paths. Support base URL, node name, and token file. Return redacted representation for logs. Do not store token values in state payloads or exception strings.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_client.py::test_client_config_loads_token_from_secret_file -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: load poseidon hitl client config`

## Task 3: Validate operator events against local worker state

**Objective:** Reject stale, mismatched, or unauthorized operator events before a worker acts.

**Files:**
- Create: `src/stateful_dev/hitl_resume.py`
- Create: `tests/test_hitl_resume.py`

**RED command:** `uv run pytest tests/test_hitl_resume.py::test_resume_rejects_mismatched_request_id -q`

**Expected RED:** FAIL because resume validation is missing.

**GREEN guidance:** Implement `validate_operator_event_for_state(event, state, state_path, allowed_actor_ids=None)`. Check request id, worker, node, item id, state path hash, event status, allowed event types, request still current, actor allowlist if provided, and expiration metadata when available.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_resume.py::test_resume_rejects_mismatched_request_id -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: validate hitl resume events`

## Task 4: Record consumed events into local state before resume

**Objective:** Persist consumed operator events in `.agent-state` before executing resumed work.

**Files:**
- Modify: `src/stateful_dev/hitl_resume.py`
- Modify: `tests/test_hitl_resume.py`

**RED command:** `uv run pytest tests/test_hitl_resume.py::test_record_consumed_event_updates_state_audit_trail -q`

**Expected RED:** FAIL because local state event recording is missing.

**GREEN guidance:** Add helper to append a normalized operator event record under `operator_events`, clear the current HITL blocker when matching, and write consumed timestamp metadata. It must not mark work succeeded or perform side effects.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_resume.py::test_record_consumed_event_updates_state_audit_trail -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: record consumed hitl events`

## Task 5: Build bounded subagent context after HITL resume

**Objective:** Convert a validated operator event into a safe, narrow subagent prompt/context.

**Files:**
- Modify: `src/stateful_dev/hitl_resume.py`
- Modify: `tests/test_hitl_resume.py`

**RED command:** `uv run pytest tests/test_hitl_resume.py::test_bounded_subagent_context_includes_constraints_and_allowed_action -q`

**Expected RED:** FAIL because bounded resume context rendering is missing.

**GREEN guidance:** Add `build_bounded_resume_context` that includes project root, state path, plan path, item id/title, event id/type, actor id, constraints, allowed next action, forbidden actions, and verification gates. It must exclude secrets and raw oversized logs.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_resume.py::test_bounded_subagent_context_includes_constraints_and_allowed_action -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: build bounded hitl resume context`
