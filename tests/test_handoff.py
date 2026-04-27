"""Tests for the handoff CLI command — operator handoff for blocked items.

RED: command does not exist (exit 2, no such subcommand).
GREEN: command exists, accepts question/why/recommended-answer/allowed-next-action,
item context, and emits plain text + JSON output.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app


def test_handoff_subcommand_exists() -> None:
    """RED: exit 2 — handoff command does not exist."""
    runner = CliRunner()
    result = runner.invoke(app, ["handoff", "--help"])
    assert result.exit_code != 2, f"Expected command to exist, got: {result.output}"


def test_handoff_emits_plain_text_output(tmp_path: Path) -> None:
    """Plain text output contains question, why, recommendation, and context."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "handoff",
            "--question",
            "Should we accept coverage-only evidence?",
            "--why",
            "The focused test passed immediately.",
            "--recommended-answer",
            "Mark needs_review and wait for explicit approval.",
            "--allowed-next-action",
            "Update the item status after the operator answers.",
            "--job-name",
            "test-worker",
            "--project-root",
            str(tmp_path),
            "--plan-path",
            "docs/plans/test.md",
            "--state-path",
            str(tmp_path / "state.json"),
            "--item-id",
            "T1-test",
            "--title",
            "Test item",
            "--status",
            "needs_review",
            "--evidence",
            "Focused test passed immediately",
            "--evidence",
            "No production code was changed",
        ],
    )
    assert result.exit_code == 0, f"Command failed: {result.output}"
    output = result.stdout
    assert "test-worker needs operator input" in output
    assert "Should we accept coverage-only evidence?" in output
    assert "The focused test passed immediately." in output
    assert "Mark needs_review and wait for explicit approval." in output
    assert "T1-test — Test item" in output
    assert "Fresh agent handoff — copy/paste:" in output


def test_handoff_emits_json_output(tmp_path: Path) -> None:
    """--json flag emits a JSON payload with all required fields."""
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "handoff",
            "--json",
            "--question",
            "Should we accept coverage-only evidence?",
            "--why",
            "The focused test passed immediately.",
            "--recommended-answer",
            "Mark needs_review.",
            "--allowed-next-action",
            "Update item status after operator answers.",
            "--job-name",
            "test-worker",
            "--project-root",
            str(tmp_path),
            "--plan-path",
            "docs/plans/test.md",
            "--state-path",
            str(tmp_path / "state.json"),
            "--item-id",
            "T1-test",
            "--title",
            "Test item",
            "--status",
            "needs_review",
            "--evidence",
            "Focused test passed immediately",
            "--evidence",
            "No production code changed",
        ],
    )
    assert result.exit_code == 0, f"Command failed: {result.output}"
    payload = json.loads(result.stdout)
    assert payload["job_name"] == "test-worker"
    assert payload["question"] == "Should we accept coverage-only evidence?"
    assert payload["why"] == "The focused test passed immediately."
    assert payload["recommended_answer"] == "Mark needs_review."
    assert (
        payload["allowed_next_action"] == "Update item status after operator answers."
    )
    assert payload["item_id"] == "T1-test"
    assert payload["title"] == "Test item"
    assert payload["status"] == "needs_review"
    assert payload["evidence"] == [
        "Focused test passed immediately",
        "No production code changed",
    ]
    assert "plain" in payload
    assert "test-worker needs operator input" in payload["plain"]
