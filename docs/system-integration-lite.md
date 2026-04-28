# Stateful-dev System Integration — Lite

This is the quick mental model for how `stateful-dev`, Poseidon, Hermes cron, and the Hermes plugin work together.

For the detailed reference, see [`system-integration.md`](system-integration.md).

Related repos:

- [Poseidon](https://github.com/xlyk/poseidon) — remote HITL mailbox/control plane.
- [Hermes plugins](https://github.com/xlyk/hermes-plugins) — plugin archive for reusable Hermes plugin code.
- [`plugins/stateful-dev/`](../plugins/stateful-dev/) — the in-repo stateful-dev Hermes plugin source.

## The one-line model

Hermes schedules the run. `stateful-dev` decides whether work is safe to claim. Poseidon carries operator decisions. The Hermes agent does the coding. The plugin gives the agent safe tools to update state.

## The flow

```text
Plan file
  -> .agent-state/<worker>/state.json
  -> Hermes cron starts a scheduled run
  -> wrapper script calls stateful-dev cron-gate
  -> cron-gate checks state, git, locks, and HITL
  -> cron-gate claims one safe item
  -> Hermes agent implements that item
  -> agent records evidence and transitions state
```

## What each piece does

| Piece | Job |
| --- | --- |
| `stateful-dev` | Local state machine. Validates state, checks locks, claims work, records evidence, and enforces legal transitions. |
| `.agent-state/<worker>/state.json` | Source of truth for what work exists, what status it is in, and what evidence proves it. |
| Hermes cron | Scheduler. Starts runs on a timer and can run a preflight script first. |
| Wrapper script | Thin adapter under `~/.hermes/scripts/`. Calls `stateful-dev cron-gate`; does not make decisions itself. |
| `stateful-dev cron-gate` | Wake gate. Decides: run agent, skip silently, or report a blocker. |
| Poseidon | Remote mailbox for human/operator decisions. It does not mutate local state directly. |
| Hermes agent | Coding executor. Processes the one claimed item and stops. |
| `plugins/stateful-dev` | Hermes tool wrappers for the same safe state operations exposed by the CLI. |

## The key boundary

`stateful-dev` is not the coder and Hermes is not the state machine.

```text
Hermes cron       = when to run
stateful-dev      = whether it is safe to run and what item to run
Poseidon          = operator decisions
Hermes agent      = implementation work
Hermes plugin     = safe state tools inside the agent runtime
```

Keeping those roles separate prevents prompt-only logic, duplicate state machines, and hidden side effects.

## What happens before an agent wakes

`stateful-dev cron-gate` runs before the agent. It checks:

1. Is the state file valid?
2. Is git clean enough to work?
3. Is there a fresh lock from another run?
4. If HITL is enabled, did this run poll Poseidon successfully?
5. Is there an active, pending, or retryable item to process?

Then it emits a `wakeAgent` JSON result:

| Result | Meaning |
| --- | --- |
| `wake` | Work is safe. Run the agent with one item. |
| `skip` | No work is available. Skip silently. |
| `blocker` | Something needs operator attention: dirty git, invalid state, lock, failed HITL poll. |
| `error` | The gate itself broke. Fix the system before continuing. |

## How Poseidon fits

Poseidon is the human-in-the-loop mailbox.

When a worker needs an operator decision, Poseidon stores the request and later stores the response event. The local worker polls Poseidon before claiming work.

Routing uses durable IDs, not chat text or cron IDs:

```text
node_id + worker_id + request_id + item_id + state_path_hash
```

If HITL is required and polling fails, `stateful-dev` blocks the run. That prevents the agent from coding past an operator decision it has not seen.

## How the plugin fits

The Hermes plugin exposes `stateful-dev` operations as tools, for example:

- check status
- claim work
- record RED/GREEN/full-suite/lint evidence
- transition an item
- inspect or recover locks
- render a handoff
- audit completion

The plugin should stay thin. The CLI/package are canonical; plugin tools should not reimplement lifecycle rules.

## The safety rules

- Local state is authoritative.
- Process one item per run by default.
- Do not claim work without validating state.
- Do not bypass locks.
- Do not continue if required Poseidon polling fails.
- Do not mark work done without RED/GREEN/full-suite evidence.
- Use blocker/error notifications for problems; use silent skip only when there is no work.
- Keep wrapper scripts and plugin tools thin.

## Where to look next

- Full architecture: [`system-integration.md`](system-integration.md)
- Cron gate contract: [`cron-gate-contract.md`](cron-gate-contract.md)
- Wrapper runbook: [`cron-gate.md`](cron-gate.md)
- CLI/plugin usage: [`usage.md`](usage.md)
