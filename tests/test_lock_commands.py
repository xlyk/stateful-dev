"""Tests for `stateful-dev lock` subcommands: status and recover."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.locking import LOCK_DIR_NAME, LOCK_METADATA_NAME

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def write_lock_metadata(lock_path: Path, run_id: str, acquired_at: str) -> None:
    meta = {"run_id": run_id, "acquired_at": acquired_at}
    (lock_path / LOCK_METADATA_NAME).write_text(json.dumps(meta) + "\n")


# ---------------------------------------------------------------------------
# lock status
# ---------------------------------------------------------------------------

class TestLockStatus:
    """`stateful-dev lock status --state <path>`"""

    def test_command_does_not_exist(self, tmp_path):
        """RED: lock status command does not exist yet."""
        result = invoke_lock(
            ["lock", "status", "--state", str(tmp_path / "nonexistent.json")],
        )
        # Typer exits 2 for "no such command"
        assert result.exit_code == 2

    def test_lock_clear_returns_clear_json(self, tmp_path):
        """GREEN: lock status on clear lock returns held=false."""
        # create a valid state file so doctor passes
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "job_name": "test",
                    "version": 1,
                    "project_root": str(tmp_path),
                    "state_path": str(state_path),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "counts": {
                        "pending": 1,
                        "in_progress": 0,
                        "succeeded": 0,
                        "failed_retryable": 0,
                        "red_verified": 0,
                        "green_verified": 0,
                        "full_suite_verified": 0,
                        "blocked": 0,
                        "skipped": 0,
                        "needs_review": 0,
                        "failed_final": 0,
                    },
                    "items": [
                        {
                            "id": "test:T1",
                            "title": "Test item",
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
                    ],
                }
            )
        )
        result = invoke_lock(
            ["lock", "status", "--state", str(state_path), "--json"],
        )
        data = json.loads(result.output)
        assert data["held"] is False
        assert data["run_id"] is None

    def test_lock_held_shows_run_id_and_acquired_at(self, tmp_path):
        """GREEN: lock status on held lock returns run_id and acquired_at."""
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "job_name": "test",
                    "version": 1,
                    "project_root": str(tmp_path),
                    "state_path": str(state_path),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "counts": {
                        "pending": 1,
                        "in_progress": 0,
                        "succeeded": 0,
                        "failed_retryable": 0,
                        "red_verified": 0,
                        "green_verified": 0,
                        "full_suite_verified": 0,
                        "blocked": 0,
                        "skipped": 0,
                        "needs_review": 0,
                        "failed_final": 0,
                    },
                    "items": [
                        {
                            "id": "test:T1",
                            "title": "Test item",
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
                    ],
                }
            )
        )
        lock_path = tmp_path / LOCK_DIR_NAME
        lock_path.mkdir()
        acquired = datetime.now(UTC).isoformat()
        write_lock_metadata(lock_path, "run-abc-123", acquired)

        result = invoke_lock(
            ["lock", "status", "--state", str(state_path), "--json"],
        )
        data = json.loads(result.output)
        assert data["held"] is True
        assert data["run_id"] == "run-abc-123"
        assert data["acquired_at"] == acquired

    def test_stale_vs_fresh_classification(self, tmp_path):
        """GREEN: lock status marks stale vs fresh using default 60-minute timeout."""
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "job_name": "test",
                    "version": 1,
                    "project_root": str(tmp_path),
                    "state_path": str(state_path),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "counts": {
                        "pending": 1,
                        "in_progress": 0,
                        "succeeded": 0,
                        "failed_retryable": 0,
                        "red_verified": 0,
                        "green_verified": 0,
                        "full_suite_verified": 0,
                        "blocked": 0,
                        "skipped": 0,
                        "needs_review": 0,
                        "failed_final": 0,
                    },
                    "items": [
                        {
                            "id": "test:T1",
                            "title": "Test item",
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
                    ],
                }
            )
        )
        lock_path = tmp_path / LOCK_DIR_NAME
        lock_path.mkdir()

        # Fresh lock: acquired 5 minutes ago
        five_min_ago = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        write_lock_metadata(lock_path, "run-fresh", five_min_ago)

        result = invoke_lock(
            ["lock", "status", "--state", str(state_path), "--json"],
        )
        data = json.loads(result.output)
        assert data["held"] is True
        assert data["is_stale"] is False

        # Stale lock: acquired 90 minutes ago
        ninety_min_ago = (datetime.now(UTC) - timedelta(minutes=90)).isoformat()
        write_lock_metadata(lock_path, "run-stale", ninety_min_ago)

        result = invoke_lock(
            ["lock", "status", "--state", str(state_path), "--json"],
        )
        data = json.loads(result.output)
        assert data["held"] is True
        assert data["is_stale"] is True


# ---------------------------------------------------------------------------
# lock recover
# ---------------------------------------------------------------------------

class TestLockRecover:
    """`stateful-dev lock recover --state <path> [--confirm]`"""

    def test_command_does_not_exist(self, tmp_path):
        """RED: lock recover command does not exist yet."""
        result = invoke_lock(
            ["lock", "recover", "--state", str(tmp_path / "nonexistent.json")],
        )
        assert result.exit_code == 2

    def test_refuses_fresh_lock_recovery(self, tmp_path):
        """GREEN: recovers a stale lock but refuses a fresh one."""
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "job_name": "test",
                    "version": 1,
                    "project_root": str(tmp_path),
                    "state_path": str(state_path),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "counts": {
                        "pending": 1,
                        "in_progress": 0,
                        "succeeded": 0,
                        "failed_retryable": 0,
                        "red_verified": 0,
                        "green_verified": 0,
                        "full_suite_verified": 0,
                        "blocked": 0,
                        "skipped": 0,
                        "needs_review": 0,
                        "failed_final": 0,
                    },
                    "items": [
                        {
                            "id": "test:T1",
                            "title": "Test item",
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
                    ],
                }
            )
        )
        lock_path = tmp_path / LOCK_DIR_NAME
        lock_path.mkdir()
        # Fresh lock (5 minutes old)
        five_min_ago = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        write_lock_metadata(lock_path, "run-fresh", five_min_ago)

        result = invoke_lock(
            ["lock", "recover", "--state", str(state_path), "--confirm"],
        )
        # Must refuse
        assert result.exit_code == 1
        assert "fresh" in result.output.lower() or "active" in result.output.lower()
        # Lock must still exist
        assert lock_path.exists()

    def test_recovers_stale_lock(self, tmp_path):
        """GREEN: recovers a stale lock after backup and doctor validation."""
        state_path = tmp_path / "state.json"
        state_data = {
            "job_name": "test",
            "version": 1,
            "project_root": str(tmp_path),
            "state_path": str(state_path),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "counts": {
                "pending": 1,
                "in_progress": 0,
                "succeeded": 0,
                "failed_retryable": 0,
                "red_verified": 0,
                "green_verified": 0,
                "full_suite_verified": 0,
                "blocked": 0,
                "skipped": 0,
                "needs_review": 0,
                "failed_final": 0,
            },
            "items": [
                {
                    "id": "test:T1",
                    "title": "Test item",
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
            ],
        }
        state_path.write_text(json.dumps(state_data))

        # Create a stale lock
        lock_path = tmp_path / LOCK_DIR_NAME
        lock_path.mkdir()
        ninety_min_ago = (datetime.now(UTC) - timedelta(minutes=90)).isoformat()
        write_lock_metadata(lock_path, "run-stale-crashed", ninety_min_ago)

        # Recover with --confirm
        result = invoke_lock(
            ["lock", "recover", "--state", str(state_path), "--confirm"],
        )
        assert result.exit_code == 0, result.output
        # Lock must be gone
        assert not lock_path.exists()

    def test_recover_requires_confirm_flag(self, tmp_path):
        """GREEN: recover without --confirm exits non-zero and does not remove lock."""
        state_path = tmp_path / "state.json"
        state_path.write_text(
            json.dumps(
                {
                    "job_name": "test",
                    "version": 1,
                    "project_root": str(tmp_path),
                    "state_path": str(state_path),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "counts": {
                        "pending": 1,
                        "in_progress": 0,
                        "succeeded": 0,
                        "failed_retryable": 0,
                        "red_verified": 0,
                        "green_verified": 0,
                        "full_suite_verified": 0,
                        "blocked": 0,
                        "skipped": 0,
                        "needs_review": 0,
                        "failed_final": 0,
                    },
                    "items": [
                        {
                            "id": "test:T1",
                            "title": "Test item",
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
                    ],
                }
            )
        )
        lock_path = tmp_path / LOCK_DIR_NAME
        lock_path.mkdir()
        ninety_min_ago = (datetime.now(UTC) - timedelta(minutes=90)).isoformat()
        write_lock_metadata(lock_path, "run-stale", ninety_min_ago)

        result = invoke_lock(
            ["lock", "recover", "--state", str(state_path)],
        )
        # Must refuse without --confirm
        assert result.exit_code == 1
        assert lock_path.exists()


# ---------------------------------------------------------------------------
# pytest runner fixture
# ---------------------------------------------------------------------------

def invoke_lock(args):
    """Invoke the CLI with the given lock subcommand args."""
    from stateful_dev.cli import app
    return CliRunner().invoke(app, args)
