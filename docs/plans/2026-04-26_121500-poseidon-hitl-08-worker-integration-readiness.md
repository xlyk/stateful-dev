# Poseidon HITL Milestone 08 — Worker Integration and Readiness Proof

> **For Hermes:** Use the `stateful-cron-development` skill. Execute one `## Task N:` item per run with strict RED/GREEN/REFACTOR.

**Goal:** Wire the HITL helpers into stateful-dev operator workflows, document the Poseidon/Mac mini contract, and prove the flow with dry-run tests.

**Architecture:** Keep v1 polling-only. Poseidon handles public Discord ingress; Mac mini handles execution. No tunnel or push wake-up in this milestone.

**Tech Stack:** Python 3.11+, Typer, pytest, Ruff, local fixture states.

**Todoist project:** Poseidon HITL Ingress Gateway (`6gV83p5xWjGwpHm9`).

---

## Task 1: Add CLI support for creating HITL request payloads

**Objective:** Let workers or operators produce deterministic HITL request JSON from local state context.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Create: `tests/test_hitl_cli.py`

**RED command:** `uv run pytest tests/test_hitl_cli.py::test_hitl_request_cli_emits_json_payload -q`

**Expected RED:** FAIL because no HITL CLI command exists.

**GREEN guidance:** Add a `hitl request` command or equivalent that accepts state path, worker, item id, type, question, allowed actions, and fallback context path/stdin. It should print deterministic JSON and not contact Poseidon unless a later explicit submit mode is added.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_cli.py::test_hitl_request_cli_emits_json_payload -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add hitl request cli`

## Task 2: Add CLI support for validating and recording consumed events

**Objective:** Give workers a local command to validate a consumed Poseidon event and record it into state.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify: `tests/test_hitl_cli.py`

**RED command:** `uv run pytest tests/test_hitl_cli.py::test_hitl_consume_cli_records_valid_event -q`

**Expected RED:** FAIL because no consume/record CLI exists.

**GREEN guidance:** Add a `hitl consume` command or equivalent that accepts state path and event JSON path/stdin, validates the event against state, records it locally, and emits JSON status. It must reject mismatches before writing.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_cli.py::test_hitl_consume_cli_records_valid_event -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `feat: add hitl event consume cli`

## Task 3: Document Poseidon ingress and Mac mini polling contract

**Objective:** Provide an operator/developer runbook for the remote Poseidon HITL ingress design.

**Files:**
- Create: `docs/poseidon-hitl-ingress.md`
- Modify: `README.md`
- Create or modify: `tests/test_docs.py`

**RED command:** `uv run pytest tests/test_docs.py::test_poseidon_hitl_docs_cover_polling_and_safety_contract -q`

**Expected RED:** FAIL because Poseidon HITL docs do not exist or omit required sections.

**GREEN guidance:** Document: architecture, request/event lifecycle, Poseidon responsibilities, Mac mini responsibilities, Option A polling, node token config, Discord allowlist, validation-before-consumption, bounded subagent delegation, fallback copy/paste block, and failure recovery.

**Verification gates:**
- Focused: `uv run pytest tests/test_docs.py::test_poseidon_hitl_docs_cover_polling_and_safety_contract -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `docs: document poseidon hitl ingress`

## Task 4: Add local fake-Poseidon dry-run flow

**Objective:** Prove a Mac mini worker can create a request, receive a fake operator event, consume it once, and record local state.

**Files:**
- Create: `tests/test_hitl_e2e.py`

**RED command:** `uv run pytest tests/test_hitl_e2e.py::test_fake_poseidon_poll_consume_resume_flow -q`

**Expected RED:** FAIL because composed HITL dry-run flow is missing.

**GREEN guidance:** Use a temporary SQLite store and fake transport. Create a request, insert an operator event, poll it through the client, validate it, consume it, record it in local state, and verify duplicate consume is rejected.

**Verification gates:**
- Focused: `uv run pytest tests/test_hitl_e2e.py::test_fake_poseidon_poll_consume_resume_flow -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`

**Commit:** `test: add hitl polling dry run`

## Task 5: Add readiness audit checklist for real Discord dogfood

**Objective:** Define the final supervised proof before treating Poseidon HITL ingress as usable infrastructure.

**Files:**
- Modify: `docs/poseidon-hitl-ingress.md`
- Modify: `tests/test_docs.py`

**RED command:** `uv run pytest tests/test_docs.py::test_poseidon_hitl_docs_include_discord_dogfood_checklist -q`

**Expected RED:** FAIL because real Discord dogfood readiness criteria are missing.

**GREEN guidance:** Add a checklist for real Discord-native dry run: create a HITL request, render Discord card, answer via modal/button, Poseidon stores OperatorEvent, Mac mini polls on next cron run, event is recorded locally, parent worker delegates bounded work if allowed, and no side effects occur unless explicitly approved.

**Verification gates:**
- Focused: `uv run pytest tests/test_docs.py::test_poseidon_hitl_docs_include_discord_dogfood_checklist -q`
- Full suite: `uv run pytest -q`
- Lint: `uv run ruff check .`
- Smoke: `uv run stateful-dev --help`

**Commit:** `docs: add poseidon hitl dogfood checklist`
