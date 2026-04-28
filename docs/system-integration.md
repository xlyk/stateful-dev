# Stateful-dev, Poseidon, and Hermes Plugin Integration

This document explains how the local `stateful-dev` helper, the Poseidon HITL mailbox, Hermes cron, and the `stateful-dev` Hermes plugin fit together.

If you only need the mental model, start with [`system-integration-lite.md`](system-integration-lite.md).

## Short version

`stateful-dev` is the local source of truth for worker execution. Poseidon is a remote mailbox for operator decisions. Hermes cron schedules fresh agent runs. Hermes plugin tools expose the same checked state operations to agents without making the plugin a second state machine.

```text
Markdown plans
  -> stateful-dev state (.agent-state/<worker>/state.json)
  -> Hermes cron script wrapper
  -> stateful-dev cron-gate
  -> optional Poseidon poll-before-claim
  -> stateful-dev claim
  -> Hermes agent run
  -> stateful-dev record/transition/complete via CLI or plugin tools
```

The boundary is intentional: scheduling, state, mailbox, and execution stay separate.

## Components and responsibilities

| Component | Owns | Does not own |
| --- | --- | --- |
| `stateful-dev` CLI/package | Durable local state, validation, locks, evidence, transitions, claim selection, cron-gate wake decisions, HITL poll markers | Scheduling, code generation, remote operator UI, Todoist authority |
| `.agent-state/<worker>/state.json` | Execution source of truth for plan item status, counts, attempts, evidence, HITL config | Chat history, cron job identity, remote mailbox storage |
| Hermes cron | Schedules recurring/one-shot agent runs and runs optional pre-run scripts | Item selection, RED/GREEN validation, remote HITL routing |
| `~/.hermes/scripts/stateful_dev_<worker>_gate.py` | Per-worker adapter: `chdir`, call `stateful-dev cron-gate`, emit final JSON, preserve exit code | Wake-decision logic, claim logic, state inspection |
| `stateful-dev cron-gate` | Deterministic local wake/skip/blocker decision: doctor, git status, lock check, HITL preflight, claim/resume, `wakeAgent` JSON | Running implementation work |
| Poseidon | Durable remote HITL request/event mailbox | Local state transitions, cron IDs, git checks, item claiming |
| Hermes agent | Executes exactly one claimed item under prompt/tool constraints | Deciding whether to wake, bypassing state gates |
| `plugins/stateful-dev` | Thin Hermes tool wrappers around tested `stateful-dev` library behavior | Independent lifecycle implementation |

## Runtime flow

### 1. Plan becomes durable state

A markdown plan with `## Task N: Title` headings is initialized into project-local state:

```bash
uv run stateful-dev init \
  --plan docs/plans/<plan>.md \
  --state .agent-state/<worker>/state.json \
  --job-name <worker> \
  --project-root "$PWD" \
  --json

uv run stateful-dev doctor --state .agent-state/<worker>/state.json --json
```

The state file controls execution. Todoist, Discord, GitHub, and Poseidon can mirror or route work, but they are not the execution authority.

### 2. Hermes cron invokes a thin gate wrapper

Hermes cron can attach a pre-run script:

```text
script: stateful_dev_<worker>_gate.py
workdir: <project root>
skills: ["stateful-dev-lean-worker"]
enabled_toolsets: ["terminal", "file", "skills"]
```

The script lives under `~/.hermes/scripts/`. It calls:

```bash
uv run --directory <project-root> stateful-dev cron-gate \
  --state <state-path> \
  --project-root <project-root> \
  --worker-id <worker-id> \
  --run-id <run-id>
```

The wrapper must preserve the `cron-gate` exit code. Converting a nonzero blocker into exit-0 `wakeAgent:false` hides the problem as a silent skip.

### 3. `cron-gate` decides wake, skip, blocker, or error

`stateful-dev cron-gate` checks local readiness before an agent runs:

1. Load and validate state with `doctor` semantics.
2. Check git status. Dirty git or inability to check git is a blocker.
3. Check state lock freshness.
4. If HITL is enabled, require a successful poll marker for the run before claim.
5. Resume an active item or atomically claim one eligible item.
6. Emit the final `wakeAgent` JSON payload.

Current Hermes behavior:

| Result | Exit | Hermes behavior |
| --- | --- | --- |
| `mode=wake`, `wakeAgent:true` | 0 | Runs the agent with Script Output. |
| `mode=skip`, `wakeAgent:false` | 0 | Skips the agent and suppresses delivery. |
| `mode=blocker`, `wakeAgent:false` | nonzero | Runs the agent through Script Error so it can notify the operator. |
| `mode=error`, `wakeAgent:false` | nonzero | Runs the agent through Script Error so it can report the bug. |

The full JSON contract lives in [`cron-gate-contract.md`](cron-gate-contract.md). The wrapper runbook lives in [`cron-gate.md`](cron-gate.md).

## Poseidon HITL integration

Poseidon is a mailbox, not the local authority.

A stateful worker may store HITL configuration in state:

```json
{
  "hitl": {
    "enabled": true,
    "provider": "poseidon",
    "node_id": "<node>",
    "worker_id": "<worker>",
    "poll_policy": "required",
    "active_requests": ["<request-id>"]
  }
}
```

`stateful-dev hitl poll-before-run` / the Poseidon integration uses these routing keys:

```text
node_id + worker_id + request_id + item_id + state_path_hash
```

The local worker polls narrowly for active request IDs, validates routing, stages matching events under the local HITL inbox, and records a run marker:

```text
.agent-state/<worker>/hitl-inbox/<request_id>/<event_id>.json
.agent-state/<worker>/runs/<run_id>.json
```

A successful run marker includes `hitl_poll.ok=true` for the current `run_id`. `stateful-dev claim` and `cron-gate` fail closed when HITL is enabled with `poll_policy=required` and that marker is absent, stale, or failed.

This prevents normal coding work from advancing after an operator decision exists remotely but has not been fetched locally.

## Hermes plugin integration

The plugin lives here:

```text
plugins/stateful-dev/
```

It exposes JSON-serializable Hermes tools around the same package behavior used by the CLI. The CLI/package remain canonical.

Current plugin tools:

- `stateful_dev_doctor`
- `stateful_dev_report`
- `stateful_dev_status`
- `stateful_dev_transition`
- `stateful_dev_record_red`
- `stateful_dev_record_green`
- `stateful_dev_record_full_suite`
- `stateful_dev_record_lint`
- `stateful_dev_claim`
- `stateful_dev_lock_status`
- `stateful_dev_lock_recover`
- `stateful_dev_handoff`
- `stateful_dev_complete`

Use plugin tools when the Hermes agent needs structured state operations. Use the CLI when operating from a terminal or script. Both paths must preserve the same semantics for locks, HITL preflight, evidence validation, claim order, and shutdown readiness.

The plugin should not grow separate selection or transition logic. If behavior changes, change the package/CLI first, then keep the plugin thin.

## State and evidence lifecycle

Normal success path:

```text
pending -> in_progress -> red_verified -> green_verified -> succeeded
```

Evidence gates:

| Status | Required evidence |
| --- | --- |
| `red_verified` | focused RED command and failing result for the intended reason |
| `green_verified` | prior RED plus focused GREEN command and passing result |
| `succeeded` | prior RED/GREEN plus full-suite passing result; lint when configured |

Record commands are lifecycle-aware:

```text
record-red        requires in_progress
record-green      requires red_verified and prior RED evidence
record-full-suite requires green_verified and prior RED evidence
record-lint       supplemental evidence
```

Structured evidence fields such as `exit_code` and `passed` take precedence over text heuristics.

## Failure and safety model

The system prefers fail-closed behavior:

- Invalid state blocks the run.
- Dirty git blocks the run.
- Git-status failure blocks the run.
- Fresh lock blocks the run.
- Required HITL poll failure blocks the run.
- Missing HITL poll marker blocks claim.
- Out-of-order evidence recording is rejected.
- Shutdown approval requires all work to be terminal.

Silent skip is reserved for expected idle states only.

## Operator workflows

### Inspect a worker

```bash
uv run stateful-dev doctor --state .agent-state/<worker>/state.json --json
uv run stateful-dev status --state .agent-state/<worker>/state.json --json
uv run stateful-dev lock status --state .agent-state/<worker>/state.json
```

### Debug cron wake behavior

```bash
uv run stateful-dev cron-gate \
  --state .agent-state/<worker>/state.json \
  --project-root "$PWD" \
  --worker-id <worker> \
  --run-id "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --json
```

Then run the actual wrapper under `~/.hermes/scripts/` and confirm the last stdout line is JSON and the exit code is preserved.

### Poll Poseidon before claim

```bash
uv run stateful-dev hitl poll-before-run \
  --state .agent-state/<worker>/state.json \
  --run-id <run-id> \
  --base-url <poseidon-base-url> \
  --node-token-file <path-to-node-token>
```

If polling is required and this fails, do not claim work. Fix the mailbox, token, routing, or local state config first.

### Complete or retire a worker

```bash
uv run stateful-dev complete --state .agent-state/<worker>/state.json --json
```

Only retire or pause a recurring worker as complete when `complete` says shutdown is approved and the cron job/state/repo have been verified.

## Design rules

1. Keep durable state local and authoritative.
2. Route remote HITL by stable worker/request/item/state identifiers, not cron IDs or chat text.
3. Keep wrapper scripts thin.
4. Keep plugin tools thin.
5. Put deterministic checks in `stateful-dev`, not in prompts.
6. Let Hermes execute code; do not turn `stateful-dev` into an agent runner.
7. Treat operator-visible blockers as nonzero exits, not silent `wakeAgent:false` skips.
8. Do not create duplicate workers to escape stale locks or bad state.

## Related docs

- [`usage.md`](usage.md) — CLI and plugin usage.
- [`cron-gate-contract.md`](cron-gate-contract.md) — exact `wakeAgent` JSON contract.
- [`cron-gate.md`](cron-gate.md) — wrapper setup and runbook.
- [`plans/`](plans/) — implementation plans used to generate worker state.
