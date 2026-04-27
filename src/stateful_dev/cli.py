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
    lock_status,
    recover_stale_lock,
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
    fix_counts: Annotated[bool, typer.Option("--fix-counts")] = False,
    backup: Annotated[bool, typer.Option("--backup")] = False,
) -> None:
    """Validate a durable worker state file.

    With --fix-counts: recompute counts from items and repair mechanical count drift.
    Item statuses are never mutated. Use --backup to create a timestamped .bak file
    before applying the fix.
    """
    data = json.loads(state.read_text(encoding="utf-8"))

    if fix_counts:
        import shutil

        # Backup before touching anything when --backup is set
        if backup:
            label = "pre-fix-counts"
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            bak_path = state.with_name(f"{state.name}.bak.{label}.{ts}")
            shutil.copy2(state, bak_path)

        # Recompute counts from items — never mutate item statuses
        counts = {s: 0 for s in VALID_STATUSES}
        for item in data.get("items", []):
            s = item.get("status")
            if s in counts:
                counts[s] += 1
        data["counts"] = counts
        data["updated_at"] = datetime.now(UTC).isoformat()

        # Write fixed state back atomically
        _write_json(state, data)

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
def backup(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    label: Annotated[str, typer.Option("--label")],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Create a timestamped backup copy of a state file.

    The backup is written next to the original as <state>.bak.<label>.<timestamp>.
    The original is never modified.
    """
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    bak_path = state.with_name(f"{state.name}.bak.{label}.{ts}")
    import shutil

    shutil.copy2(state, bak_path)
    payload = {
        "backup_path": str(bak_path),
        "backup_at": datetime.now(UTC).isoformat(),
        "original_path": str(state),
        "label": label,
    }
    if as_json:
        typer.echo(to_json(payload), nl=False)
    else:
        typer.echo(f"backed up {state} -> {bak_path}")


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


_APP_LOCK_TIMEOUT = 60


def _claim_one_item(
    data: dict[str, Any],
    state: Path,
    run_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Atomically claim one eligible item or return an existing active item.

    Shared primitive used by both `claim` CLI and `cron_gate`.
    Acquires the state lock, validates HITL preconditions, selects or resumes
    an item, records active_run_id and claimed_at, recomputes counts, and
    writes the updated state.

    Args:
        data: already-loaded and validated state dict
        state: path to the state file (for lock acquisition)
        run_id: run identifier for this invocation

    Returns:
        (chosen_item, updated_data) where chosen_item is the claimed dict
        (with id/title/status/attempts populated), or (None, updated_data)
        if no active or eligible item exists.
    """
    from stateful_dev.hitl_poseidon import hitl_enabled, hitl_poll_ok_for_run
    from stateful_dev.locking import acquire_lock, release_lock
    from stateful_dev.state import validate_state
    from stateful_dev.status import ACTIVE_STATUSES, ELIGIBLE_STATUSES

    data["state_path"] = str(state)
    validation = validate_state(data)
    if not validation.ok:
        raise ValueError("invalid state: " + "; ".join(validation.errors))

    # HITL enforcement: fail closed when HITL is required but no successful poll
    if hitl_enabled(data):
        hitl_ok, hitl_reason = hitl_poll_ok_for_run(data, run_id)
        if not hitl_ok:
            raise ValueError("hitl poll required: " + hitl_reason)

    lock = None
    try:
        lock = acquire_lock(
            state.parent, _lock_run_id("claim"), timeout_minutes=_APP_LOCK_TIMEOUT
        )

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
            return (
                {
                    "id": active.get("id"),
                    "title": active.get("title"),
                    "status": active.get("status"),
                    "attempts": active.get("attempts", 0),
                },
                data,
            )

        eligible_candidates = [
            item for item in items
            if isinstance(item, dict) and item.get("status") in ELIGIBLE_STATUSES
        ]
        if not eligible_candidates:
            return (None, data)

        def _priority(item: dict) -> int:
            return 0 if item.get("status") == "failed_retryable" else 1

        chosen = min(eligible_candidates, key=_priority)
        chosen["status"] = "in_progress"
        chosen["attempts"] = chosen.get("attempts", 0) + 1
        chosen["active_run_id"] = run_id
        chosen["claimed_at"] = datetime.now(UTC).isoformat()

        # Recompute counts
        counts = {s: 0 for s in VALID_STATUSES}
        for item in data.get("items", []):
            s = item.get("status")
            if s in counts:
                counts[s] += 1
        data["counts"] = counts
        data["updated_at"] = datetime.now(UTC).isoformat()

        _write_json(state, data)

        return (
            {
                "id": chosen.get("id"),
                "title": chosen.get("title"),
                "status": chosen.get("status"),
                "attempts": chosen.get("attempts", 0),
            },
            data,
        )

    finally:
        if lock is not None:
            release_lock(lock)


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
    When HITL is enabled and poll_policy=required, refuses to claim new work
    unless the current run has a successful HITL poll marker.
    Emits compact JSON with claimed flag, item, and run_id.
    """
    try:
        data = _load_json(state)
        item, _ = _claim_one_item(data, state, run_id)
        if item is None:
            payload = {"claimed": False, "item": None, "run_id": run_id}
        else:
            payload = {"claimed": True, "item": item, "run_id": run_id}
        typer.echo(to_json(payload), nl=False)
    except (FreshLockError, LockError) as error:
        _exit_lock_error(error)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc


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

    from stateful_dev.locking import (
        LOCK_DIR_NAME,
        LOCK_METADATA_NAME,
        FreshLockError,
        LockError,
        _read_metadata,
    )
    from stateful_dev.state import validate_state
    from stateful_dev.status import build_status

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
        # No active item but work exists — claim one via the shared primitive
        try:
            claimed_item, data = _claim_one_item(data, state, run_id)
        except (FreshLockError, LockError) as error:
            _exit_lock_error(error)
        except ValueError as exc:
            typer.echo(str(exc))
            raise typer.Exit(1) from exc

        if claimed_item is None:
            payload = _build_payload(
                "skip",
                wake_agent=False,
                blocker=None,
                message="No eligible items. Worker may be complete.",
                complete=True,
            )
        else:
            iid = claimed_item.get("id")
            ititle = claimed_item.get("title")
            payload = _build_payload(
                "wake",
                wake_agent=True,
                item_id=iid,
                item_title=ititle,
                item_status="in_progress",
                complete=False,
                message=f"Claimed {iid} for {run_id}",
            )

    # Non-zero exit for blocker/error triggers Hermes notification
    if payload.get("mode") in ("blocker", "error"):
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
        raise typer.Exit(1)

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


hitl_app = typer.Typer(help="Poseidon HITL polling commands.")


@hitl_app.command("poll-before-run")
def hitl_poll_before_run(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    run_id: Annotated[str, typer.Option("--run-id")],
    base_url: Annotated[str, typer.Option("--base-url")],
    node_token_file: Annotated[
        Path, typer.Option("--node-token-file", exists=True, readable=True)
    ],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Poll Poseidon for active HITL events and stage them locally.

    Reads the node token from the specified file.
    Validates events against HITL state metadata (worker_id, state_path_hash).
    Stages valid events under .agent-state/<worker>/hitl-inbox/<request_id>/.
    Writes a run marker recording the poll result.
    Fails closed when HITL poll_policy=required and the poll fails.
    """

    from stateful_dev.hitl_poseidon import (
        compute_state_path_hash,
        hitl_enabled,
        poll_poseidon,
        stage_event,
    )
    from stateful_dev.locking import (
        FreshLockError,
        LockError,
        acquire_lock,
        release_lock,
    )

    # Load state
    data = _load_json(state)
    data["state_path"] = str(state)
    validation = validate_state(data)
    if not validation.ok:
        for err in validation.errors:
            typer.echo(f"state error: {err}")
        raise typer.Exit(1)

    if not hitl_enabled(data):
        typer.echo("HITL is not enabled for this worker")
        raise typer.Exit(0)

    hitl = data["hitl"]
    node_id = hitl.get("node_id", "")
    worker_id = hitl.get("worker_id", "")
    state_path_hash = hitl.get("state_path_hash") or compute_state_path_hash(str(state))
    active_requests = hitl.get("active_requests", [])
    active_request_ids = [
        r.get("request_id") for r in active_requests
        if isinstance(r, dict) and r.get("request_id")
    ]

    # Read node token
    try:
        node_token = node_token_file.read_text(encoding="utf-8").strip()
    except OSError as e:
        typer.echo(f"failed to read node token file: {e}")
        raise typer.Exit(1) from None

    # Acquire lock for the polling operation
    lock = None
    try:
        lock = acquire_lock(
            state.parent, _lock_run_id("hitl-poll"), timeout_minutes=5
        )

        result = poll_poseidon(
            base_url=base_url,
            node_token=node_token,
            node_id=node_id,
            worker_id=worker_id,
            state_path_hash=state_path_hash,
            active_request_ids=active_request_ids,
        )

        # Stage valid events locally
        inbox_dir = state.parent / "hitl-inbox"
        staged_count = 0
        for event in result.events:
            try:
                stage_event(event, inbox_dir)
                staged_count += 1
            except OSError as e:
                typer.echo(f"warning: failed to stage event {event.event_id}: {e}")

        # Write run marker
        runs_dir = state.parent / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        run_marker = runs_dir / f"{run_id}.json"
        marker = {
            "run_id": run_id,
            "hitl_poll": {
                "required": True,
                "ok": result.ok,
                "completed_at": datetime.now(UTC).isoformat(),
                "worker_id": worker_id,
                "request_ids": result.request_ids_found,
                "event_count": len(result.events),
                "staged_event_count": staged_count,
                "error": result.error,
            },
        }
        _write_json(run_marker, marker)

        if as_json:
            typer.echo(to_json({
                "ok": result.ok,
                "events_staged": staged_count,
                "run_id": run_id,
                "error": result.error,
            }), nl=False)
        else:
            if result.ok:
                typer.echo(f"HITL poll ok: {staged_count} event(s) staged")
            else:
                typer.echo(f"HITL poll failed: {result.error}")

    except (FreshLockError, LockError) as error:
        _exit_lock_error(error)
    finally:
        if lock is not None:
            release_lock(lock)


app.add_typer(hitl_app, name="hitl")


# ---------------------------------------------------------------------------
# lock subcommands: status and recover
# ---------------------------------------------------------------------------

lock_app = typer.Typer(help="Lock status and stale-lock recovery commands.")


@lock_app.command("status")
def lock_status_cmd(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show the current lock state for a worker state file.

    Reports whether the lock is held or clear, the run_id and acquired_at
    timestamp if held, and whether the lock is classified as stale (>60 min old).
    """
    status = lock_status(state)
    if as_json:
        typer.echo(to_json(status), nl=False)
    else:
        if status["held"]:
            stale_str = " (STALE)" if status["is_stale"] else ""
            typer.echo(
                f"lock: held by {status['run_id'] or 'unknown'} "
                f"since {status['acquired_at'] or 'unknown'}{stale_str}"
            )
        else:
            typer.echo("lock: clear")


@lock_app.command("recover")
def lock_recover_cmd(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    confirm: Annotated[bool, typer.Option("--confirm")] = False,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Remove a stale lock after operator confirmation.

    Performs backup-before-write: the lock dir is renamed to lock.bak before
    removal so it can be restored if needed.

    Refuses to recover a fresh (non-stale) lock.
    Exits non-zero if --confirm is not provided or if the lock is fresh.
    """
    if not confirm:
        typer.echo("aborted: --confirm flag is required to remove a stale lock")
        raise typer.Exit(1)

    try:
        recovered_run_id = recover_stale_lock(state)
        payload = {"ok": True, "recovered_run_id": recovered_run_id}
        if as_json:
            typer.echo(to_json(payload), nl=False)
        else:
            typer.echo(f"recovered stale lock: {recovered_run_id}")
    except LockError as exc:
        payload = {"ok": False, "error": str(exc)}
        if as_json:
            typer.echo(to_json(payload), nl=False)
        else:
            typer.echo(f"lock recover failed: {exc}", err=True)
        raise typer.Exit(1) from exc


app.add_typer(lock_app, name="lock")
