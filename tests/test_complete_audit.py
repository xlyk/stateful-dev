"""Tests for the complete/audit command — safe worker shutdown decisions.

RED: command does not exist (exit 2, no such subcommand).
GREEN: command exists, runs doctor, checks lock, verifies no active/retryable
work, and emits a structured shutdown-approval report.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app


def _write_state(
    path: Path, items: list[dict], counts: dict[str, int] | None = None
) -> None:
    """Write a minimal valid state file for testing."""
    if counts is None:
        counts = {s: 0 for s in [
            "pending", "in_progress", "red_verified", "green_verified",
            "succeeded", "needs_review", "blocked", "failed_retryable",
            "failed_final", "skipped",
        ]}
        for item in items:
            status = str(item.get("status", "pending"))
            if status in counts:
                counts[status] += 1

    path.write_text(
        json.dumps(
            {
                "job_name": "test-worker",
                "version": 1,
                "project_root": str(path.parent),
                "plan_paths": ["docs/plans/test.md"],
                "state_path": str(path),
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "counts": counts,
                "items": items,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


class TestCompleteCommandExists:
    """Verify the complete command exists and is reachable."""

    def test_complete_subcommand_exists(self) -> None:
        """RED: exit 2 — complete command does not exist."""
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--help"])
        # Should not get "no such command" error
        assert result.exit_code != 2, f"Expected command to exist, got: {result.output}"


class TestCompleteShutdownDecision:
    """Verify complete command emits correct shutdown-approval decision fields."""

    def test_complete_safe_to_shutdown_when_all_succeeded_and_lock_clear(
        self, tmp_path: Path
    ) -> None:
        """When all items succeeded and lock is clear, shutdown_approved is True."""
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            items=[
                {"id": "T1", "title": "One", "status": "succeeded"},
                {"id": "T2", "title": "Two", "status": "succeeded"},
            ],
            counts={
                "succeeded": 2, "pending": 0, "in_progress": 0,
                "red_verified": 0, "green_verified": 0, "needs_review": 0,
                "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0,
            },
        )
        # No lock directory = lock clear
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--state", str(state_path), "--json"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.stdout)
        assert payload["shutdown_approved"] is True
        assert payload["doctor_ok"] is True
        assert payload["lock_clear"] is True
        assert payload["active_or_retryable_count"] == 0

    def test_complete_blocked_by_active_item(self, tmp_path: Path) -> None:
        """When an item is in_progress, shutdown is not approved."""
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            items=[
                {"id": "T1", "title": "Done", "status": "succeeded"},
                {"id": "T2", "title": "Active", "status": "in_progress"},
            ],
            counts={
                "succeeded": 1, "pending": 0, "in_progress": 1,
                "red_verified": 0, "green_verified": 0, "needs_review": 0,
                "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0,
            },
        )
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--state", str(state_path), "--json"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.stdout)
        assert payload["shutdown_approved"] is False
        assert payload["active_or_retryable_count"] == 1

    def test_complete_blocked_by_failed_retryable(self, tmp_path: Path) -> None:
        """When a failed_retryable item exists, shutdown is not approved."""
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            items=[
                {"id": "T1", "title": "Done", "status": "succeeded"},
                {
                    "id": "T2", "title": "Retry",
                    "status": "failed_retryable", "attempts": 2,
                },
            ],
            counts={
                "succeeded": 1, "pending": 0, "in_progress": 0,
                "red_verified": 0, "green_verified": 0, "needs_review": 0,
                "blocked": 0, "failed_retryable": 1, "failed_final": 0, "skipped": 0,
            },
        )
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--state", str(state_path), "--json"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.stdout)
        assert payload["shutdown_approved"] is False
        assert payload["failed_retryable_count"] == 1

    def test_complete_blocked_by_pending_item(self, tmp_path: Path) -> None:
        """Pending work must block shutdown approval."""
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            items=[
                {"id": "T1", "title": "Done", "status": "succeeded"},
                {"id": "T2", "title": "Pending", "status": "pending"},
            ],
            counts={
                "succeeded": 1, "pending": 1, "in_progress": 0,
                "red_verified": 0, "green_verified": 0, "needs_review": 0,
                "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0,
            },
        )
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--state", str(state_path), "--json"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.stdout)
        assert payload["shutdown_approved"] is False
        assert payload["pending_count"] == 1
        assert "pending" in payload["next_action"].lower()

    def test_complete_blocked_by_stale_lock(self, tmp_path: Path) -> None:
        """When a non-stale lock is held, shutdown is not approved."""
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            items=[{"id": "T1", "title": "Done", "status": "succeeded"}],
            counts={
                "succeeded": 1, "pending": 0, "in_progress": 0,
                "red_verified": 0, "green_verified": 0, "needs_review": 0,
                "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0,
            },
        )
        # Create a fresh (non-stale) lock
        lock_dir = tmp_path / "lock"
        lock_dir.mkdir()
        (lock_dir / "metadata.json").write_text(
            json.dumps({
                "run_id": "some-run-123",
                "acquired_at": datetime.now(UTC).isoformat(),
            }),
            encoding="utf-8",
        )
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--state", str(state_path), "--json"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.stdout)
        assert payload["shutdown_approved"] is False
        assert payload["lock_clear"] is False

    def test_complete_blocked_by_invalid_state(self, tmp_path: Path) -> None:
        """When doctor reports invalid state, shutdown is not approved."""
        state_path = tmp_path / "state.json"
        # Write state with no counts (missing required fields)
        state_path.write_text(
            json.dumps({"job_name": "bad", "items": []}), encoding="utf-8"
        )
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--state", str(state_path), "--json"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.stdout)
        assert payload["shutdown_approved"] is False
        assert payload["doctor_ok"] is False

    def test_complete_recommends_pause_or_remove_when_approved(
        self, tmp_path: Path
    ) -> None:
        """When shutdown is approved, next_action recommends pause/remove."""
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            items=[{"id": "T1", "title": "Done", "status": "succeeded"}],
            counts={
                "succeeded": 1, "pending": 0, "in_progress": 0,
                "red_verified": 0, "green_verified": 0, "needs_review": 0,
                "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0,
            },
        )
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--state", str(state_path), "--json"])
        assert result.exit_code == 0, f"Command failed: {result.output}"
        payload = json.loads(result.stdout)
        assert payload["shutdown_approved"] is True
        next_action_lower = payload["next_action"].lower()
        assert "pause" in next_action_lower or "remove" in next_action_lower

    def test_complete_plain_output_renders_readably(self, tmp_path: Path) -> None:
        """Plain (non-JSON) output is human-readable."""
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            items=[{"id": "T1", "title": "Done", "status": "succeeded"}],
            counts={
                "succeeded": 1, "pending": 0, "in_progress": 0,
                "red_verified": 0, "green_verified": 0, "needs_review": 0,
                "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0,
            },
        )
        runner = CliRunner()
        result = runner.invoke(app, ["complete", "--state", str(state_path)])
        assert result.exit_code == 0
        assert "shutdown_approved" in result.stdout
        assert "next_action" in result.stdout
