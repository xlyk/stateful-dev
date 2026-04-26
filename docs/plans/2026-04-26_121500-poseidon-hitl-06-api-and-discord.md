# Poseidon HITL Milestone 06 — Poseidon API and Discord Ingress

> **For Hermes:** Use the `stateful-cron-development` skill. Execute one `## Task N:` item per run with strict RED/GREEN/REFACTOR.

**Goal:** Add a minimal Poseidon-facing ingress layer for HITL requests and Discord operator events.

**Architecture:** Keep HTTP and Discord handlers thin and testable. They should validate inputs, call the HITL store, and return deterministic JSON. Avoid starting a real server in unit tests.

**Tech Stack:** Python 3.11+, stdlib-first handlers, optional FastAPI/Discord adapters only if already justified by tests, pytest, Ruff.

**Todoist project:** Poseidon HITL Ingress Gateway (`6gV83p5xWjGwpHm9`).

---

## Task 1: Define Poseidon API request and response helpers

**Objective:** Specify the local handler contract for creating requests, polling events, and consuming events.

**Files:**
- Create: `src/stateful_dev/hitl_api.py`
- Create: `tests/test_hitl_api.py`

**RED command:** `uv run pytest tests/test_hitl_api.py::test_create_request_handler_validates_node_token -q`

**Expected RED:** FAIL because `stateful_dev.hitl_api` does not exist.

**GREEN guidance:** Add pure functions for API behavior before adding web framework glue: `create_request_handler`, `pending_events_handler`, and `consume_event_handler`. Use dependency injection for store path and token verifier. Return dicts with HTTP-like status codes and JSON bodies.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_api.py::test_create_request_handler_validates_node_token -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add hitl api handlers`

## Task 2: Add node-scoped token verification

**Objective:** Ensure Poseidon only accepts and returns events for the authenticated node.

**Files:**
- Create: `src/stateful_dev/hitl_auth.py`
- Modify: `tests/test_hitl_api.py`

**RED command:** `uv run pytest tests/test_hitl_api.py::test_pending_events_are_scoped_to_authenticated_node -q`

**Expected RED:** FAIL because node auth/event isolation is missing.

**GREEN guidance:** Implement a small token verifier that accepts a configured mapping of node names to token hashes or test tokens. API handlers must reject missing/bad tokens and ignore caller-provided node values that conflict with the authenticated node.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_api.py::test_pending_events_are_scoped_to_authenticated_node -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: scope hitl api by node token`

## Task 3: Render Discord HITL cards as deterministic payloads

**Objective:** Convert HITL requests into compact Discord embed/component payloads without contacting Discord.

**Files:**
- Create: `src/stateful_dev/hitl_discord.py`
- Create: `tests/test_hitl_discord.py`

**RED command:** `uv run pytest tests/test_hitl_discord.py::test_hitl_request_renders_discord_card_payload -q`

**Expected RED:** FAIL because no Discord renderer exists.

**GREEN guidance:** Render a concise embed-like dict containing worker, project, item id, question, recommendation, risk/constraints, and state path. Include component metadata for `use_recommendation`, `answer`, `approve`, `deny`, `defer`, and `stop_worker` based on allowed actions. Keep fallback context available but not fully expanded into the main card.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_discord.py::test_hitl_request_renders_discord_card_payload -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: render hitl discord cards`

## Task 4: Normalize Discord button and modal submissions into OperatorEvents

**Objective:** Convert Discord interaction payloads into typed operator events.

**Files:**
- Modify: `src/stateful_dev/hitl_discord.py`
- Modify: `tests/test_hitl_discord.py`

**RED command:** `uv run pytest tests/test_hitl_discord.py::test_discord_modal_submission_creates_operator_event -q`

**Expected RED:** FAIL because Discord interaction normalization is missing.

**GREEN guidance:** Add a pure `operator_event_from_discord_interaction` helper. It must preserve actor Discord id, request id, action, modal fields, constraints, and timestamp. It must reject unsupported action ids and missing request ids.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_discord.py::test_discord_modal_submission_creates_operator_event -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: normalize discord hitl interactions`

## Task 5: Persist Discord message lifecycle metadata

**Objective:** Track Discord message ids so cards can be updated after answer, consume, cancel, or expiry.

**Files:**
- Modify: `src/stateful_dev/hitl_store.py`
- Modify: `src/stateful_dev/hitl_discord.py`
- Modify: `tests/test_hitl_store.py`

**RED command:** `uv run pytest tests/test_hitl_store.py::test_discord_message_metadata_round_trips -q`

**Expected RED:** FAIL because Discord message metadata persistence is missing.

**GREEN guidance:** Add helpers to store and load `channel_id`, `message_id`, `request_id`, `render_version`, and current card status. Do not require Discord API access in tests.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_store.py::test_discord_message_metadata_round_trips -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: track discord hitl messages`
