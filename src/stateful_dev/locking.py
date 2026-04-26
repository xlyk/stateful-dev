from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
