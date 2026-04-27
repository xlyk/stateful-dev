# Stateful Dev Poseidon HITL Poll-Before-Claim Implementation Plan

> **For Hermes:** Use `stateful-dev-cron`, `stateful-dev-helper`, and `test-driven-development` to execute this plan task-by-task.

**Goal:** Guarantee that stateful-dev cron workers poll Poseidon for pending HITL operator events before they can claim or continue normal coding work.

**Architecture:** Add a first-class HITL preflight phase to `stateful-dev`: workers record active HITL request metadata in local state, `run start`/`claim` enforce a successful poll marker for the current run when HITL is enabled, and matching Poseidon events are validated and staged before normal work selection. Poseidon remains the remote mailbox; stateful-dev remains the local authority that validates, consumes, and resumes work under its own state lock.

**Tech Stack:** Python 3.11+, Typer, pytest, ruff, stdlib HTTP/file handling unless a dependency is explicitly justified.

**Todoist Project:** `Stateful Dev` (`6gV7Qgm6PWwrHhM2`).

**Related Poseidon project:** `Poseidon HITL Ingress Gateway` (`6gV83p5xWjGwpHm9`). Poseidon already supports API-created HITL requests and Discord gateway posting. Server-side guarded consume may still need a matching Poseidon task before this becomes production-grade.

---

## Design invariants

1. Prompt text is not the guarantee. `stateful-dev` must enforce the poll-before-claim invariant in code.
2. A worker with Poseidon HITL enabled must not claim new normal work until the current run has a successful HITL poll marker.
3. Routing keys are strict: `node_id + worker_id + request_id + item_id + state_path_hash`.
4. State mutation happens only while the local state lock is held.
5. Poseidon is a durable mailbox, not a scheduler. It must not know Hermes cron IDs.
6. A node-local dispatcher may be added later, but the first production path should be worker self-polling.
7. Poll failures fail closed for HITL-enabled workers unless the config explicitly sets `poll_policy=optional`.

## Proposed state additions

Top-level optional state block:

```json
{
  "hitl": {
    "enabled": true,
    "provider": "poseidon",
    "node_id": "mac-mini-remote-dogfood",
    "worker_id": "stateful-dev-todoist-backlog-worker",
    "state_path_hash": "sha256:...",
    "poll_policy": "required",
    "active_requests": [
      {
        "request_id": "...",
        "item_id": "...",
        "allowed_actions": ["approve_recommendation", "answer", "edit"],
        "status": "pending",
        "created_at": "...",
        "expires_at": "..."
      }
    ],
    "last_poll": {
      "run_id": "...",
      "started_at": "...",
      "completed_at": "...",
      "ok": true,
      "event_count": 0
    }
  }
}
```

Per-run marker in `.agent-state/<job>/runs/<run-id>.json`:

```json
{
  "run_id": "...",
  "hitl_poll": {
    "required": true,
    "started_at": "...",
    "completed_at": "...",
    "ok": true,
    "worker_id": "...",
    "request_ids": ["..."],
    "event_count": 0,
    "staged_event_count": 0
  }
}
```

Per-worker staged event path:

```text
.agent-state/<worker>/hitl-inbox/<request_id>/<event_id>.json
```

## Task 1: Add HITL state schema validation and state-path hash helper

**Objective:** Teach `stateful-dev` to recognize optional Poseidon HITL metadata and compute the canonical state path hash used for event routing.

**Files:**
- Modify: `src/stateful_dev/state.py`
- Create: `src/stateful_dev/hitl.py`
- Test: `tests/test_hitl_state.py`

**Required cycle:**
1. Write failing tests for valid and invalid top-level `hitl` blocks.
2. Write a failing test for canonical `state_path_hash` generation from a state path.
3. Implement minimal validation helpers without requiring HITL fields for non-HITL states.
4. Run focused tests, `uv run pytest -q`, and `uv run ruff check .`.

**Acceptance criteria:**
- [ ] Non-HITL state files remain valid and backwards compatible.
- [ ] HITL-enabled state requires `provider`, `node_id`, `worker_id`, `state_path_hash`, `poll_policy`, and `active_requests`.
- [ ] Active requests require `request_id`, `item_id`, `allowed_actions`, and `status`.
- [ ] Invalid `poll_policy`, malformed request IDs, or non-list `allowed_actions` fail doctor validation clearly.
- [ ] State path hashing is deterministic and documented in test names.

## Task 2: Add run-start support for required HITL poll markers

**Objective:** Extend the run lifecycle model so each cron execution has a durable place to record HITL poll start/completion before any claim.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Modify/Create: `src/stateful_dev/runs.py`
- Modify/Create: `tests/test_runs.py`
- Test: `tests/test_hitl_run_markers.py`

**Dependency:** This can be implemented with the existing planned run lifecycle command work, but the HITL marker fields must be explicit.

**Required cycle:**
1. Write failing tests for `run start --state STATE --run-id RUN --json` creating a run summary with `hitl_poll.required=true` when state HITL is enabled.
2. Write failing tests proving non-HITL states create `hitl_poll.required=false` or omit HITL fields consistently.
3. Implement minimal run summary support and atomic writes.
4. Run focused tests, full suite, and lint.

**Acceptance criteria:**
- [ ] Run summaries are written under `.agent-state/<job>/runs/<run-id>.json`.
- [ ] HITL-enabled workers record that a poll is required for the run.
- [ ] The run marker includes `run_id`, state path, worker ID, node ID, and active request IDs.
- [ ] Existing `status` and `report` behavior remain compatible.

## Task 3: Add Poseidon HITL poll-before-run command

**Objective:** Add a command that polls Poseidon for active request IDs, validates matching events against local state metadata, stages them in a local inbox, and records a successful poll marker.

**Files:**
- Modify: `src/stateful_dev/cli.py`
- Create: `src/stateful_dev/hitl_poseidon.py`
- Modify/Create: `src/stateful_dev/hitl.py`
- Test: `tests/test_hitl_poseidon.py`
- Test: `tests/test_hitl_cli.py`

**Command shape:**

```bash
stateful-dev hitl poll-before-run \
  --state .agent-state/<worker>/state.json \
  --run-id <run-id> \
  --base-url "$POSEIDON_HITL_BASE_URL" \
  --node-token-file "$POSEIDON_HITL_NODE_TOKEN_FILE" \
  --json
```

**Required cycle:**
1. Write failing tests with a fake Poseidon transport returning no events.
2. Write failing tests with a matching event that must be staged to `hitl-inbox/<request_id>/<event_id>.json`.
3. Write failing tests for mismatched worker, item ID, state path hash, event type, and request ID.
4. Write failing tests proving poll failure records failure and exits nonzero when policy is `required`.
5. Implement the minimal client using injectable transport; avoid live network in unit tests.
6. Run focused tests, full suite, and lint.

**Acceptance criteria:**
- [ ] Polls narrowly by `worker` and each active `request_id`, not broad node-wide scans.
- [ ] Validates `node_id`, `worker_id`, `request_id`, `item_id`, `state_path_hash`, and allowed action before staging.
- [ ] Writes staged event JSON atomically under the worker inbox.
- [ ] Records `hitl.last_poll` and run summary `hitl_poll` fields.
- [ ] Does not consume remote events until local validation succeeds.
- [ ] Does not mutate item status directly.

## Task 4: Make claim refuse normal work until HITL poll succeeds

**Objective:** Enforce the guarantee: HITL-enabled workers cannot claim new normal work unless the current run has a successful poll marker.

**Files:**
- Modify/Create: `src/stateful_dev/claiming.py`
- Modify: `src/stateful_dev/cli.py`
- Modify: `src/stateful_dev/status.py`
- Test: `tests/test_claiming.py`
- Test: `tests/test_hitl_claim_gate.py`

**Dependency:** This extends the existing Todoist task `Add atomic claim command for next stateful-dev work item`.

**Required cycle:**
1. Write a failing test where HITL is disabled and claim behavior is unchanged.
2. Write a failing test where HITL is enabled, no current-run poll marker exists, and claim is refused.
3. Write a failing test where HITL poll failed and claim is refused.
4. Write a failing test where HITL poll succeeded and claim proceeds normally.
5. Implement the smallest precondition check around claim.
6. Run focused tests, full suite, and lint.

**Acceptance criteria:**
- [ ] Claim checks `run_id` and refuses stale poll markers from earlier runs.
- [ ] Refusal output is machine-readable and tells the worker to run `hitl poll-before-run`.
- [ ] Claim does not consume or discard staged HITL events.
- [ ] Non-HITL workers are unaffected.

## Task 5: Add resume-from-HITL inbox handling

**Objective:** Let the worker detect staged operator events before selecting normal pending work and produce exact resume instructions for the active item.

**Files:**
- Modify/Create: `src/stateful_dev/hitl.py`
- Modify/Create: `src/stateful_dev/claiming.py`
- Modify: `src/stateful_dev/status.py`
- Test: `tests/test_hitl_inbox.py`

**Required cycle:**
1. Write failing tests where a staged event causes claim/status to report `resume_hitl` instead of normal work.
2. Write failing tests proving mismatched or malformed inbox files are quarantined or ignored with warnings.
3. Write failing tests proving the state lock is required before moving staged events into a processed/resume record.
4. Implement minimal inbox scan and resume payload.
5. Run focused tests, full suite, and lint.

**Acceptance criteria:**
- [ ] A matching staged event takes priority over new normal work.
- [ ] Output includes event ID, request ID, item ID, event type, payload, and allowed next action.
- [ ] Processed events are marked locally so the same inbox file is not replayed indefinitely.
- [ ] Invalid inbox files do not crash the worker without a clear diagnostic.

## Task 6: Add guarded remote consume support after local validation

**Objective:** Consume Poseidon events only after local validation and, when the server supports it, include worker/request/item/state preconditions.

**Files:**
- Modify: `src/stateful_dev/hitl_poseidon.py`
- Test: `tests/test_hitl_poseidon.py`
- Docs: update this plan or README if Poseidon support is still missing.

**Poseidon-side dependency:** Poseidon should add a guarded consume endpoint/body that atomically matches `event_id`, authenticated node, `worker`, `request_id`, `item_id`, `state_path_hash`, and `status=pending`. Until then, stateful-dev should treat node-only consume as dogfood-grade.

**Required cycle:**
1. Write failing tests for guarded consume request body generation.
2. Write failing tests for duplicate consume and mismatch responses becoming clear local errors.
3. Implement minimal consume helper with response-body error preservation.
4. Run focused tests, full suite, and lint.

**Acceptance criteria:**
- [ ] Consume happens after local validation, not before.
- [ ] Guard fields are sent when configured/supported.
- [ ] Duplicate consume is reported as already handled, not silently ignored.
- [ ] Mismatch errors fail closed.

## Task 7: Update deployment profile and prompt rendering for HITL preflight

**Objective:** Make generated cron prompts and deployment profiles require the HITL preflight sequence when Poseidon HITL is enabled.

**Files:**
- Modify/Create: `src/stateful_dev/profiles.py`
- Modify/Create: `src/stateful_dev/prompt_rendering.py`
- Modify: skill/template docs if copied into repo
- Test: `tests/test_profiles.py`
- Test: `tests/test_prompt_rendering.py`

**Required cycle:**
1. Write failing profile validation tests for HITL config fields and token-file references.
2. Write failing prompt render tests proving the first executable step is `hitl poll-before-run`, then `claim`.
3. Implement minimal validation/rendering.
4. Run focused tests, full suite, lint, and `uv build` if package data changes.

**Acceptance criteria:**
- [ ] Profiles can declare Poseidon HITL config without embedding secrets.
- [ ] Token paths are file references, not raw tokens.
- [ ] Rendered prompts state that claim must not run before HITL poll.
- [ ] Rendered prompts include fallback behavior for poll failures.

## Task 8: Prove two-worker same-node isolation

**Objective:** Add an integration-style test proving two workers sharing one node token cannot receive or consume each other's events.

**Files:**
- Test: `tests/test_hitl_two_worker_isolation.py`
- Fixtures: local fake state files and fake Poseidon transport

**Required cycle:**
1. Write failing two-worker test with worker A and worker B using the same `node_id` and different `worker_id`/`state_path_hash`.
2. Prove worker A does not stage worker B's event.
3. Prove mismatched consume preconditions are rejected by the fake server.
4. Prove duplicate consume still rejects.
5. Implement any missing seams exposed by the test.
6. Run focused tests, full suite, lint, and `uv build` if packaging changed.

**Acceptance criteria:**
- [ ] Same-node isolation is covered by tests.
- [ ] Worker/request/item/state hash mismatch rejects.
- [ ] Duplicate consume rejects.
- [ ] The test does not require live Poseidon or Discord.

## Task 9: Dogfood with one real low-risk stateful-dev worker item

**Objective:** Verify the full beginning-of-run sequence on a real worker state before calling the design actual-use ready.

**Files:**
- Evidence: `.agent-state/<worker>/runs/<run-id>.json`
- Evidence: optional `docs/evidence/<date>-stateful-dev-hitl-poll-before-claim.md`

**Required cycle:**
1. Configure one low-risk worker with Poseidon HITL enabled and one active request.
2. Start a cron-like run.
3. Verify `run start` creates a HITL-required marker.
4. Verify `hitl poll-before-run` runs before `claim`.
5. Verify claim refuses if the poll marker is absent or failed.
6. Verify a real operator event is staged/resumed before normal work.
7. Run `uv run pytest -q`, `uv run ruff check .`, and `uv build`.

**Acceptance criteria:**
- [ ] Evidence proves poll-before-claim ordering.
- [ ] No normal work is claimed before HITL polling.
- [ ] Operator event routes to the correct worker/item.
- [ ] Failure mode is safe and recoverable.
- [ ] Todoist and local state agree after the dogfood run.
