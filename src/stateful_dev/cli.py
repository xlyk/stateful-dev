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
def report(
    state: Annotated[Path, typer.Option("--state", exists=True, readable=True)],
    summary: Annotated[Path, typer.Option("--summary", exists=True, readable=True)],
) -> None:
    """Render a compact batch report from state and run summary JSON."""
    typer.echo(render_batch_report(_load_json(state), _load_json(summary)), nl=False)
