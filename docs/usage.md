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

The plugin is a path-enabled plugin. It lives at `plugins/stateful-dev`; it is not installed as a Python package plugin. Enable it from the Hermes configuration or local tool registry used on the worker host:

```bash
hermes tools enable ./plugins/stateful-dev
```

Keep the plugin thin. The CLI and `stateful_dev` package remain the canonical implementation; plugin tools should call tested library functions and return JSON-serializable payloads. The manifest should list the same tools that `register(ctx)` registers.

## Validate worker state

Use `stateful-dev doctor` against a project-local state file before trusting a worker run:

```bash
stateful-dev doctor --state path/to/.agent-state/<job>/state.json --json
```

The command reports whether the state shape is valid, lists schema/count errors, and emits recomputed counts. Treat `.agent-state/<job>/state.json` as the execution source of truth. Todoist or other trackers are visibility layers only.

## Disposable smoke flow

Before using the tool on real worker state, run a disposable smoke flow in a temporary directory. Every command below uses `/tmp/stateful-dev-smoke`, not a production worker state path:

```bash
rm -rf /tmp/stateful-dev-smoke
mkdir -p /tmp/stateful-dev-smoke
cp docs/plans/2026-04-26_095545-stateful-dev-01-foundation.md /tmp/stateful-dev-smoke/plan.md
stateful-dev init --plan /tmp/stateful-dev-smoke/plan.md --state /tmp/stateful-dev-smoke/state.json --job-name demo-worker --project-root /tmp/stateful-dev-smoke --json
stateful-dev doctor --state /tmp/stateful-dev-smoke/state.json --json
stateful-dev transition --state /tmp/stateful-dev-smoke/state.json --item-id '<item-id>' --status in_progress
stateful-dev transition --state /tmp/stateful-dev-smoke/state.json --item-id '<item-id>' --status red_verified --evidence-json '{"focused_red_command":"uv run pytest tests/test_smoke_flow.py::test_disposable_state_flow -q","focused_red_result":"exit 1; expected missing behavior"}'
stateful-dev transition --state /tmp/stateful-dev-smoke/state.json --item-id '<item-id>' --status green_verified --evidence-json '{"focused_green_command":"uv run pytest tests/test_smoke_flow.py::test_disposable_state_flow -q","focused_green_result":"exit 0; 1 passed"}'
stateful-dev transition --state /tmp/stateful-dev-smoke/state.json --item-id '<item-id>' --status succeeded --evidence-json '{"full_suite_command":"uv run pytest -q","full_suite_result":"exit 0; tests passed"}'
stateful-dev report --state /tmp/stateful-dev-smoke/state.json --summary /tmp/stateful-dev-smoke/summary.json
uv run stateful-dev --help
```

A good smoke flow never touches production worker state. It uses a temp plan/state fixture, validates the state with `stateful-dev doctor`, exercises legal transitions with recorded RED/GREEN evidence, renders a compact report, and then deletes the temp directory.

## Worker safety rules

- Process one plan item per run until the workflow is proven.
- Verify RED before writing production code.
- Commit only after focused tests, the full suite, and lint pass.
- Do not push from the worker by default.
- Stop and request operator review when the plan is ambiguous or RED cannot be proven.
