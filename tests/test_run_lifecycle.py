"""Tests for `stateful-dev run` subcommands: start, finish, fail."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app

RUNS_DIR_NAME = "runs"


def invoke_run(args):
    """Invoke the CLI with the given run subcommand args."""
    return CliRunner().invoke(app, args)


# --------------------------------------------------------------------------:
# run start
# --------------------------------------------------------------------------:


class TestRunStart:
    """`stateful-dev run start --state <path> --run-id <id> --item-id <id>`"""

    def test_start_without_item_id_fails(self, tmp_path):
        """GREEN: run start requires --item-id."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))
        result = invoke_run(
            ["run", "start", "--state", str(state_path), "--run-id", "r1"],
        )
        assert result.exit_code != 0

    def test_creates_run_summary_file(self, tmp_path):
        """GREEN: run start creates .agent-state/<job>/runs/<run-id>.json."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))
        result = invoke_run(
            [
                "run", "start",
                "--state", str(state_path),
                "--run-id", "2026-04-27T21:37:06Z",
                "--item-id", "test:T1",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        runs_dir = tmp_path / RUNS_DIR_NAME
        run_file = runs_dir / "2026-04-27T21:37:06Z.json"
        assert run_file.exists()
        run_data = json.loads(run_file.read_text())
        assert run_data["run_id"] == "2026-04-27T21:37:06Z"
        assert run_data["item_id"] == "test:T1"
        assert run_data["started_at"] is not None
        assert run_data["finished_at"] is None
        assert run_data["status"] == "in_progress"

    def test_start_idempotent_claims_existing_run(self, tmp_path):
        """GREEN: starting the same run twice is idempotent (no duplicate file)."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))
        for _ in range(2):
            result = invoke_run(
                [
                    "run", "start",
                    "--state", str(state_path),
                    "--run-id", "2026-04-27T21:37:06Z",
                    "--item-id", "test:T1",
                    "--json",
                ],
            )
            assert result.exit_code == 0, result.output
        runs_dir = tmp_path / RUNS_DIR_NAME
        assert len(list(runs_dir.glob("*.json"))) == 1


# --------------------------------------------------------------------------:
# run finish
# --------------------------------------------------------------------------:


class TestRunFinish:
    """`stateful-dev run finish --state <path> --run-id <id>`"""

    def test_finish_requires_run_id(self, tmp_path):
        """GREEN: run finish requires --run-id."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))
        result = invoke_run(
            ["run", "finish", "--state", str(state_path)],
        )
        assert result.exit_code != 0

    def test_finish_closes_run_and_records_summary(self, tmp_path):
        """GREEN: run finish marks the run file as success and records finished_at."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))

        # Start the run first
        invoke_run(
            [
                "run", "start",
                "--state", str(state_path),
                "--run-id", "2026-04-27T21:37:06Z",
                "--item-id", "test:T1",
            ],
        )

        result = invoke_run(
            [
                "run", "finish",
                "--state", str(state_path),
                "--run-id", "2026-04-27T21:37:06Z",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        run_file = tmp_path / RUNS_DIR_NAME / "2026-04-27T21:37:06Z.json"
        run_data = json.loads(run_file.read_text())
        assert run_data["status"] == "success"
        assert run_data["finished_at"] is not None
        # started_at must still be set
        assert run_data["started_at"] is not None

    def test_finish_nonexistent_run_returns_error(self, tmp_path):
        """GREEN: finishing a nonexistent run returns ok=false with exit 1."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))
        result = invoke_run(
            [
                "run", "finish",
                "--state", str(state_path),
                "--run-id", "nonexistent-run",
                "--json",
            ],
        )
        assert result.exit_code == 1, result.output
        data = json.loads(result.output)
        assert data["ok"] is False
        assert "not found" in data.get("error", "").lower()


# --------------------------------------------------------------------------:
# run fail
# --------------------------------------------------------------------------:


class TestRunFail:
    """`stateful-dev run fail --state <path> --run-id <id> --reason <reason>`"""

    def test_fail_requires_reason(self, tmp_path):
        """GREEN: run fail requires --reason."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))
        result = invoke_run(
            ["run", "fail", "--state", str(state_path), "--run-id", "r1"],
        )
        assert result.exit_code != 0

    def test_fail_closes_run_with_failure_status(self, tmp_path):
        """GREEN: run fail marks the run file as failure and records reason."""
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(_minimal_state()))

        # Start the run first
        invoke_run(
            [
                "run", "start",
                "--state", str(state_path),
                "--run-id", "2026-04-27T21:37:06Z",
                "--item-id", "test:T1",
            ],
        )

        result = invoke_run(
            [
                "run", "fail",
                "--state", str(state_path),
                "--run-id", "2026-04-27T21:37:06Z",
                "--reason", "test failure",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["ok"] is True
        run_file = tmp_path / RUNS_DIR_NAME / "2026-04-27T21:37:06Z.json"
        run_data = json.loads(run_file.read_text())
        assert run_data["status"] == "failure"
        assert run_data["finished_at"] is not None
        assert run_data["reason"] == "test failure"


# --------------------------------------------------------------------------:
# fixture helper
# --------------------------------------------------------------------------:

def _minimal_state() -> dict:
    return {
        "job_name": "test-job",
        "version": 1,
        "project_root": str(Path("/tmp")),
        "state_path": str(Path("/tmp") / "state.json"),
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
