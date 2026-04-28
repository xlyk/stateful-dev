# stateful-dev

`stateful-dev` is local-first safety tooling for stateful Hermes cron coding workers.

It turns a markdown implementation plan into durable worker state, then gives agents and operators checked commands for claiming work, recording evidence, enforcing legal transitions, handling locks, rendering handoffs, and deciding whether a scheduled cron run should wake an agent.

It is not an autonomous coder, scheduler, PR bot, or project manager. The JSON state file is the execution source of truth; Todoist, Discord, GitHub, and other systems are visibility or transport layers.

## Why it exists

Cron-launched coding workers are useful but brittle when progress only lives in prompts or hand-edited JSON. `stateful-dev` makes the worker lifecycle explicit and inspectable:

- parse plan files into stable item IDs
- store progress in `.agent-state/<worker>/state.json`
- validate state shape, counts, locks, and drift
- claim exactly one eligible item per run
- enforce legal status transitions
- require RED/GREEN/full-suite evidence before success
- render compact status, completion audits, and operator handoffs
- provide a deterministic Hermes cron wake/skip gate

## Architecture

```text
markdown plan files
        │
        ▼
stateful-dev init / state sync-plans
        │
        ▼
.agent-state/<worker>/state.json
        │
        ├── doctor/status/complete validate operator-visible state
        ├── claim/transition/record move one item through the lifecycle
        ├── lock/run commands preserve resumability
        ├── handoff/report render compact operator context
        └── cron-gate emits Hermes wake/skip JSON
        │
        ▼
Hermes plugin + Hermes cron script wrappers
```

For script-backed cron workers, the responsibility boundary is strict:

| Layer | Responsibility |
| --- | --- |
| Hermes cron | schedules jobs, runs optional pre-run scripts, launches the agent |
| `~/.hermes/scripts/stateful_dev_<worker>_gate.py` | thin per-worker adapter: `chdir`, call `stateful-dev cron-gate`, preserve JSON/exit semantics |
| `stateful-dev cron-gate` | deterministic local wake/skip/claim decision engine |
| Hermes agent | coding executor; does not decide whether work should be claimed |

See [`docs/system-integration.md`](docs/system-integration.md) for how `stateful-dev`, Poseidon, Hermes cron, and the Hermes plugin work together. See [`docs/cron-gate-contract.md`](docs/cron-gate-contract.md) for the scheduler contract and [`docs/cron-gate.md`](docs/cron-gate.md) for the runbook.

## Install

From a checkout:

```bash
uv tool install .
stateful-dev --help
```

For local development, prefer the project environment:

```bash
uv run stateful-dev --help
uv run pytest -q
uv run ruff check .
```

Requires Python 3.11+.

## Core commands

```bash
# Inspect the CLI
uv run stateful-dev --help
uv run stateful-dev version

# Create state from a markdown plan
uv run stateful-dev init \
  --plan docs/plans/example.md \
  --state .agent-state/my-worker/state.json \
  --job-name my-worker \
  --project-root "$PWD" \
  --json

# Validate and summarize state
uv run stateful-dev doctor --state .agent-state/my-worker/state.json --json
uv run stateful-dev status --state .agent-state/my-worker/state.json --json

# Claim work for a run
uv run stateful-dev claim \
  --state .agent-state/my-worker/state.json \
  --run-id "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Move an item through the evidence-gated lifecycle
uv run stateful-dev transition --state .agent-state/my-worker/state.json --item-id ITEM --status in_progress
uv run stateful-dev transition --state .agent-state/my-worker/state.json --item-id ITEM --status red_verified \
  --evidence-json '{"focused_red_command":"uv run pytest tests/test_feature.py -q","focused_red_result":"exit 1; expected failure"}'
uv run stateful-dev transition --state .agent-state/my-worker/state.json --item-id ITEM --status green_verified \
  --evidence-json '{"focused_green_command":"uv run pytest tests/test_feature.py -q","focused_green_result":"exit 0; 1 passed"}'
uv run stateful-dev transition --state .agent-state/my-worker/state.json --item-id ITEM --status succeeded \
  --evidence-json '{"full_suite_command":"uv run pytest -q","full_suite_result":"exit 0; suite passed"}'
```

Important subcommands:

| Command | Purpose |
| --- | --- |
| `init` | create initial state from a markdown plan |
| `doctor` | validate state shape, item statuses, and counts |
| `status` | summarize active/next work for operators and agents |
| `claim` | atomically claim one eligible item or return the active item |
| `transition` | move an item through the legal lifecycle |
| `record-red`, `record-green`, `record-full-suite`, `record-lint` | append gate evidence |
| `lock status`, `lock recover` | inspect or recover stale worker locks |
| `run start`, `run finish`, `run fail` | track per-run lifecycle records |
| `handoff` | render copy-paste-ready operator context for blocked work |
| `complete` | audit whether a worker is safe to shut down |
| `cron-gate` | emit Hermes `wakeAgent` JSON for script-backed cron jobs |
| `plan lint`, `plan parse` | validate and inspect markdown plan structure |
| `state sync-plans` | add missing plan items to existing state without mutating statuses |
| `profile validate`, `profile render` | validate deployment profiles and render executor prompts |
| `hitl poll-before-run` | poll Poseidon HITL events and stage run markers before claim |

## State model

Plan headings like this become durable items:

```markdown
## Task 1: Add the first capability
```

Each item gets a stable ID derived from the plan filename, task number, and title. Items move through the normal success path:

```text
pending -> in_progress -> red_verified -> green_verified -> succeeded
```

The state file also supports terminal or operator states such as `blocked`, `failed_final`, `failed_retryable`, `needs_review`, and `skipped`. `doctor` recomputes counts from item statuses and fails on drift or malformed state.

## Script-backed Hermes cron gates

`stateful-dev cron-gate` is the deterministic wake/skip engine for Hermes cron jobs. It checks:

- state validity
- lock status
- dirty git state
- active item resumability
- eligible item claimability
- optional Poseidon HITL poll markers

It emits a final JSON line containing `wakeAgent`:

```bash
uv run stateful-dev cron-gate \
  --state .agent-state/my-worker/state.json \
  --project-root "$PWD" \
  --worker-id my-worker \
  --run-id "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --json
```

Current Hermes behavior matters:

- exit `0` + `wakeAgent: true` wakes the agent
- exit `0` + `wakeAgent: false` skips the agent and suppresses delivery
- nonzero exit runs the agent through Hermes' script-error path so a blocker can be reported

Wrapper scripts must preserve nonzero `blocker`/`error` exits. Converting them into exit-0 skips makes operator-visible blockers silent.

## Manual script-backed worker setup

There is not yet an installer for wrapper scripts. Until `stateful-dev` grows a `worker install` or `profile apply` command, create the wrapper and Hermes cron job manually.

Assume:

```bash
WORKER_ID=my-worker
PROJECT_ROOT=/absolute/path/to/project
STATE_PATH="$PROJECT_ROOT/.agent-state/$WORKER_ID/state.json"
SCRIPT_PATH="$HOME/.hermes/scripts/stateful_dev_${WORKER_ID}_gate.py"
```

### 1. Create state from a plan

Your plan must use `## Task N: Title` headings.

```bash
cd "$PROJECT_ROOT"
uv run stateful-dev init \
  --plan docs/plans/<plan>.md \
  --state "$STATE_PATH" \
  --job-name "$WORKER_ID" \
  --project-root "$PROJECT_ROOT" \
  --json
uv run stateful-dev doctor --state "$STATE_PATH" --json
```

### 2. Create the Hermes cron gate wrapper

The wrapper lives in `~/.hermes/scripts/`. It must stay a thin adapter: call `stateful-dev cron-gate`, emit the last JSON line, and preserve nonzero exits.

```bash
mkdir -p "$HOME/.hermes/scripts"
cat > "$SCRIPT_PATH" <<'PY'
#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKER_ID = "my-worker"
PROJECT_ROOT = Path("/absolute/path/to/project")
STATE_PATH = PROJECT_ROOT / ".agent-state" / WORKER_ID / "state.json"


def _run_id() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    run_id = _run_id()
    print(f"[gate-wrapper] worker={WORKER_ID} run={run_id}", file=sys.stderr, flush=True)

    result = subprocess.run(
        [
            "uv", "run", "--directory", str(PROJECT_ROOT),
            "stateful-dev", "cron-gate",
            "--state", str(STATE_PATH),
            "--project-root", str(PROJECT_ROOT),
            "--worker-id", WORKER_ID,
            "--run-id", run_id,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    last_json = None
    for line in reversed(result.stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
        except json.JSONDecodeError:
            continue
        last_json = stripped
        break

    if last_json:
        print(last_json, flush=True)
        if result.returncode != 0:
            sys.exit(result.returncode)
        return

    if result.returncode != 0:
        print(json.dumps({
            "wakeAgent": False,
            "mode": "error",
            "worker_id": WORKER_ID,
            "run_id": run_id,
            "project_root": str(PROJECT_ROOT),
            "state_path": str(STATE_PATH),
            "item_id": None,
            "item_title": None,
            "item_status": None,
            "blocker": f"wrapper exited {result.returncode} and produced no parseable JSON output",
            "complete": False,
            "message": "Internal error in gate wrapper script.",
        }), flush=True)
        sys.exit(result.returncode)

    print(result.stdout.rstrip(), flush=True)


if __name__ == "__main__":
    main()
PY
chmod +x "$SCRIPT_PATH"
```

Replace `WORKER_ID`, `PROJECT_ROOT`, and `STATE_PATH` inside the generated script before using it.

### 3. Smoke-test the wrapper

The final stdout line must be JSON and include `wakeAgent`.

```bash
python "$SCRIPT_PATH" 2>/dev/null \
  | python -c 'import json,sys; d=json.load(sys.stdin); assert "wakeAgent" in d; print(d["mode"], d["wakeAgent"])'
```

If this fails, do not create the cron job yet. Run the underlying command directly:

```bash
cd "$PROJECT_ROOT"
uv run stateful-dev cron-gate \
  --state "$STATE_PATH" \
  --project-root "$PROJECT_ROOT" \
  --worker-id "$WORKER_ID" \
  --run-id "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --json
```

### 4. Register the Hermes cron job

Use Hermes' `cronjob` tool/API and set `script` to the wrapper filename, not the absolute path.

```python
cronjob(action="create",
    name="my-worker",
    schedule="every 5m",
    prompt="You are a stateful-dev cron coding worker. Process the item provided in Script Output using the stateful-dev-lean-worker protocol.",
    skills=["stateful-dev-lean-worker"],
    script="stateful_dev_my-worker_gate.py",
    workdir="/absolute/path/to/project",
    enabled_toolsets=["terminal", "file", "skills"],
    deliver="discord:#notifications")
```

Recommended defaults:

- one worker per repo/worktree/state file;
- lean prompt plus `stateful-dev-lean-worker` skill;
- `terminal,file,skills` toolsets unless the plan needs more;
- Discord notifications for blockers/completion, not routine idle skips.

### 5. Verify after registration

```bash
uv run stateful-dev doctor --state "$STATE_PATH" --json
uv run stateful-dev status --state "$STATE_PATH" --json
python "$SCRIPT_PATH" 2>/dev/null \
  | python -c 'import json,sys; print(json.load(sys.stdin)["mode"])'
```

Then list Hermes cron jobs and confirm the job has the expected `script`, `workdir`, skill, and toolsets.

## Hermes plugin

The plugin lives at [`plugins/stateful-dev`](plugins/stateful-dev). It exposes thin Hermes tool wrappers around tested library behavior.

```bash
hermes tools enable ./plugins/stateful-dev
```

The CLI and `stateful_dev` package remain canonical. Plugin tools should stay thin and JSON-serializable. The plugin manifest and registered plugin tools are mechanically checked.

Plugin tools currently include:

- `stateful_dev_doctor`
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
- `stateful_dev_report`

## Safety rules for workers

- Treat `.agent-state/<worker>/state.json` as authoritative.
- Process one plan item per run until the workflow is proven.
- Verify RED before implementing production behavior.
- Record focused GREEN and full-suite evidence before marking success.
- Commit only after focused checks, full suite, and lint pass.
- Do not push from workers by default.
- Stop and request operator review when the plan is ambiguous, RED cannot be proven, state is invalid, or HITL validation fails.
- Do not hand-edit state unless recovery requires it; prefer CLI/plugin commands.

## Development checks

Run these before trusting changes:

```bash
uv run pytest -q
uv run ruff check .
uv build
```

For wrapper-specific changes, also run the hermetic wrapper tests:

```bash
HOME="$(mktemp -d)" uv run pytest tests/test_wrapper_scripts.py -q
```

For real worker state, verify health before and after changes:

```bash
uv run stateful-dev doctor --state .agent-state/<worker>/state.json --json
uv run stateful-dev status --state .agent-state/<worker>/state.json --json
```

## Documentation

- [`docs/usage.md`](docs/usage.md) — CLI/plugin usage and disposable smoke flow
- [`docs/system-integration.md`](docs/system-integration.md) — how stateful-dev, Poseidon, Hermes cron, and the Hermes plugin fit together
- [`docs/cron-gate-contract.md`](docs/cron-gate-contract.md) — stable wake/skip JSON contract
- [`docs/cron-gate.md`](docs/cron-gate.md) — script-backed cron gate runbook
- [`docs/plans/`](docs/plans/) — milestone and backlog plans used to generate worker state

## Maturity

This is local worker infrastructure for stateful development automation. It is useful because it keeps plan progress, evidence, locks, and wake decisions durable and reviewable. It intentionally stops short of full orchestration: scheduling remains in Hermes cron, code execution remains in the agent, and live side effects remain operator-gated.
