# Cron-Gate Wake/Skip JSON Contract

Stable integration contract between Hermes cron scripts and `stateful-dev`.
Defines the wake/skip decision output format emitted by `~/.hermes/scripts/` gate wrappers
and consumed by the Hermes cron scheduler.

---

## Overview

The Hermes cron scheduler runs a shell script before building the agent prompt.
The script's stdout is injected as `## Script Output` into the prompt.
The **last non-empty stdout line** is parsed as JSON to determine whether to run the agent.

```
Hermes cron scheduler  →  runs script  →  last non-empty stdout line is JSON
                                               ↓
                         wakeAgent: true  →  run agent with Script Output
                         wakeAgent: false →  skip agent, suppress delivery [SILENT]
```

---

## Contract Fields

| Field | Type | Description |
|---|---|---|
| `wakeAgent` | `bool` | `true` = run agent with Script Output. `false` = skip agent and suppress delivery. |
| `mode` | `string` | One of: `wake`, `skip`, `blocker`, `error`. |
| `worker_id` | `string` | Stable worker identifier (stateful-dev job name). |
| `run_id` | `string` | Unique run identifier for this cron invocation. |
| `project_root` | `string` | Absolute path to the project root. |
| `state_path` | `string` | Absolute path to the state JSON file. |
| `item_id` | `string\|null` | Claimed or provided item ID, if any. |
| `item_title` | `string\|null` | Title of the claimed or provided item. |
| `item_status` | `string\|null` | Current status of the claimed item. |
| `blocker` | `string\|null` | Human-readable blocker reason, when `mode` is `blocker` or `error`. |
| `complete` | `bool` | `true` when all state items are terminal and no work remains. |
| `message` | `string\|null` | Optional context message for the agent or operator. |

### `mode` Values

- **`wake`** — Work is available. Agent should run and process `item_id`.
- **`skip`** — No work is available. Agent should not run.
- **`blocker`** — Work cannot proceed due to a condition the operator must resolve (e.g., dirty git, stale lock, invalid state, HITL poll failure). Agent should not run.
- **`error`** — Script encountered an internal error (bug, not a business-condition blocker). Agent should not run. Distinguishing `error` from `blocker` lets operators decide whether to page urgently or file a ticket.

---

## Stdout/Stderr Convention

- The script should emit **structured text output** (e.g., status lines) to stdout before the final JSON line.
- stdout is injected as `## Script Output` into the agent prompt when `wakeAgent: true`.
- Only the **last non-empty line** of stdout is parsed as JSON.
- Empty lines are ignored.
- stderr is **not** injected into the prompt and is not parsed for wake/skip decisions.
- For diagnostic purposes, stderr does not affect the wake/skip decision — only the last non-empty stdout line matters.

---

## Nonzero Exit Semantics

- **Exit 0** — Script succeeded. Parse last non-empty stdout line for `wakeAgent` value.
- **Exit nonzero** — Script encountered an internal error. Treat as `mode: error` regardless of stdout content.
  - If the last non-empty stdout line already contains valid `wakeAgent: false`, prefer that as the safe skip signal.
  - If stdout is empty or invalid, Hermes treats this as a script bug (not a business blocker).

---

## Blocker vs. Script-Bug Behavior

| Condition | mode | Agent runs? | Delivery suppressed? | Operator action |
|---|---|---|---|---|
| No eligible work | `skip` | No | Yes | None — expected idle |
| State invalid | `blocker` | No | No (delivery sent) | Must resolve state |
| Lock held, not stale | `blocker` | No | No | Wait for lock holder |
| HITL poll required but failed | `blocker` | No | No | Must resolve poll |
| Dirty git with uncommitted changes | `blocker` | No | No | Must commit or stash |
| Script internal error | `error` | No | No | File a bug report |
| Work available | `wake` | Yes | No | None — expected |

A `blocker` is a business condition that requires operator action before the worker can proceed.
An `error` is a script bug that requires a fix before the worker can proceed.

---

## Last-Line JSON Rule

Only the **last non-empty stdout line** is parsed as JSON.

Example stdout with explanatory lines above the contract line:

```
Running stateful-dev cron-gate for worker stateful-dev-cron-gate-worker
State: valid | Lock: clear | Item: T1-define-cron-gate-wake-skip-json-contract (in_progress)
{"wakeAgent": true, "mode": "wake", "worker_id": "stateful-dev-cron-gate-worker", "run_id": "2026-04-27T10:00:00Z", "project_root": "/Users/xlyk/Code/stateful-dev", "state_path": ".agent-state/stateful-dev-cron-gate-worker/state.json", "item_id": "2026-04-27-104500-stateful-dev-cron-gate-backlog:T1-define-cron-gate-wake-skip-json-contract", "item_title": "Define cron-gate wake/skip JSON contract", "item_status": "in_progress", "blocker": null, "complete": false, "message": "Continuing T1 (in_progress)"}
```

---

## Example Payloads

### Wake — work available, agent should run

```json
{
  "wakeAgent": true,
  "mode": "wake",
  "worker_id": "stateful-dev-cron-gate-worker",
  "run_id": "2026-04-27T10:00:00Z",
  "project_root": "/Users/xlyk/Code/stateful-dev",
  "state_path": ".agent-state/stateful-dev-cron-gate-worker/state.json",
  "item_id": "2026-04-27-104500-stateful-dev-cron-gate-backlog:T1-define-cron-gate-wake-skip-json-contract",
  "item_title": "Define cron-gate wake/skip JSON contract",
  "item_status": "in_progress",
  "blocker": null,
  "complete": false,
  "message": "Continuing T1 (in_progress)"
}
```

### Skip — no work available

```json
{
  "wakeAgent": false,
  "mode": "skip",
  "worker_id": "stateful-dev-cron-gate-worker",
  "run_id": "2026-04-27T10:00:00Z",
  "project_root": "/Users/xlyk/Code/stateful-dev",
  "state_path": ".agent-state/stateful-dev-cron-gate-worker/state.json",
  "item_id": null,
  "item_title": null,
  "item_status": null,
  "blocker": null,
  "complete": true,
  "message": "All 22 items terminal. Worker complete."
}
```

### Blocker — state invalid

```json
{
  "wakeAgent": false,
  "mode": "blocker",
  "worker_id": "stateful-dev-cron-gate-worker",
  "run_id": "2026-04-27T10:00:00Z",
  "project_root": "/Users/xlyk/Code/stateful-dev",
  "state_path": ".agent-state/stateful-dev-cron-gate-worker/state.json",
  "item_id": null,
  "item_title": null,
  "item_status": null,
  "blocker": "stateful-dev doctor failed: count drift detected — pending=21 but item statuses sum to 20",
  "complete": false,
  "message": "State invalid. Resolve before resuming worker."
}
```

### Error — script internal bug

```json
{
  "wakeAgent": false,
  "mode": "error",
  "worker_id": "stateful-dev-cron-gate-worker",
  "run_id": "2026-04-27T10:00:00Z",
  "project_root": "/Users/xlyk/Code/stateful-dev",
  "state_path": ".agent-state/stateful-dev-cron-gate-worker/state.json",
  "item_id": null,
  "item_title": null,
  "item_status": null,
  "blocker": "stateful-dev cron-gate exited with code 1: AttributeError: 'NoneType' object has no attribute 'items'",
  "complete": false,
  "message": "Script bug. File a report before the next scheduled run."
}
```

---

## Ownership Boundary

```
Hermes cron scheduler   —  schedules and runs ~/.hermes/scripts/ gate wrappers
~/.hermes/scripts/       —  thin per-worker adapters (chdir, call stateful-dev cron-gate, emit last-line JSON)
stateful-dev cron-gate  —  deterministic local lifecycle / wake decision engine
Hermes agent            —  coding executor; never makes wake/skip decisions
```

`stateful-dev cron-gate` owns all local state, lock, git-status, claim, and wake/skip decisions.
Scripts under `~/.hermes/scripts/` are thin adapters only. No wake-decision logic belongs in wrapper scripts.

---

## Dependencies

This contract requires `stateful-dev cron-gate` (Task 3 of the cron-gate backlog) to implement the
`wakeAgent` JSON emission. Tasks 1 (contract definition) and 2 (claim/next primitive) are
prerequisites. Task 4 (per-worker wrappers) consumes this contract.
