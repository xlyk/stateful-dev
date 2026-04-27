from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

LOCK_DIR_NAME = "lock"
LOCK_METADATA_NAME = "metadata.json"


class LockError(RuntimeError):
    pass


class FreshLockError(LockError):
    pass


@dataclass(frozen=True)
class StateLock:
    path: Path
    run_id: str


def _now() -> datetime:
    return datetime.now(UTC)


def _metadata_path(lock_path: Path) -> Path:
    return lock_path / LOCK_METADATA_NAME


def _read_metadata(lock_path: Path) -> dict[str, object]:
    try:
        payload = json.loads(_metadata_path(lock_path).read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_stale(metadata: dict[str, object], timeout_minutes: int) -> bool:
    acquired_at = metadata.get("acquired_at")
    if not isinstance(acquired_at, str):
        return True
    try:
        acquired = datetime.fromisoformat(acquired_at)
    except ValueError:
        return True
    if acquired.tzinfo is None:
        acquired = acquired.replace(tzinfo=UTC)
    return _now() - acquired >= timedelta(minutes=timeout_minutes)


def _write_metadata(lock_path: Path, run_id: str) -> None:
    metadata = {
        "run_id": run_id,
        "acquired_at": _now().isoformat(),
    }
    _metadata_path(lock_path).write_text(json.dumps(metadata, indent=2) + "\n")


def write_json_atomic(path: Path | str, data: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_name(f"{target.name}.tmp")
    temp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(target)


def acquire_lock(state_dir: Path | str, run_id: str, timeout_minutes: int) -> StateLock:
    state_path = Path(state_dir)
    state_path.mkdir(parents=True, exist_ok=True)
    lock_path = state_path / LOCK_DIR_NAME

    try:
        lock_path.mkdir()
    except FileExistsError as exc:
        metadata = _read_metadata(lock_path)
        if not _is_stale(metadata, timeout_minutes):
            existing_run_id = metadata.get("run_id", "unknown")
            raise FreshLockError(f"fresh lock is held by {existing_run_id}") from exc
        shutil.rmtree(lock_path)
        lock_path.mkdir()

    _write_metadata(lock_path, run_id)
    return StateLock(path=lock_path, run_id=run_id)


def release_lock(lock: StateLock) -> None:
    metadata = _read_metadata(lock.path)
    if metadata.get("run_id") != lock.run_id:
        raise LockError("cannot release lock owned by another run")
    shutil.rmtree(lock.path)


# ---------------------------------------------------------------------------
# stale lock detection used by both locking.py and status.py / cli.py
# ---------------------------------------------------------------------------

STALE_LOCK_TIMEOUT_MINUTES = 60


def lock_status(state_path: Path) -> dict[str, Any]:
    """Return the current lock status for a state file.

    Returns a dict with keys:
        held (bool): True if a lock directory exists
        run_id (str | None): run_id from lock metadata, or None
        acquired_at (str | None): ISO timestamp from lock metadata, or None
        is_stale (bool): True if lock is held but stale (> 60 min old)
    """
    lock_path = state_path.parent / LOCK_DIR_NAME
    if not lock_path.exists():
        return {"held": False, "run_id": None, "acquired_at": None, "is_stale": False}
    metadata = _read_metadata(lock_path)
    acquired_at: str | None = (
        metadata.get("acquired_at") if isinstance(metadata, dict) else None
    )
    is_stale = (
        _is_stale(metadata, STALE_LOCK_TIMEOUT_MINUTES)
        if lock_path.exists()
        else False
    )
    return {
        "held": lock_path.exists(),
        "run_id": metadata.get("run_id") if isinstance(metadata, dict) else None,
        "acquired_at": acquired_at,
        "is_stale": is_stale,
    }


def recover_stale_lock(state_path: Path) -> str:
    """Remove a stale lock directory after confirming it is stale.

    Performs backup-before-write by renaming the lock dir to a .bak path
    with a timestamp before removal, so recovery is possible.

    Returns the run_id of the recovered lock.

    Raises LockError if the lock is fresh (not stale).
    Raises LockError if no lock exists.
    """
    lock_path = state_path.parent / LOCK_DIR_NAME
    if not lock_path.exists():
        raise LockError("no lock to recover")

    metadata = _read_metadata(lock_path)
    if not _is_stale(metadata, STALE_LOCK_TIMEOUT_MINUTES):
        raise LockError("refusing to recover a fresh lock")

    run_id = (
        metadata.get("run_id", "unknown") if isinstance(metadata, dict) else "unknown"
    )

    # Backup before removal
    backup_path = lock_path.parent / f"{LOCK_DIR_NAME}.bak"
    if backup_path.exists():
        shutil.rmtree(backup_path)
    shutil.move(str(lock_path), str(backup_path))

    return run_id
