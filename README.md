# stateful-dev

`stateful-dev` is local-first helper tooling for stateful Hermes cron development workers.

It turns the worker protocol into executable checks: parse milestone plans, create durable JSON state, validate state drift, enforce legal task transitions, require TDD evidence, and render compact operator reports. It is a safety harness for autonomous coding workers, not a general project manager or orchestration framework.

## What it is for

Use `stateful-dev` when a cron-launched coding worker needs to work through plan files one item at a time while preserving durable progress state.

It helps answer:

- Which plan item is active?
- Is the state file still valid?
- Did counts drift from item statuses?
- Did the worker prove RED before GREEN?
- Did the worker run the focused test, full suite, and lint gates before success?
- What compact status should be sent to the operator?

## What it is not

`stateful-dev` does not write code, schedule agents, manage PRs, or replace Todoist. Todoist and similar trackers are visibility layers; the JSON state file remains the execution source of truth.

Non-goals for v1:

- autonomous code generation
- multi-agent scheduling
- GitHub PR automation
- database-backed coordination
- GUI/TUI workflow management
- unsupervised live side effects

## Core workflow

```text
Markdown milestone plans
        │
        ▼
plan_parser.py
        │
        ▼
durable JSON state file
        │
        ├── doctor/state.py validates shape and counts
        ├── transitions.py enforces legal progress and evidence
        ├── reports.py renders operator/status summaries
        └── locking.py provides filesystem lock primitives
        │
        ▼
Typer CLI
        │
        ▼
Hermes plugin wrapper
```

## Features

### Plan parsing

`stateful-dev init` parses milestone plans with task headings:

```markdown
## Task 1: Add the first capability
```

Each task becomes a state item with a stable ID derived from the plan filename, task number, and title.

### State validation

`stateful-dev doctor` validates durable worker state and reports:

- required top-level keys
- item list shape
- missing or duplicate item IDs
- invalid statuses
- count drift between `counts` and item statuses

Example:

```bash
stateful-dev doctor --state .agent-state/stateful-dev-worker/state.json --json
```

### Legal transitions

`stateful-dev transition` moves one item through the allowed state machine:

```text
pending -> in_progress -> red_verified -> green_verified -> succeeded
```

It prevents invalid jumps such as `pending -> succeeded`.

### Evidence gates

Transitions require evidence at the right points:

- `red_verified` requires focused RED command/result evidence.
- `green_verified` requires prior RED evidence.
- `succeeded` requires RED, focused GREEN, and full-suite evidence.

### Reports

`stateful-dev report` renders compact batch output for operator updates:

- processed count
- succeeded/failed/review counts
- remaining count
- gate results
- Todoist visibility fields, if provided
- state path
- next action

### Hermes plugin

The plugin wrapper exposes checked library behavior to Hermes tools. The CLI and `stateful_dev` package remain the canonical implementation; plugin tools should stay thin.

## Install

From a checkout:

```bash
uv tool install .
stateful-dev --help
```

For local development:

```bash
uv run stateful-dev --help
uv run pytest -q
uv run ruff check .
```

## Enable the Hermes plugin

The plugin lives at `plugins/stateful-dev`.

```bash
hermes tools enable ./plugins/stateful-dev
```

See [docs/usage.md](docs/usage.md) for the current plugin setup and disposable smoke flow.

## CLI

```bash
stateful-dev version
stateful-dev init --plan PLAN.md --state STATE.json --job-name JOB --project-root ROOT
stateful-dev doctor --state STATE.json --json
stateful-dev transition --state STATE.json --item-id ITEM --status in_progress
stateful-dev report --state STATE.json --summary RUN_SUMMARY.json
```

## Usefulness

This project is useful for a narrow, real problem: making stateful cron coding workers safer and less dependent on manual JSON edits or implicit protocol memory.

The useful abstraction is:

- plan item
- durable state
- legal transition
- evidence gate
- compact report
- thin plugin wrapper

That is enough to turn a fragile agent workflow into something inspectable and recoverable without turning the project into a full orchestration platform.

## Current maturity

This is a partially hardened v1.

Known gaps under active hardening:

- CLI write paths need full lock usage and atomic replace before the tool should be trusted with important state.
- `init` should refuse to overwrite existing state unless explicitly forced.
- state validation should reject more malformed field types.
- evidence validation should reject obvious bogus RED/GREEN result strings.
- the plugin manifest and registered plugin tools should stay mechanically checked.
- the documented smoke flow should only use disposable state paths.

Until those are complete and verified, treat `stateful-dev` as promising worker infrastructure, not trusted production infrastructure.

## Worker safety rules

- Process one plan item per run until the workflow is proven.
- Verify RED before writing production code.
- Commit only after focused tests, the full suite, and lint pass.
- Do not push from the worker by default.
- Stop and request operator review when the plan is ambiguous or RED cannot be proven.

## Verification

Before trusting changes:

```bash
uv run pytest -q
uv run ruff check .
uv run stateful-dev --help
```

For state changes, also run:

```bash
stateful-dev doctor --state .agent-state/stateful-dev-worker/state.json --json
```
