"""Tests for `stateful-dev backup` and `doctor --fix-counts`."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app

_runner = CliRunner()


def _minimal_state(extra_counts: dict | None = None, items: list | None = None) -> dict:
    counts = {
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
    }
    if extra_counts:
        counts.update(extra_counts)
    return {
        "job_name": "test-worker",
        "version": 1,
        "project_root": "/tmp",
        "plan_paths": ["docs/plans/test.md"],
        "state_path": str(Path("/tmp/state.json")),
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "counts": counts,
        "items": items or [
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


# ---------------------------------------------------------------------------
# backup command
# ---------------------------------------------------------------------------

class TestBackupCommand:
    """`stateful-dev backup --state <path> --label <label> [--json]`"""

    def test_backup_command_exists_and_succeeds(self, tmp_path: Path) -> None:
        """GREEN: backup command exists and exits 0 on success."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))
        result = _runner.invoke(
            app,
            ["backup", "--state", str(state_path), "--label", "before-fix"],
        )
        assert result.exit_code == 0, f"backup should succeed: {result.output}"
        assert "backed up" in result.output, (
            f"expected 'backed up' in output: {result.output}"
        )

    def test_backup_creates_timestamped_copy(self, tmp_path: Path) -> None:
        """GREEN: backup creates a timestamped .bak file next to the state file."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))

        result = _runner.invoke(
            app,
            ["backup", "--state", str(state_path), "--label", "before-fix"],
        )

        assert result.exit_code == 0, f"backup failed: {result.output}"
        backups = list(tmp_path.glob("state.json.bak*"))
        assert len(backups) == 1, f"expected exactly one backup, found: {backups}"
        bak_data = json.loads(backups[0].read_text())
        assert bak_data["job_name"] == "test-worker"

    def test_backup_label_appears_in_filename(self, tmp_path: Path) -> None:
        """GREEN: the label is embedded in the backup filename."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))

        _runner.invoke(
            app,
            ["backup", "--state", str(state_path), "--label", "my-label"],
        )

        backups = list(tmp_path.glob("state.json.bak*my-label*"))
        assert len(backups) == 1, (
            f"expected backup with label in filename: "
            f"{list(tmp_path.glob('state.json.bak*'))}"
        )

    def test_backup_returns_json_payload(self, tmp_path: Path) -> None:
        """GREEN: --json returns structured payload with path and timestamp."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))

        result = _runner.invoke(
            app,
            ["backup", "--state", str(state_path), "--label", "test", "--json"],
        )

        assert result.exit_code == 0, f"backup --json failed: {result.output}"
        payload = json.loads(result.stdout)
        assert "backup_path" in payload, f"expected backup_path in payload: {payload}"
        assert "backup_at" in payload, f"expected backup_at in payload: {payload}"


# ---------------------------------------------------------------------------
# doctor --fix-counts
# ---------------------------------------------------------------------------

class TestDoctorFixCounts:
    """`doctor --state <path> [--fix-counts] [--backup]`"""

    def test_fix_counts_flag_is_recognized(self, tmp_path: Path) -> None:
        """GREEN: --fix-counts option is recognized and fixes counts without error."""
        state_path = tmp_path / "state.json"
        state = _minimal_state(
            extra_counts={"pending": 1},
            items=[{
                "id": "test:T1",
                "title": "Test item",
                "status": "succeeded",
                "attempts": 1,
                "max_attempts": 3,
                "red_verified": True,
                "green_verified": True,
                "full_suite_verified": True,
                "files_touched": [],
                "test_commands": [],
                "commit_sha": None,
                "needs_operator": False,
                "result": None,
            }],
        )
        state_path.write_text(json.dumps(state))

        result = _runner.invoke(
            app,
            ["doctor", "--state", str(state_path), "--fix-counts"],
        )
        assert result.exit_code == 0, f"--fix-counts should succeed: {result.output}"
        assert "ok" in result.output.lower(), f"expected ok in output: {result.output}"

    def test_fix_counts_repairs_drift(self, tmp_path: Path) -> None:
        """GREEN: --fix-counts recomputes counts from items; never touches statuses."""
        # State has wrong counts (pending:1 but item is succeeded)
        state_path = tmp_path / "state.json"
        state = _minimal_state(
            extra_counts={"pending": 1, "succeeded": 0},
            items=[{
                "id": "test:T1",
                "title": "Test item",
                "status": "succeeded",  # item is succeeded but counts say pending=1
                "attempts": 1,
                "max_attempts": 3,
                "red_verified": True,
                "green_verified": True,
                "full_suite_verified": True,
                "files_touched": [],
                "test_commands": [],
                "commit_sha": None,
                "needs_operator": False,
                "result": None,
            }],
        )
        state_path.write_text(json.dumps(state))

        result = _runner.invoke(
            app,
            ["doctor", "--state", str(state_path), "--fix-counts", "--json"],
        )

        assert result.exit_code == 0, f"--fix-counts failed: {result.output}"
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, f"expected ok=True after fix: {payload}"
        assert payload["counts"]["succeeded"] == 1, (
            f"expected succeeded=1: {payload['counts']}"
        )
        assert payload["counts"]["pending"] == 0, (
            f"expected pending=0: {payload['counts']}"
        )

    def test_fix_counts_does_not_mutate_item_statuses(self, tmp_path: Path) -> None:
        """GREEN: --fix-counts only repairs counts, never changes item statuses."""
        state_path = tmp_path / "state.json"
        state = _minimal_state(
            extra_counts={"pending": 2},  # WRONG — both items pending
            items=[
                {
                    "id": "test:T1",
                    "title": "Item 1",
                    "status": "in_progress",  # NOT pending
                    "attempts": 1,
                    "max_attempts": 3,
                    "red_verified": False,
                    "green_verified": False,
                    "full_suite_verified": False,
                    "files_touched": [],
                    "test_commands": [],
                    "commit_sha": None,
                    "needs_operator": False,
                    "result": None,
                },
                {
                    "id": "test:T2",
                    "title": "Item 2",
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
                },
            ],
        )
        state_path.write_text(json.dumps(state))

        _runner.invoke(app, ["doctor", "--state", str(state_path), "--fix-counts"])

        fixed = json.loads(state_path.read_text())
        # Statuses must not have changed
        statuses = {item["id"]: item["status"] for item in fixed["items"]}
        assert statuses["test:T1"] == "in_progress"
        assert statuses["test:T2"] == "pending"
        # But counts should be correct
        assert fixed["counts"]["in_progress"] == 1
        assert fixed["counts"]["pending"] == 1

    def test_fix_counts_with_backup_flag_creates_backup(self, tmp_path: Path) -> None:
        """GREEN: --backup creates a .bak file before fixing counts."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state(extra_counts={"pending": 99})))

        result = _runner.invoke(
            app,
            [
                "doctor",
                "--state",
                str(state_path),
                "--fix-counts",
                "--backup",
                "--json",
            ],
        )

        assert result.exit_code == 0, f"--fix-counts --backup failed: {result.output}"
        backups = list(tmp_path.glob("state.json.bak*"))
        assert len(backups) >= 1, (
            f"expected at least one backup: {list(tmp_path.glob('state.json.bak*'))}"
        )

    def test_fix_counts_returns_updated_counts_in_payload(self, tmp_path: Path) -> None:
        """GREEN: --fix-counts returns the recomputed counts in the JSON payload."""
        state_path = tmp_path / "state.json"
        state = _minimal_state(
            extra_counts={"pending": 0, "succeeded": 1},
            items=[{
                "id": "test:T1",
                "title": "Test item",
                "status": "succeeded",
                "attempts": 1,
                "max_attempts": 3,
                "red_verified": True,
                "green_verified": True,
                "full_suite_verified": True,
                "files_touched": [],
                "test_commands": [],
                "commit_sha": None,
                "needs_operator": False,
                "result": None,
            }],
        )
        state_path.write_text(json.dumps(state))

        result = _runner.invoke(
            app,
            ["doctor", "--state", str(state_path), "--fix-counts", "--json"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["counts"]["succeeded"] == 1
        assert payload["counts"]["pending"] == 0
