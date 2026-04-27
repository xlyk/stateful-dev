# Script-Backed Cron Gate Runbook

Operator reference for the script-backed Hermes cron wake-gate architecture implemented in this project.

---

## Architecture

```
Hermes cron scheduler  →  runs ~/.hermes/scripts/stateful_dev_<worker>_gate.py
                               │
                               ├── chdir into project root
                               ├── call stateful-dev cron-gate (deterministic local engine)
                               ├── emit last non-empty stdout line as JSON
                               │
                               ▼
              wakeAgent: true  →  run agent with Script Output injected
              wakeAgent: false →  skip agent, suppress delivery [SILENT]
```

**Ownership boundary:**

| Layer | Responsibility |
|---|---|
| Hermes cron scheduler | Schedules and runs gate scripts; parses last stdout line for `wakeAgent` |
| `~/.hermes/scripts/stateful_dev_<worker>_gate.py` | Thin per-worker adapter only — no wake-decision logic |
| `stateful-dev cron-gate` | Owns all deterministic local decisions: state doctor, git status, locks, item selection, claim |
| Hermes agent | Coding executor; never makes wake/skip decisions |

`stateful-dev cron-gate` owns all local state, lock, git-status, claim, and wake/skip decisions.
Scripts under `~/.hermes/scripts/` are thin adapters only. No wake-decision logic belongs in wrappers.

---

## Wrapper Script Example

`~/.hermes/scripts/stateful_dev_stateful-dev-cron-gate-worker_gate.py`:

```python
#!/usr/bin/env python3
"""
Per-worker Hermes cron gate wrapper.
Thin adapter: chdirs into the project root and calls `stateful-dev cron-gate`.
No wake-decision logic lives here.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKER_ID = "stateful-dev-cron-gate-worker"
PROJECT_ROOT = Path("/Users/xlyk/Code/stateful-dev")
STATE_PATH = Path("/Users/xlyk/Code/stateful-dev/.agent-state/stateful-dev-cron-gate-worker/state.json")


def _generate_run_id() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _last_json_line(output: str) -> str | None:
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def _emit_json(payload: dict) -> None:
    print(json.dumps(payload), flush=True)


def _run_cron_gate(run_id: str) -> tuple[int, str, str]:
    cmd = [
        "uv", "run", "--directory", str(PROJECT_ROOT),
        "stateful-dev", "cron-gate",
        "--state", str(STATE_PATH),
        "--project-root", str(PROJECT_ROOT),
        "--worker-id", WORKER_ID,
        "--run-id", run_id,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode, result.stdout, result.stderr


def main() -> None:
    run_id = _generate_run_id()
    print(f"[gate-wrapper] worker={WORKER_ID} run={run_id}", file=sys.stderr, flush=True)

    exit_code, stdout, stderr = _run_cron_gate(run_id)

    # Find last JSON line in stdout only — stderr warnings must not corrupt the contract line.
    last_json = None
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            json.loads(stripped)
            last_json = stripped
            break
        except json.JSONDecodeError:
            continue

    if last_json:
        print(last_json, flush=True)
        if exit_code != 0:
            sys.exit(exit_code)
        return

    # No parseable JSON in stdout
    if exit_code != 0:
        error_payload = {
            "wakeAgent": False, "mode": "error",
            "worker_id": WORKER_ID, "run_id": run_id,
            "project_root": str(PROJECT_ROOT), "state_path": str(STATE_PATH),
            "item_id": None, "item_title": None, "item_status": None,
            "blocker": f"wrapper exited {exit_code} and produced no parseable JSON output",
            "complete": False,
            "message": "Internal error in gate wrapper script. File a bug report.",
        }
        print(json.dumps(error_payload), flush=True)
        sys.exit(exit_code)

    # Exit 0 but no JSON — pass stdout through (should not happen for healthy cron-gate)
    print(stdout.rstrip(), flush=True)


if __name__ == "__main__":
    main()
```

### Key wrapper design points

- **No wake-decision logic** — delegates entirely to `stateful-dev cron-gate`.
- **Last-line JSON rule** — parses stdout in reverse to find the last parseable JSON line, ignoring uv warnings on stderr.
- **Error resilience** — if `cron-gate` exits nonzero with no JSON, emits an `error`-mode fallback payload and exits with the original code so Hermes routes to the notification path.
- **Diagnostic prefix on stderr** — status lines go to stderr so they never corrupt the stdout contract line.

---

## Cron Job Configuration

Register the wrapper as the pre-run script in the Hermes cron job config:

```json
{
  "cron_jobs": [
    {
      "name": "stateful-dev-cron-gate-worker",
      "workdir": "/Users/xlyk/Code/stateful-dev",
      "script": "stateful_dev_stateful-dev-cron-gate-worker_gate.py",
      "restricted_toolsets": ["filesystem", "terminal", "web_search"],
      "schedule": "0 */2 * * *"
    }
  ]
}
```

Replace `stateful_dev_<worker>_gate.py` in the `script` field with the appropriate per-worker wrapper name.

---

## Wake/Skip JSON Contract

See [cron-gate-contract.md](cron-gate-contract.md) for the full contract. The essential fields:

| Field | Type | Description |
|---|---|---|
| `wakeAgent` | `bool` | `true` = run agent. `false` = skip and suppress delivery. |
| `mode` | `string` | `wake` \| `skip` \| `blocker` \| `error` |
| `worker_id` | `string` | Worker identifier |
| `run_id` | `string` | Unique run ID for this invocation |
| `project_root` | `string` | Absolute project root path |
| `state_path` | `string` | Absolute path to the state JSON file |
| `item_id` | `string\|null` | Claimed item ID, if any |
| `item_title` | `string\|null` | Title of the claimed item |
| `item_status` | `string\|null` | Current status of the claimed item |
| `blocker` | `string\|null` | Blocker reason when `mode` is `blocker` or `error` |
| `complete` | `bool` | `true` when all items are terminal |
| `message` | `string\|null` | Optional context message |

### Last-line rule

Only the **last non-empty stdout line** is parsed as JSON. Example:

```
Running stateful-dev cron-gate for worker stateful-dev-cron-gate-worker
State: valid | Lock: clear | Item: T1-define-cron-gate-wake-skip-json-contract (in_progress)
{"wakeAgent": true, "mode": "wake", "worker_id": "stateful-dev-cron-gate-worker", ...}
```

### Mode semantics

| mode | Exit | Agent runs? | Delivery suppressed? | When to use |
|---|---|---|---|---|
| `wake` | 0 | Yes | No | Work available — agent should run |
| `skip` | 0 | No | Yes | No eligible work — expected idle |
| `blocker` | 1 | Yes (Script Error) | No | Operator must resolve a business condition |
| `error` | 1 | Yes (Script Error) | No | Script bug — file a report |

`blocker` and `error` exit nonzero to trigger Hermes' notification path. The JSON payload is still written to stdout so the Script Error prompt contains structured context.

---

## Failure Modes

### State invalid (`blocker`)

`stateful-dev doctor` fails — counts drift, schema errors, or duplicate item IDs.
**Action:** Run `stateful-dev doctor --state <state>.json --json` to diagnose. May require manual state repair or `stateful-dev transition --fix-counts`.

### Lock held, not stale (`blocker`)

Another worker run holds the lock file.
**Action:** Wait for the concurrent run to complete, or investigate stale locks with `stateful-dev lock status --state <state>.json`.

### Dirty git with uncommitted changes (`blocker`)

The working tree has uncommitted changes.
**Action:** Commit, stash, or discard changes before the next run.

### HITL poll required but failed (`blocker`)

Poseidon polling is enabled and the poll returned an error or policy violation.
**Action:** Investigate the Poseidon/HITL integration. Operator must resolve before the worker can proceed.

### Wrapper exited nonzero, no JSON (`error`)

The wrapper script encountered an internal error (bug, not a business condition).
**Action:** File a bug report. Run the wrapper manually to capture stderr for diagnosis:

```bash
cd /Users/xlyk/Code/stateful-dev
uv run --directory . stateful-dev cron-gate \
  --state .agent-state/stateful-dev-cron-gate-worker/state.json \
  --project-root . \
  --worker-id stateful-dev-cron-gate-worker \
  --run-id "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

---

## Local Smoke Tests

Run these locally before trusting a new wrapper or `cron-gate` change against production state.

### Smoke: wrapper emits valid JSON

```bash
cd /Users/xlyk/Code/stateful-dev
python ~/.hermes/scripts/stateful_dev_stateful-dev-cron-gate-worker_gate.py 2>/dev/null \
  | python -c "import sys, json; d = json.load(sys.stdin); assert 'wakeAgent' in d; print(d['mode'], d['wakeAgent'])"
```

### Smoke: skip when no work remains

```bash
# Touch the state file so all items are terminal, then run the wrapper
# It should emit {"wakeAgent": false, "mode": "skip", "complete": true}
python ~/.hermes/scripts/stateful_dev_stateful-dev-cron-gate-worker_gate.py 2>/dev/null \
  | python -c "import sys, json; d = json.load(sys.stdin); \
    assert d.get('complete') == True, 'expected complete=True'; \
    assert d.get('wakeAgent') == False, 'expected wakeAgent=False'; \
    print('skip-when-complete smoke PASSED')"
```

### Smoke: cron-gate command alone

```bash
uv run stateful-dev cron-gate \
  --state .agent-state/stateful-dev-cron-gate-worker/state.json \
  --project-root . \
  --worker-id stateful-dev-cron-gate-worker \
  --run-id "smoke-test-$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --json
```

Expected: exits 0, prints valid `wakeAgent` JSON to stdout.

### Smoke: doctor before and after

```bash
uv run stateful-dev doctor --state .agent-state/stateful-dev-cron-gate-worker/state.json --json
# Expect: ok=true, no errors
```

---

## Migration Steps

To migrate an existing worker to script-backed wake gates:

1. **Ensure `stateful-dev cron-gate` is implemented and tested.** This is a prerequisite — do not create wrapper scripts before the command exists.

2. **Generate the per-worker wrapper:**
   - Wrapper lives at `~/.hermes/scripts/stateful_dev_<worker-id>_gate.py`.
   - Hardcode `WORKER_ID`, `PROJECT_ROOT`, and `STATE_PATH`.
   - Call `uv run --directory <project-root> stateful-dev cron-gate` with the required flags.
   - Emit the last non-empty stdout line as the JSON contract line.

3. **Register the wrapper in the Hermes cron job config:**
   ```json
   { "script": "stateful_dev_<worker-id>_gate.py" }
   ```

4. **Run one no-work smoke test** — confirm `wakeAgent: false` is emitted when all items are terminal.

5. **Run one work wake smoke test** — confirm `wakeAgent: true` and a valid `item_id` are emitted when eligible work exists.

6. **Verify state remains valid** after the smoke runs:
   ```bash
   uv run stateful-dev doctor --state .agent-state/<worker>/state.json --json
   ```

7. **Do not migrate real workers** until wake, skip, blocker, nonzero exit, stdout, and stderr behavior have been smoke-tested against the live scheduler. See also: [HERMES.md](../HERMES.md) operational pitfalls.

---

## Per-Worker Wrapper Requirements

| Requirement | Rationale |
|---|---|
| Hardcoded `WORKER_ID`, `PROJECT_ROOT`, `STATE_PATH` | Wrappers must not accept dynamic configuration at runtime from the scheduler |
| `uv run --directory <project-root>` | Ensures the project `.venv` is used regardless of caller's `VIRTUAL_ENV` |
| Last-line JSON from stdout only | stderr warnings from `uv` must not corrupt the contract line |
| Error fallback with `error` mode | Internal errors must exit nonzero with a structured payload so Hermes routes to notification |
| Diagnostic prefix on stderr | Status lines must not appear in stdout's last-line JSON |
