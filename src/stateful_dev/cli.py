import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from stateful_dev import __version__
from stateful_dev.locking import (
    FreshLockError,
    LockError,
    acquire_lock,
    release_lock,
    write_json_atomic,
)
from stateful_dev.output import to_json
from stateful_dev.plan_parser import parse_plan_tasks
from stateful_dev.reports import render_batch_report
from stateful_dev.state import VALID_STATUSES, validate_state
from stateful_dev.status import build_status, render_status
from stateful_dev.transitions import transition_item

app = typer.Typer(help="Stateful development worker utilities.")


def _empty_counts() -> dict[str, int]:
    return {status: 0 for status in VALID_STATUSES}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    write_json_atomic(path, data)


def _lock_run_id(command: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    return f"stateful-dev-{command}-{stamp}"


def _exit_lock_error(error: LockError) -> None:
    typer.echo(str(error))
    raise typer.Exit(1) from error


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise typer.BadParameter("JSON file must contain an object")
    return data


def _build_initial_state(
    *, plan: Path, state_path: Path, job_name: str, project_root: Path
) -> dict[str, Any]:
    tasks = parse_plan_tasks(plan)
    counts = _empty_counts()
    counts["pending"] = len(tasks)
    now = datetime.now(UTC).isoformat()
    return {
        "job_name": job_name,
        "version": 1,
        "project_root": str(project_root),
        "plan_paths": [str(plan)],
        "state_path": str(state_path),
        "created_at": now,
        "updated_at": now,
        "counts": counts,
        "items": [
            {
                "id": task.item_id,
                "plan_path": str(task.plan_path),
                "title": task.title,
                "status": "pending",
                "attempts": 0,
                "max_attempts": 3,
                "red_verified": False,
                "green_verified": False,
                "full_suite_verified": False,
                "files_touched": [],
                "test_commands": [],
                "commit_sha": None,
                "needs_operator": False,
                "result": None,
            }
            for task in tasks
        ],
    }


@app.callback()
def main() -> None:
    """Stateful development worker utilities."""


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command()
def doctor(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Validate a durable worker state file."""
    data = json.loads(state.read_text(encoding="utf-8"))
    result = validate_state(data)
    payload = {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
        "counts": result.counts,
    }
    if as_json:
        typer.echo(to_json(payload), nl=False)
    else:
        typer.echo("ok" if result.ok else "invalid")
    if not result.ok:
        raise typer.Exit(1)


@app.command()
def init(
    plan: Annotated[Path, typer.Option("--plan", exists=True, readable=True)],
    state: Annotated[Path, typer.Option("--state")],
    job_name: Annotated[str, typer.Option("--job-name")],
    project_root: Annotated[Path, typer.Option("--project-root")],
    as_json: Annotated[bool, typer.Option("--json")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Create a disposable state file from a plan."""
    if state.exists() and not force:
        typer.echo(f"state file already exists: {state}")
        raise typer.Exit(1)

    lock = None
    try:
        lock = acquire_lock(state.parent, _lock_run_id("init"), timeout_minutes=60)
        payload = _build_initial_state(
            plan=plan,
            state_path=state,
            job_name=job_name,
            project_root=project_root,
        )
        _write_json(state, payload)
    except (FreshLockError, LockError) as error:
        _exit_lock_error(error)
    finally:
        if lock is not None:
            release_lock(lock)
    if as_json:
        typer.echo(to_json(payload), nl=False)
    else:
        typer.echo(f"initialized {len(payload['items'])} item(s)")


@app.command()
def status(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Summarize worker lifecycle status for operators and cron workers."""
    payload = build_status(state, _load_json(state))
    if as_json:
        typer.echo(to_json(payload), nl=False)
    else:
        typer.echo(render_status(payload), nl=False)
    if not payload["ok"]:
        raise typer.Exit(1)


@app.command()
def transition(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    item_id: Annotated[str, typer.Option("--item-id")],
    status: Annotated[str, typer.Option("--status")],
    evidence_json: Annotated[str | None, typer.Option("--evidence-json")] = None,
) -> None:
    """Move one item through a legal status transition."""
    evidence = json.loads(evidence_json) if evidence_json else None
    if evidence is not None and not isinstance(evidence, dict):
        raise typer.BadParameter("--evidence-json must contain an object")
    lock = None
    try:
        lock = acquire_lock(
            state.parent, _lock_run_id("transition"), timeout_minutes=60
        )
        payload = transition_item(_load_json(state), item_id, status, evidence)
        payload["updated_at"] = datetime.now(UTC).isoformat()
        _write_json(state, payload)
    except (FreshLockError, LockError) as error:
        _exit_lock_error(error)
    finally:
        if lock is not None:
            release_lock(lock)
    typer.echo(to_json(payload), nl=False)


@app.command()
def claim(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    run_id: Annotated[str, typer.Option("--run-id")],
) -> None:
    """Atomically select and claim one eligible item or return an existing active item.

    Validates state first; exits non-zero if invalid.
    Respects fresh locks; exits non-zero if a non-stale lock is held.
    Returns an active item (in_progress/red_verified/green_verified) as-is.
    If no active item, atomically claims the first eligible item
    (failed_retryable then pending), increments its attempts, and records run_id.
    Emits compact JSON with claimed flag, item, and run_id.
    """
    from stateful_dev.locking import FreshLockError, LockError
    from stateful_dev.state import validate_state
    from stateful_dev.status import ACTIVE_STATUSES, ELIGIBLE_STATUSES

    data = _load_json(state)
    validation = validate_state(data)
    if not validation.ok:
        for err in validation.errors:
            typer.echo(f"state error: {err}")
        raise typer.Exit(1)

    lock = None
    try:
        lock = acquire_lock(state.parent, _lock_run_id("claim"), timeout_minutes=60)

        items = data.get("items", [])
        active = next(
            (
                item
                for item in items
                if isinstance(item, dict) and item.get("status") in ACTIVE_STATUSES
            ),
            None,
        )
        if active is not None:
            payload = {
                "claimed": True,
                "item": {
                    "id": active.get("id"),
                    "title": active.get("title"),
                    "status": active.get("status"),
                    "attempts": active.get("attempts", 0),
                },
                "run_id": run_id,
            }
            typer.echo(to_json(payload), nl=False)
            return

        eligible_candidates = [
            item for item in items
            if isinstance(item, dict) and item.get("status") in ELIGIBLE_STATUSES
        ]
        if not eligible_candidates:
            payload = {
                "claimed": False,
                "item": None,
                "run_id": run_id,
            }
            typer.echo(to_json(payload), nl=False)
            return

        # Select in priority order: failed_retryable first, then pending
        def _priority(item: dict) -> int:
            return 0 if item.get("status") == "failed_retryable" else 1

        chosen = min(eligible_candidates, key=_priority)
        chosen["status"] = "in_progress"
        chosen["attempts"] = chosen.get("attempts", 0) + 1

        # Recompute counts
        counts = {s: 0 for s in VALID_STATUSES}
        for item in data.get("items", []):
            s = item.get("status")
            if s in counts:
                counts[s] += 1
        data["counts"] = counts
        data["updated_at"] = datetime.now(UTC).isoformat()

        _write_json(state, data)

        payload = {
            "claimed": True,
            "item": {
                "id": chosen.get("id"),
                "title": chosen.get("title"),
                "status": chosen.get("status"),
                "attempts": chosen.get("attempts", 0),
            },
            "run_id": run_id,
        }
        typer.echo(to_json(payload), nl=False)

    except (FreshLockError, LockError) as error:
        _exit_lock_error(error)
    finally:
        if lock is not None:
            release_lock(lock)


@app.command()
def cron_gate(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    project_root: Annotated[Path, typer.Option("--project-root")],
    worker_id: Annotated[str, typer.Option("--worker-id")],
    run_id: Annotated[str, typer.Option("--run-id")],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Emit the cron-gate wake/skip decision JSON for Hermes cron.

    Owns deterministic local wake/skip decisions:
    - validates state via doctor
    - checks git status for uncommitted changes
    - checks lock state
    - resumes active items
    - claims eligible items when no active item exists
    - emits the contract-defined wakeAgent JSON payload

    Does not acquire a long-lived lock; claim is called internally for eligible items,
    which acquires/releases a short lock as needed.
    """
    import subprocess
    from datetime import UTC, timedelta

    from stateful_dev.locking import LOCK_DIR_NAME, LOCK_METADATA_NAME, _read_metadata
    from stateful_dev.state import validate_state
    from stateful_dev.status import ELIGIBLE_STATUSES, build_status

    # 1. Load and validate state
    data = _load_json(state)
    validation = validate_state(data)
    state_ok = validation.ok

    # 2. Git status check
    git_dirty = False
    git_reason = ""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout.strip():
            git_dirty = True
            git_reason = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        # git unavailable — not a blocker, just skip
        pass

    # 3. Lock check
    lock_path = state.parent / LOCK_DIR_NAME
    lock_metadata_path = lock_path / LOCK_METADATA_NAME
    lock_held = lock_path.exists()
    lock_stale = False
    if lock_held:
        meta = _read_metadata(lock_path)
        acquired_at = meta.get("acquired_at")
        if isinstance(acquired_at, str):
            try:
                acquired = datetime.fromisoformat(acquired_at)
                if acquired.tzinfo is None:
                    acquired = acquired.replace(tzinfo=UTC)
                lock_stale = (datetime.now(UTC) - acquired) >= timedelta(minutes=60)
            except ValueError:
                lock_stale = True
        else:
            lock_stale = True

    lock_blocked = lock_held and not lock_stale

    # 4. Build status payload
    status_payload = build_status(state, data)

    # 5. Determine mode and payload
    def _item_fields(item: dict | None) -> tuple[str | None, str | None, str | None]:
        if item is None:
            return None, None, None
        return item.get("id"), item.get("title"), item.get("status")

    def _build_payload(
        mode: str,
        *,
        wake_agent: bool,
        blocker: str | None = None,
        message: str | None = None,
        item_id: str | None = None,
        item_title: str | None = None,
        item_status: str | None = None,
        complete: bool = False,
    ) -> dict:
        return {
            "wakeAgent": wake_agent,
            "mode": mode,
            "worker_id": worker_id,
            "run_id": run_id,
            "project_root": str(project_root),
            "state_path": str(state),
            "item_id": item_id,
            "item_title": item_title,
            "item_status": item_status,
            "blocker": blocker,
            "complete": complete,
            "message": message,
        }

    # Determine primary blocker reason (priority order)
    if not state_ok:
        err_details = "; ".join(validation.errors[:2])
        blocker_msg = f"state invalid: {err_details}"
        payload = _build_payload(
            "blocker",
            wake_agent=False,
            blocker=blocker_msg,
            message="State invalid. Resolve before resuming worker.",
            complete=False,
        )
    elif lock_blocked:
        lock_run = "unknown"
        if lock_metadata_path.exists():
            try:
                meta = json.loads(lock_metadata_path.read_text(encoding="utf-8"))
                lock_run = meta.get("run_id", "unknown")
            except Exception:
                pass
        blocker_msg = f"lock held by {lock_run}"
        payload = _build_payload(
            "blocker",
            wake_agent=False,
            blocker=blocker_msg,
            message="Lock is held. Wait for lock holder or recover stale lock.",
            complete=False,
        )
    elif git_dirty:
        blocker_msg = f"uncommitted changes in project root: {git_reason}"
        payload = _build_payload(
            "blocker",
            wake_agent=False,
            blocker=blocker_msg,
            message="Uncommitted changes detected. Commit or stash before running.",
            complete=False,
        )
    elif status_payload.get("complete"):
        payload = _build_payload(
            "skip",
            wake_agent=False,
            blocker=None,
            message="All items terminal. No work available.",
            complete=True,
        )
    elif status_payload.get("active_item"):
        item = status_payload["active_item"]
        iid, ititle, istatus = _item_fields(item)
        payload = _build_payload(
            "wake",
            wake_agent=True,
            item_id=iid,
            item_title=ititle,
            item_status=istatus,
            complete=False,
            message=f"Continuing {iid} ({istatus})",
        )
    else:
        # No active item but work exists — claim one
        items = data.get("items", [])
        eligible = [
            item for item in items
            if isinstance(item, dict) and item.get("status") in ELIGIBLE_STATUSES
        ]
        if not eligible:
            # Race: item became terminal between status check and now
            payload = _build_payload(
                "skip",
                wake_agent=False,
                blocker=None,
                message="No eligible items. Worker may be complete.",
                complete=True,
            )
        else:
            # Claim the first eligible item
            chosen = min(
                eligible,
                key=lambda i: 0 if i.get("status") == "failed_retryable" else 1,
            )
            chosen["status"] = "in_progress"
            chosen["attempts"] = chosen.get("attempts", 0) + 1

            # Recompute counts
            counts = {s: 0 for s in VALID_STATUSES}
            for item in data.get("items", []):
                s = item.get("status")
                if s in counts:
                    counts[s] += 1
            data["counts"] = counts
            data["updated_at"] = datetime.now(UTC).isoformat()
            _write_json(state, data)

            iid, ititle, _ = _item_fields(chosen)
            payload = _build_payload(
                "wake",
                wake_agent=True,
                item_id=iid,
                item_title=ititle,
                item_status="in_progress",
                complete=False,
                message=f"Claimed {iid} for {run_id}",
            )

    if as_json:
        typer.echo(to_json(payload), nl=False)
    else:
        # Human-readable summary lines, then JSON on the last line
        item_line = (
            f"item: {payload['item_id']} ({payload['item_status']})"
            if payload["item_id"]
            else "item: none"
        )
        summary_lines = [
            f"worker: {worker_id}",
            f"run: {run_id}",
            f"mode: {payload['mode']}",
            f"wakeAgent: {payload['wakeAgent']}",
            item_line,
            f"complete: {payload['complete']}",
        ]
        if payload["blocker"]:
            summary_lines.append(f"blocker: {payload['blocker']}")
        for line in summary_lines:
            typer.echo(line)
        typer.echo(to_json(payload), nl=False)


@app.command()
def report(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    summary: Annotated[Path, typer.Option("--summary", exists=True, readable=True)],
) -> None:
    """Render a compact batch report from state and run summary JSON."""
    typer.echo(render_batch_report(_load_json(state), _load_json(summary)), nl=False)
