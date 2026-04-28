"""Tests for evidence record commands (RED, GREEN, full-suite, lint)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app

runner = CliRunner()

# Shorter command/result strings to stay within ruff 88-char line limit
RED_CMD = "pytest tests/test_record.py -v"
RED_RES = "exit 1; FAILED - no such test"
GREEN_CMD = "pytest tests/test_record.py -v"
GREEN_RES = "exit 0; 1 passed"
FS_CMD = "pytest -q"
FS_RES = "exit 0; 5 passed"
LINT_CMD = "ruff check ."
LINT_RES = "exit 0; All checks passed"


def _make_state(tmp_path: Path, item_status: str = "in_progress") -> Path:
    state = {
        "job_name": "test-worker",
        "version": 1,
        "project_root": str(tmp_path),
        "state_path": str(tmp_path / "state.json"),
        "created_at": "2026-04-27T10:00:00+00:00",
        "updated_at": "2026-04-27T10:00:00+00:00",
        "counts": {
            "needs_review": 0,
            "skipped": 0,
            "succeeded": 0,
            "failed_final": 0,
            "red_verified": 0,
            "failed_retryable": 0,
            "blocked": 0,
            "in_progress": 1,
            "green_verified": 0,
            "pending": 0,
        },
        "items": [
            {
                "id": "plan:T1-test",
                "plan_path": str(tmp_path / "plan.md"),
                "title": "Test item",
                "status": item_status,
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
            }
        ],
    }
    path = tmp_path / "state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


class TestRecordRed:
    def test_record_red_stores_focused_red_evidence(self, tmp_path: Path):
        """record-red stores command and result in item's evidence list."""
        state_path = _make_state(tmp_path, item_status="in_progress")
        result = runner.invoke(
            app,
            [
                "record-red",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                RED_CMD,
                "--result",
                RED_RES,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(state_path.read_text(encoding="utf-8"))
        item = next(i for i in data["items"] if i["id"] == "plan:T1-test")
        assert len(item["evidence"]) == 1
        assert item["evidence"][0]["focused_red_command"] == RED_CMD
        assert item["evidence"][0]["focused_red_result"] == RED_RES

    def test_record_red_item_not_found(self, tmp_path: Path):
        """Non-existent item exits non-zero."""
        state_path = _make_state(tmp_path)
        result = runner.invoke(
            app,
            [
                "record-red",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T99-does-not-exist",
                "--command",
                "echo test",
                "--result",
                "exit 1",
            ],
        )
        assert result.exit_code == 1
        assert "item not found" in result.output

    def test_record_red_json_output(self, tmp_path: Path):
        """--json flag emits structured JSON."""
        state_path = _make_state(tmp_path)
        result = runner.invoke(
            app,
            [
                "record-red",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                RED_CMD,
                "--result",
                "exit 1; failed",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["item_id"] == "plan:T1-test"
        assert "focused_red_command" in data["evidence_keys"]

    def test_record_red_rejects_empty_command_and_result(self, tmp_path: Path):
        """record-red requires non-empty command and result values."""
        state_path = _make_state(tmp_path)
        result = runner.invoke(
            app,
            [
                "record-red",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                "",
                "--result",
                "",
            ],
        )
        assert result.exit_code == 1
        assert "must not be empty" in result.output

    def test_record_red_rejects_successful_result(self, tmp_path: Path):
        """RED evidence must describe an expected failure, not a pass."""
        state_path = _make_state(tmp_path)
        result = runner.invoke(
            app,
            [
                "record-red",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                RED_CMD,
                "--result",
                "exit 0; 1 passed",
            ],
        )
        assert result.exit_code == 1
        assert "RED evidence result appears to be a success" in result.output


class TestRecordGreen:
    def test_record_green_requires_red_evidence_first(self, tmp_path: Path):
        """GREEN evidence requires RED evidence to already be recorded."""
        state_path = _make_state(tmp_path, item_status="red_verified")
        result = runner.invoke(
            app,
            [
                "record-green",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                GREEN_CMD,
                "--result",
                GREEN_RES,
            ],
        )
        assert result.exit_code == 1
        assert "RED evidence must be recorded before GREEN" in result.output

    def test_record_green_stores_evidence_with_red_present(self, tmp_path: Path):
        """GREEN evidence is stored when RED evidence already exists."""
        state = {
            "job_name": "test-worker",
            "version": 1,
            "project_root": str(tmp_path),
            "state_path": str(tmp_path / "state.json"),
            "created_at": "2026-04-27T10:00:00+00:00",
            "updated_at": "2026-04-27T10:00:00+00:00",
            "counts": {
                "needs_review": 0,
                "skipped": 0,
                "succeeded": 0,
                "failed_final": 0,
                "red_verified": 1,
                "failed_retryable": 0,
                "blocked": 0,
                "in_progress": 0,
                "green_verified": 0,
                "pending": 0,
            },
            "items": [
                {
                    "id": "plan:T1-test",
                    "plan_path": str(tmp_path / "plan.md"),
                    "title": "Test item",
                    "status": "red_verified",
                    "attempts": 1,
                    "max_attempts": 3,
                    "red_verified": True,
                    "green_verified": False,
                    "full_suite_verified": False,
                    "files_touched": [],
                    "test_commands": [],
                    "commit_sha": None,
                    "needs_operator": False,
                    "result": None,
                    "evidence": [
                        {
                            "focused_red_command": RED_CMD,
                            "focused_red_result": RED_RES,
                        }
                    ],
                }
            ],
        }
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "record-green",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                GREEN_CMD,
                "--result",
                GREEN_RES,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(state_path.read_text(encoding="utf-8"))
        item = next(i for i in data["items"] if i["id"] == "plan:T1-test")
        assert len(item["evidence"]) == 2
        assert item["evidence"][1]["focused_green_command"] == GREEN_CMD
        assert item["evidence"][1]["focused_green_result"] == GREEN_RES


class TestRecordFullSuite:
    def test_record_full_suite_requires_red_evidence(self, tmp_path: Path):
        """full-suite evidence requires RED evidence to already be recorded."""
        state_path = _make_state(tmp_path, item_status="green_verified")
        result = runner.invoke(
            app,
            [
                "record-full-suite",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                FS_CMD,
                "--result",
                FS_RES,
            ],
        )
        assert result.exit_code == 1
        assert (
            "RED evidence must be recorded before GREEN or full-suite evidence"
            in result.output
        )

    def test_record_full_suite_stores_evidence(self, tmp_path: Path):
        """full-suite evidence is stored when RED evidence already exists."""
        state = {
            "job_name": "test-worker",
            "version": 1,
            "project_root": str(tmp_path),
            "state_path": str(tmp_path / "state.json"),
            "created_at": "2026-04-27T10:00:00+00:00",
            "updated_at": "2026-04-27T10:00:00+00:00",
            "counts": {
                "needs_review": 0,
                "skipped": 0,
                "succeeded": 0,
                "failed_final": 0,
                "red_verified": 1,
                "failed_retryable": 0,
                "blocked": 0,
                "in_progress": 0,
                "green_verified": 1,
                "pending": 0,
            },
            "items": [
                {
                    "id": "plan:T1-test",
                    "plan_path": str(tmp_path / "plan.md"),
                    "title": "Test item",
                    "status": "green_verified",
                    "attempts": 1,
                    "max_attempts": 3,
                    "red_verified": True,
                    "green_verified": True,
                    "full_suite_verified": False,
                    "files_touched": [],
                    "test_commands": [],
                    "commit_sha": None,
                    "needs_operator": False,
                    "result": None,
                    "evidence": [
                        {
                            "focused_red_command": RED_CMD,
                            "focused_red_result": RED_RES,
                        },
                        {
                            "focused_green_command": GREEN_CMD,
                            "focused_green_result": GREEN_RES,
                        },
                    ],
                }
            ],
        }
        state_path = tmp_path / "state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "record-full-suite",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                FS_CMD,
                "--result",
                FS_RES,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(state_path.read_text(encoding="utf-8"))
        item = next(i for i in data["items"] if i["id"] == "plan:T1-test")
        assert len(item["evidence"]) == 3
        assert item["evidence"][2]["full_suite_command"] == FS_CMD
        assert item["evidence"][2]["full_suite_result"] == FS_RES


class TestRecordLint:
    def test_record_lint_stores_lint_evidence(self, tmp_path: Path):
        """lint evidence is stored without preconditions."""
        state_path = _make_state(tmp_path)
        result = runner.invoke(
            app,
            [
                "record-lint",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                LINT_CMD,
                "--result",
                LINT_RES,
            ],
        )
        assert result.exit_code == 0
        data = json.loads(state_path.read_text(encoding="utf-8"))
        item = next(i for i in data["items"] if i["id"] == "plan:T1-test")
        assert len(item["evidence"]) == 1
        assert item["evidence"][0]["lint_command"] == LINT_CMD
        assert item["evidence"][0]["lint_result"] == LINT_RES

    def test_record_lint_recordable_from_in_progress(self, tmp_path: Path):
        """Lint can be recorded even when item has no RED evidence yet."""
        state_path = _make_state(tmp_path, item_status="in_progress")
        result = runner.invoke(
            app,
            [
                "record-lint",
                "--state",
                str(state_path),
                "--item-id",
                "plan:T1-test",
                "--command",
                LINT_CMD,
                "--result",
                LINT_RES,
            ],
        )
        assert result.exit_code == 0



def test_record_red_rejects_pending_item(tmp_path: Path):
    state_path = _make_state(tmp_path, item_status="pending")

    result = runner.invoke(
        app,
        [
            "record-red",
            "--state",
            str(state_path),
            "--item-id",
            "plan:T1-test",
            "--command",
            RED_CMD,
            "--result",
            RED_RES,
        ],
    )

    assert result.exit_code == 1
    assert "requires item status in_progress" in result.output


def test_record_green_rejects_in_progress_item_with_red_evidence(tmp_path: Path):
    state_path = _make_state(tmp_path, item_status="in_progress")
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["items"][0]["evidence"] = [
        {"focused_red_command": RED_CMD, "focused_red_result": RED_RES}
    ]
    state_path.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "record-green",
            "--state",
            str(state_path),
            "--item-id",
            "plan:T1-test",
            "--command",
            GREEN_CMD,
            "--result",
            GREEN_RES,
        ],
    )

    assert result.exit_code == 1
    assert "requires item status red_verified" in result.output


def test_record_full_suite_rejects_before_green_verified(tmp_path: Path):
    state_path = _make_state(tmp_path, item_status="red_verified")
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["items"][0]["evidence"] = [
        {"focused_red_command": RED_CMD, "focused_red_result": RED_RES},
        {"focused_green_command": GREEN_CMD, "focused_green_result": GREEN_RES},
    ]
    state_path.write_text(json.dumps(data), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "record-full-suite",
            "--state",
            str(state_path),
            "--item-id",
            "plan:T1-test",
            "--command",
            FS_CMD,
            "--result",
            FS_RES,
        ],
    )

    assert result.exit_code == 1
    assert "requires item status green_verified" in result.output
