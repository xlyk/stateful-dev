import json
from pathlib import Path
from typing import Any

from stateful_dev.reports import render_batch_report, render_operator_handoff
from stateful_dev.state import validate_state
from stateful_dev.status import build_status

# Schema definitions: field name -> type string for Hermes plugin system
DOCTOR_SCHEMA = {"state": "path"}
REPORT_SCHEMA = {"state": "path", "run_summary": "object"}
STATUS_SCHEMA = {"state": "path"}
TRANSITION_SCHEMA = {
    "state": "path",
    "item_id": "string",
    "status": "string",
    "evidence_json": "string",
}
RECORD_RED_SCHEMA = {
    "state": "path",
    "item_id": "string",
    "command": "string",
    "result": "string",
}
RECORD_GREEN_SCHEMA = {
    "state": "path",
    "item_id": "string",
    "command": "string",
    "result": "string",
}
RECORD_FULL_SUITE_SCHEMA = {
    "state": "path",
    "item_id": "string",
    "command": "string",
    "result": "string",
}
RECORD_LINT_SCHEMA = {
    "state": "path",
    "item_id": "string",
    "command": "string",
    "result": "string",
}
CLAIM_SCHEMA = {"state": "path", "run_id": "string"}
LOCK_STATUS_SCHEMA = {"state": "path"}
LOCK_RECOVER_SCHEMA = {"state": "path", "force": "boolean"}
HANDOFF_SCHEMA = {
    "job_name": "string",
    "question": "string",
    "why": "string",
    "recommended_answer": "string",
    "allowed_next_action": "string",
    "project_root": "string",
    "plan_path": "string",
    "state_path": "string",
    "item_id": "string",
    "title": "string",
    "status": "string",
    "evidence": "array",
}
COMPLETE_SCHEMA = {"state": "path"}


def _read_state(state_path: Path) -> dict[str, Any]:
    return json.loads(state_path.read_text(encoding="utf-8"))


def _write_state(state_path: Path, data: dict[str, Any]) -> None:
    import os
    import tempfile

    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=state_path.parent, suffix=".tmp"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp_path, state_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Core tools
# ---------------------------------------------------------------------------


def stateful_dev_doctor(payload: dict[str, str]) -> dict[str, object]:
    """Validate a durable worker state file."""
    state_path = Path(payload["state"])
    result = validate_state(_read_state(state_path))
    return {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
        "counts": result.counts,
    }


def stateful_dev_report(payload: dict[str, Any]) -> dict[str, str]:
    """Render a compact stateful development batch report."""
    state_path = Path(payload["state"])
    run_summary = payload.get("run_summary", {})
    if not isinstance(run_summary, dict):
        run_summary = {}
    return {"text": render_batch_report(_read_state(state_path), run_summary)}


# ---------------------------------------------------------------------------
# Status tool
# ---------------------------------------------------------------------------


def stateful_dev_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize worker lifecycle status for operators and cron workers."""
    from stateful_dev.status import render_status

    state_path = Path(payload["state"])
    status_payload = build_status(state_path, _read_state(state_path))
    return {
        "ok": status_payload["ok"],
        "rendered": render_status(status_payload),
        "counts": status_payload["counts"],
    }


# ---------------------------------------------------------------------------
# Transition tool
# ---------------------------------------------------------------------------


def stateful_dev_transition(payload: dict[str, Any]) -> dict[str, Any]:
    """Move one item through a legal status transition.

    Requires item_id, status, and optionally evidence_json.
    Validates legal transition chain before applying.
    """
    from datetime import UTC, datetime

    from stateful_dev.locking import (
        FreshLockError,
        LockError,
        acquire_lock,
        release_lock,
        write_json_atomic,
    )
    from stateful_dev.transitions import IllegalTransitionError, transition_item

    state_path = Path(payload["state"])
    item_id = payload["item_id"]
    target_status = payload["status"]
    evidence_json = payload.get("evidence_json")
    evidence = json.loads(evidence_json) if evidence_json else None

    lock_id = (
        f"stateful-dev-transition-"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    )
    lock = None
    try:
        lock = acquire_lock(state_path.parent, lock_id, timeout_minutes=60)
        data = _read_state(state_path)
        updated = transition_item(data, item_id, target_status, evidence)
        updated["updated_at"] = datetime.now(UTC).isoformat()
        write_json_atomic(state_path, updated)
        return {"ok": True, "item_id": item_id, "status": target_status}
    except IllegalTransitionError as exc:
        return {"ok": False, "error": str(exc)}
    except (FreshLockError, LockError) as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if lock is not None:
            release_lock(lock)


# ---------------------------------------------------------------------------
# Record evidence tools
# ---------------------------------------------------------------------------


def _record_evidence(
    state_path: Path,
    item_id: str,
    command: str,
    result: str,
    gate: str,
) -> dict[str, Any]:
    """Append evidence to an item. Returns result dict."""
    from datetime import UTC, datetime

    from stateful_dev.locking import (
        FreshLockError,
        LockError,
        acquire_lock,
        release_lock,
        write_json_atomic,
    )
    from stateful_dev.transitions import _has_red_evidence

    evidence = {f"focused_{gate}_command": command, f"focused_{gate}_result": result}
    lock_id = f"stateful-dev-record-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    lock = None
    try:
        lock = acquire_lock(state_path.parent, lock_id, timeout_minutes=60)
        data = _read_state(state_path)
        item = None
        for it in data.get("items", []):
            if it.get("id") == item_id:
                item = it
                break
        if item is None:
            return {"ok": False, "error": f"item not found: {item_id}"}

        if "green" in gate or "full_suite" in gate:
            if not _has_red_evidence(item):
                return {
                    "ok": False,
                    "error": (
                        "RED evidence must be recorded before "
                        "GREEN or full-suite evidence"
                    ),
                }

        item.setdefault("evidence", []).append(evidence)
        data["updated_at"] = datetime.now(UTC).isoformat()
        write_json_atomic(state_path, data)
        return {
            "ok": True,
            "item_id": item_id,
            "gate": gate,
            "total_evidence_entries": len(item.get("evidence", [])),
        }
    except (FreshLockError, LockError) as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        if lock is not None:
            release_lock(lock)


def stateful_dev_record_red(payload: dict[str, Any]) -> dict[str, Any]:
    """Record focused RED test evidence for an item."""
    state_path = Path(payload["state"])
    return _record_evidence(
        state_path,
        payload["item_id"],
        payload["command"],
        payload["result"],
        "red",
    )


def stateful_dev_record_green(payload: dict[str, Any]) -> dict[str, Any]:
    """Record focused GREEN test evidence for an item."""
    state_path = Path(payload["state"])
    return _record_evidence(
        state_path,
        payload["item_id"],
        payload["command"],
        payload["result"],
        "green",
    )


def stateful_dev_record_full_suite(payload: dict[str, Any]) -> dict[str, Any]:
    """Record full test suite evidence for an item."""
    state_path = Path(payload["state"])
    return _record_evidence(
        state_path,
        payload["item_id"],
        payload["command"],
        payload["result"],
        "full_suite",
    )


def stateful_dev_record_lint(payload: dict[str, Any]) -> dict[str, Any]:
    """Record lint check evidence for an item."""
    state_path = Path(payload["state"])
    return _record_evidence(
        state_path,
        payload["item_id"],
        payload["command"],
        payload["result"],
        "lint",
    )


# ---------------------------------------------------------------------------
# Claim tool
# ---------------------------------------------------------------------------


def stateful_dev_claim(payload: dict[str, Any]) -> dict[str, Any]:
    """Atomically claim one eligible item or return an existing active item."""
    from datetime import UTC, datetime

    from stateful_dev.locking import (
        FreshLockError,
        LockError,
        acquire_lock,
        release_lock,
        write_json_atomic,
    )
    from stateful_dev.state import validate_state
    from stateful_dev.status import ACTIVE_STATUSES, ELIGIBLE_STATUSES

    state_path = Path(payload["state"])
    run_id = payload["run_id"]

    lock_id = f"stateful-dev-claim-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    lock = None
    try:
        lock = acquire_lock(state_path.parent, lock_id, timeout_minutes=60)
        data = _read_state(state_path)
        result = validate_state(data)
        if not result.ok:
            return {"ok": False, "error": "invalid state", "claimed": False}

        # Find active item first
        for item in data.get("items", []):
            if item.get("status") in ACTIVE_STATUSES:
                item["active_run_id"] = run_id
                item["claimed_at"] = datetime.now(UTC).isoformat()
                data["updated_at"] = datetime.now(UTC).isoformat()
                write_json_atomic(state_path, data)
                return {
                    "ok": True,
                    "claimed": True,
                    "item": {
                        "id": item["id"],
                        "title": item.get("title"),
                        "status": item["status"],
                        "attempts": item.get("attempts", 0),
                    },
                    "run_id": run_id,
                }

        # Claim first eligible item
        for item in data.get("items", []):
            if item.get("status") in ELIGIBLE_STATUSES:
                item["status"] = "in_progress"
                item["attempts"] = item.get("attempts", 0) + 1
                item["active_run_id"] = run_id
                item["claimed_at"] = datetime.now(UTC).isoformat()
                data["updated_at"] = datetime.now(UTC).isoformat()
                write_json_atomic(state_path, data)
                return {
                    "ok": True,
                    "claimed": True,
                    "item": {
                        "id": item["id"],
                        "title": item.get("title"),
                        "status": "in_progress",
                        "attempts": item["attempts"],
                    },
                    "run_id": run_id,
                }

        return {"ok": True, "claimed": False, "item": None, "run_id": run_id}
    except (FreshLockError, LockError) as exc:
        return {"ok": False, "error": str(exc), "claimed": False}
    finally:
        if lock is not None:
            release_lock(lock)


# ---------------------------------------------------------------------------
# Lock tools
# ---------------------------------------------------------------------------


def stateful_dev_lock_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Report lock status for a worker state directory."""
    from datetime import UTC, datetime, timedelta

    from stateful_dev.locking import (
        LOCK_DIR_NAME,
        _read_metadata,
    )

    state_path = Path(payload["state"])
    lock_dir = state_path.parent / LOCK_DIR_NAME

    if not lock_dir.exists():
        return {"locked": False, "stale": False, "acquired_at": None}

    meta = _read_metadata(lock_dir)
    acquired_at = meta.get("acquired_at")
    stale = False
    if isinstance(acquired_at, str):
        try:
            acquired = datetime.fromisoformat(acquired_at)
            if acquired.tzinfo is None:
                acquired = acquired.replace(tzinfo=UTC)
            stale = (datetime.now(UTC) - acquired) >= timedelta(minutes=60)
        except ValueError:
            stale = True
    else:
        stale = True

    return {"locked": True, "stale": stale, "acquired_at": acquired_at}


def stateful_dev_lock_recover(payload: dict[str, Any]) -> dict[str, Any]:
    """Recover a stale lock or report an error on a fresh lock."""
    from datetime import UTC, datetime, timedelta

    from stateful_dev.locking import (
        LOCK_DIR_NAME,
        FreshLockError,
        LockError,
        _read_metadata,
        recover_stale_lock,
    )

    state_path = Path(payload["state"])
    force = payload.get("force", False)
    lock_dir = state_path.parent / LOCK_DIR_NAME

    if not lock_dir.exists():
        return {"ok": True, "recovered": False, "message": "no lock present"}

    meta = _read_metadata(lock_dir)
    acquired_at = meta.get("acquired_at")
    is_stale = False
    if isinstance(acquired_at, str):
        try:
            acquired = datetime.fromisoformat(acquired_at)
            if acquired.tzinfo is None:
                acquired = acquired.replace(tzinfo=UTC)
            is_stale = (datetime.now(UTC) - acquired) >= timedelta(minutes=60)
        except ValueError:
            is_stale = True
    else:
        is_stale = True

    if not is_stale and not force:
        return {
            "ok": False,
            "error": (
                "lock is not stale — refusing to recover. "
                "Use force=true to override."
            ),
        }

    try:
        recover_stale_lock(lock_dir)
        return {"ok": True, "recovered": True, "message": "stale lock recovered"}
    except (FreshLockError, LockError) as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Handoff tool
# ---------------------------------------------------------------------------


def stateful_dev_handoff(payload: dict[str, Any]) -> dict[str, str]:
    """Render an operator handoff document for a blocked item.

    Accepts individual fields rather than a state path — matches the CLI interface.
    """
    rendered = render_operator_handoff(
        job_name=payload["job_name"],
        question=payload["question"],
        why=payload["why"],
        recommended_answer=payload["recommended_answer"],
        project_root=payload["project_root"],
        plan_path=payload["plan_path"],
        state_path=payload["state_path"],
        item_id=payload["item_id"],
        title=payload["title"],
        status=payload["status"],
        evidence=payload.get("evidence") or [],
        allowed_next_action=payload["allowed_next_action"],
    )
    return {"ok": True, "text": rendered}


# ---------------------------------------------------------------------------
# Complete/audit tool
# ---------------------------------------------------------------------------


def stateful_dev_complete(payload: dict[str, Any]) -> dict[str, Any]:
    """Audit a worker for safe shutdown decisions."""
    from datetime import UTC, datetime, timedelta

    from stateful_dev.locking import LOCK_DIR_NAME, _read_metadata

    state_path = Path(payload["state"])
    data = _read_state(state_path)
    validation = validate_state(data)
    doctor_ok = validation.ok

    lock_dir = state_path.parent / LOCK_DIR_NAME
    lock_held = lock_dir.exists()
    lock_stale = False
    if lock_held:
        meta = _read_metadata(lock_dir)
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
    lock_clear = not lock_held or lock_stale

    counts = validation.counts
    active_count = (
        counts.get("in_progress", 0)
        + counts.get("red_verified", 0)
        + counts.get("green_verified", 0)
    )
    retryable_count = counts.get("failed_retryable", 0)
    active_or_retryable_count = active_count + retryable_count

    shutdown_approved = doctor_ok and lock_clear and active_or_retryable_count == 0

    if not doctor_ok:
        next_action = "repair invalid state before considering shutdown"
    elif not lock_clear:
        next_action = "recover stale lock or wait for lock holder"
    elif active_count > 0:
        next_action = "resume or complete active item before shutdown"
    elif retryable_count > 0:
        next_action = "review failed_retryable items — retry or mark failed_final"
    else:
        next_action = "pause worker or remove from cron schedule"

    return {
        "shutdown_approved": shutdown_approved,
        "doctor_ok": doctor_ok,
        "lock_clear": lock_clear,
        "active_count": active_count,
        "failed_retryable_count": retryable_count,
        "active_or_retryable_count": active_or_retryable_count,
        "counts": counts,
        "next_action": next_action,
    }


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    ctx.tool(
        "stateful_dev_doctor",
        stateful_dev_doctor,
        schema=DOCTOR_SCHEMA,
        description="Validate a durable worker state file.",
    )
    ctx.tool(
        "stateful_dev_report",
        stateful_dev_report,
        schema=REPORT_SCHEMA,
        description="Render a compact stateful development batch report.",
    )
    ctx.tool(
        "stateful_dev_status",
        stateful_dev_status,
        schema=STATUS_SCHEMA,
        description="Summarize worker lifecycle status for operators and cron workers.",
    )
    ctx.tool(
        "stateful_dev_transition",
        stateful_dev_transition,
        schema=TRANSITION_SCHEMA,
        description="Move one item through a legal status transition.",
    )
    ctx.tool(
        "stateful_dev_record_red",
        stateful_dev_record_red,
        schema=RECORD_RED_SCHEMA,
        description="Record focused RED test evidence for an item.",
    )
    ctx.tool(
        "stateful_dev_record_green",
        stateful_dev_record_green,
        schema=RECORD_GREEN_SCHEMA,
        description="Record focused GREEN test evidence for an item.",
    )
    ctx.tool(
        "stateful_dev_record_full_suite",
        stateful_dev_record_full_suite,
        schema=RECORD_FULL_SUITE_SCHEMA,
        description="Record full test suite evidence for an item.",
    )
    ctx.tool(
        "stateful_dev_record_lint",
        stateful_dev_record_lint,
        schema=RECORD_LINT_SCHEMA,
        description="Record lint check evidence for an item.",
    )
    ctx.tool(
        "stateful_dev_claim",
        stateful_dev_claim,
        schema=CLAIM_SCHEMA,
        description=(
            "Atomically claim one eligible item "
            "or return an existing active item."
        ),
    )
    ctx.tool(
        "stateful_dev_lock_status",
        stateful_dev_lock_status,
        schema=LOCK_STATUS_SCHEMA,
        description="Report lock status for a worker state directory.",
    )
    ctx.tool(
        "stateful_dev_lock_recover",
        stateful_dev_lock_recover,
        schema=LOCK_RECOVER_SCHEMA,
        description="Recover a stale lock or report an error on a fresh lock.",
    )
    ctx.tool(
        "stateful_dev_handoff",
        stateful_dev_handoff,
        schema=HANDOFF_SCHEMA,
        description="Render an operator handoff document for a blocked item.",
    )
    ctx.tool(
        "stateful_dev_complete",
        stateful_dev_complete,
        schema=COMPLETE_SCHEMA,
        description="Audit a worker for safe shutdown decisions.",
    )
