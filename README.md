# stateful-dev

Stateful development worker helper tooling for Hermes cron agents.

This repository provides a small Python CLI and Hermes plugin wrapper that make stateful cron development safer: plan parsing, durable state validation, atomic locking, legal state transitions, evidence capture, and compact reports.

## Quick start

```bash
uv tool install .
stateful-dev --help
stateful-dev doctor --state .agent-state/stateful-dev-worker/state.json --json
```

For local development:

```bash
uv run pytest -q
uv run ruff check .
uv run stateful-dev --help
```

See [docs/usage.md](docs/usage.md) for local installation, `hermes tools enable` plugin setup, `stateful-dev doctor` examples, and the disposable smoke flow.
