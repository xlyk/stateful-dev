from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from stateful_dev.locking import LOCK_DIR_NAME, LOCK_METADATA_NAME
from stateful_dev.state import validate_state

ACTIVE_STATUSES = {"in_progress", "red_verified", "green_verified"}
ELIGIBLE_STATUSES = {"failed_retryable", "pending"}


def _item_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "status": item.get("status"),
    }


def _first_item_with_status(
    items: list[Any], statuses: set[str]
) -> dict[str, Any] | None:
    for item in items:
        if isinstance(item, dict) and item.get("status") in statuses:
            return _item_summary(item)
    return None


def _read_lock(state_path: Path) -> dict[str, Any]:
    metadata_path = state_path.parent / LOCK_DIR_NAME / LOCK_METADATA_NAME
    if not metadata_path.exists():
        return {"held": False, "run_id": None, "acquired_at": None}
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "held": True,
        "run_id": metadata.get("run_id"),
        "acquired_at": metadata.get("acquired_at"),
    }


def _read_last_run_summary(state_path: Path) -> dict[str, Any] | None:
    runs_dir = state_path.parent / "runs"
    if not runs_dir.exists():
        return None
    run_files = sorted(path for path in runs_dir.glob("*.json") if path.is_file())
    if not run_files:
        return None
    latest = run_files[-1]
    try:
        summary = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        summary = None
    return {"path": str(latest), "summary": summary}


def _is_complete(counts: dict[str, int]) -> bool:
    active_or_available = (
        counts.get("pending", 0)
        + counts.get("failed_retryable", 0)
        + counts.get("in_progress", 0)
        + counts.get("red_verified", 0)
        + counts.get("green_verified", 0)
    )
    return active_or_available == 0


def _suggest_next_action(
    *, active_item: dict[str, Any] | None,
    next_eligible_item: dict[str, Any] | None,
    complete: bool,
    lock: dict[str, Any],
    ok: bool,
) -> str:
    if not ok:
        return "repair invalid state"
    if lock["held"]:
        run_id = lock.get("run_id") or "unknown"
        if active_item:
            return f"continue active item {active_item['id']}"
        return f"inspect lock held by {run_id}"
    if active_item:
        return f"continue active item {active_item['id']}"
    if next_eligible_item:
        return f"claim next eligible item {next_eligible_item['id']}"
    if complete:
        return "audit completion and pause worker"
    return "review terminal blockers"


def build_status(state_path: Path, data: dict[str, Any]) -> dict[str, Any]:
    validation = validate_state(data)
    items = data.get("items", [])
    if not isinstance(items, list):
        items = []
    active_item = _first_item_with_status(items, ACTIVE_STATUSES)
    next_eligible_item = _first_item_with_status(items, ELIGIBLE_STATUSES)
    lock = _read_lock(state_path)
    complete = validation.ok and _is_complete(validation.counts)
    return {
        "ok": validation.ok,
        "errors": validation.errors,
        "warnings": validation.warnings,
        "job_name": data.get("job_name"),
        "state_path": str(state_path),
        "counts": validation.counts,
        "active_item": active_item,
        "next_eligible_item": next_eligible_item,
        "lock": lock,
        "complete": complete,
        "last_run_summary": _read_last_run_summary(state_path),
        "suggested_next_action": _suggest_next_action(
            active_item=active_item,
            next_eligible_item=next_eligible_item,
            complete=complete,
            lock=lock,
            ok=validation.ok,
        ),
    }


def _format_item(prefix: str, item: dict[str, Any] | None) -> str:
    if item is None:
        return f"{prefix}: none"
    return f"{prefix}: {item['id']} — {item.get('title')} ({item.get('status')})"


def render_status(status: dict[str, Any]) -> str:
    counts = status["counts"]
    lock = status["lock"]
    lock_line = "lock: clear"
    if lock["held"]:
        lock_line = f"lock: held by {lock.get('run_id') or 'unknown'}"
    lines = [
        f"job: {status.get('job_name')}",
        f"state: {status['state_path']}",
        "counts: "
        + ", ".join(f"{name}: {counts.get(name, 0)}" for name in sorted(counts)),
        _format_item("active", status["active_item"]),
        _format_item("next", status["next_eligible_item"]),
        lock_line,
        f"complete: {'yes' if status['complete'] else 'no'}",
        f"next action: {status['suggested_next_action']}",
    ]
    if status["errors"]:
        lines.append("errors: " + "; ".join(status["errors"]))
    return "\n".join(lines) + "\n"
