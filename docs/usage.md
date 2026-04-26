# stateful-dev usage

`stateful-dev` is a local-first helper for stateful cron development workers. Use it to inspect worker state, render reports, and expose the same checked behavior through the local Hermes plugin.

## Install the CLI

From a checkout:

```bash
uv tool install .
stateful-dev --help
```

For development, run commands through the project environment:

```bash
uv run stateful-dev --help
uv run pytest -q
uv run ruff check .
```

## Enable the Hermes plugin

The plugin lives at `plugins/stateful-dev`. Enable it from the Hermes configuration or local tool registry used on the worker host:

```bash
hermes tools enable ./plugins/stateful-dev
```

Keep the plugin thin. The CLI and `stateful_dev` package remain the canonical implementation; plugin tools should call tested library functions and return JSON-serializable payloads.

## Validate worker state

Use `stateful-dev doctor` against a project-local state file before trusting a worker run:

```bash
stateful-dev doctor --state .agent-state/stateful-dev-worker/state.json --json
```

The command reports whether the state shape is valid, lists schema/count errors, and emits recomputed counts. Treat `.agent-state/<job>/state.json` as the execution source of truth. Todoist or other trackers are visibility layers only.

## Disposable smoke flow

Before using the tool on real worker state, run a disposable smoke flow in a temporary directory:

```bash
mkdir -p /tmp/stateful-dev-smoke/.agent-state/demo-worker
cp docs/plans/2026-04-26_095545-stateful-dev-01-foundation.md /tmp/stateful-dev-smoke/plan.md
stateful-dev doctor --state .agent-state/stateful-dev-worker/state.json --json
uv run stateful-dev --help
```

A good smoke flow never touches production worker state. It should use a temp plan/state fixture, validate the state with `stateful-dev doctor`, exercise legal transitions with recorded RED/GREEN evidence, render a compact report, and then delete the temp directory.

## Worker safety rules

- Process one plan item per run until the workflow is proven.
- Verify RED before writing production code.
- Commit only after focused tests, the full suite, and lint pass.
- Do not push from the worker by default.
- Stop and request operator review when the plan is ambiguous or RED cannot be proven.
