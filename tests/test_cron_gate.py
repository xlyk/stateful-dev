"""Tests for the cron-gate command.

The cron-gate command owns deterministic local wake/skip decisions for Hermes cron.
Emits the contract-defined wakeAgent JSON without duplicating claim/status/lock logic.

Acceptance criteria:
- cron-gate --state --project-root --worker-id --run-id --json exists
- Emits the contract-defined wake/skip/blocker JSON
- Local state/git/lock decisions stay in cron-gate; wrappers stay thin
- Covers no-work, blocker, active item, eligible item, dirty git, invalid state
"""
import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app
from stateful_dev.locking import acquire_lock, release_lock


def _write_state(
    path: Path, items: list[dict], *, job_name: str = "test-worker"
) -> None:
    counts = {
        "pending": 0,
        "in_progress": 0,
        "red_verified": 0,
        "green_verified": 0,
        "succeeded": 0,
        "needs_review": 0,
        "blocked": 0,
        "failed_retryable": 0,
        "failed_final": 0,
        "skipped": 0,
    }
    for item in items:
        counts[str(item["status"])] += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "job_name": job_name,
                "version": 1,
                "project_root": str(path.parent),
                "plan_paths": ["docs/plans/demo.md"],
                "counts": counts,
                "items": items,
            }
        ),
        encoding="utf-8",
    )


def _git_status_head(state_dir: Path) -> str:
    """Return subprocess output for git status in given directory."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=state_dir,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class TestCronGateNoWork:
    """When all items are terminal, cron-gate emits skip with wakeAgent: false."""

    def test_skip_when_all_items_succeeded(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [
                {"id": "plan:T1", "title": "One", "status": "succeeded"},
                {"id": "plan:T2", "title": "Two", "status": "succeeded"},
            ],
        )
        result = CliRunner().invoke(
            app,
            [
                "cron-gate",
                "--state", str(state_path),
                "--project-root", str(tmp_path),
                "--worker-id", "test-worker",
                "--run-id", "run-abc",
            ],
        )
        assert result.exit_code == 0
        payload = _last_json_line(result.output)
        assert payload["wakeAgent"] is False
        assert payload["mode"] == "skip"
        assert payload["complete"] is True
        assert payload["worker_id"] == "test-worker"
        assert payload["run_id"] == "run-abc"

    def test_skip_when_all_items_blocked(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [{"id": "plan:T1", "title": "One", "status": "blocked"}],
        )
        result = CliRunner().invoke(
            app,
            [
                "cron-gate",
                "--state", str(state_path),
                "--project-root", str(tmp_path),
                "--worker-id", "test-worker",
                "--run-id", "run-abc",
            ],
        )
        assert result.exit_code == 0
        payload = _last_json_line(result.output)
        assert payload["wakeAgent"] is False
        assert payload["mode"] == "skip"
        assert payload["complete"] is True


class TestCronGateActiveItem:
    """When an item is in an active status, cron-gate emits wake for that item."""

    def test_wake_with_active_in_progress_item(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [
                {
                    "id": "plan:T1",
                    "title": "In progress item",
                    "status": "in_progress",
                    "attempts": 1,
                },
                {"id": "plan:T2", "title": "Pending item", "status": "pending"},
            ],
        )
        result = CliRunner().invoke(
            app,
            [
                "cron-gate",
                "--state", str(state_path),
                "--project-root", str(tmp_path),
                "--worker-id", "test-worker",
                "--run-id", "run-abc",
            ],
        )
        assert result.exit_code == 0
        payload = _last_json_line(result.output)
        assert payload["wakeAgent"] is True
        assert payload["mode"] == "wake"
        assert payload["item_id"] == "plan:T1"
        assert payload["item_title"] == "In progress item"
        assert payload["item_status"] == "in_progress"
        assert payload["complete"] is False

    def test_wake_with_active_red_verified_item(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [
                {"id": "plan:T1", "title": "RED verified", "status": "red_verified"},
                {"id": "plan:T2", "title": "Pending", "status": "pending"},
            ],
        )
        result = CliRunner().invoke(
            app,
            [
                "cron-gate",
                "--state", str(state_path),
                "--project-root", str(tmp_path),
                "--worker-id", "test-worker",
                "--run-id", "run-abc",
            ],
        )
        assert result.exit_code == 0
        payload = _last_json_line(result.output)
        assert payload["wakeAgent"] is True
        assert payload["mode"] == "wake"
        assert payload["item_id"] == "plan:T1"
        assert payload["item_status"] == "red_verified"


class TestCronGateEligibleItem:
    """No active item but eligible items exist; cron-gate claims one and emits wake."""

    def test_wake_with_pending_item(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [
                {"id": "plan:T1", "title": "Done", "status": "succeeded"},
                {
                    "id": "plan:T2",
                    "title": "Next work",
                    "status": "pending",
                    "attempts": 0,
                },
            ],
        )
        result = CliRunner().invoke(
            app,
            [
                "cron-gate",
                "--state", str(state_path),
                "--project-root", str(tmp_path),
                "--worker-id", "test-worker",
                "--run-id", "run-abc",
            ],
        )
        assert result.exit_code == 0
        payload = _last_json_line(result.output)
        assert payload["wakeAgent"] is True
        assert payload["mode"] == "wake"
        assert payload["item_id"] == "plan:T2"
        assert payload["item_status"] == "in_progress"  # claim transitions

        # Verify state was updated
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        t2 = next(i for i in saved["items"] if i["id"] == "plan:T2")
        assert t2["status"] == "in_progress"
        assert t2["attempts"] == 1


class TestCronGateBlocker:
    """Tests for blocker mode when a condition requires operator action."""

    def test_blocker_when_state_invalid(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        path_str = str(state_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text('{"items": []}', encoding="utf-8")  # invalid: no items

        result = CliRunner().invoke(
            app,
            [
                "cron-gate",
                "--state", path_str,
                "--project-root", str(tmp_path),
                "--worker-id", "test-worker",
                "--run-id", "run-abc",
            ],
        )
        assert result.exit_code == 0  # cron-gate itself succeeds; blocker is in payload
        payload = _last_json_line(result.output)
        assert payload["wakeAgent"] is False
        assert payload["mode"] == "blocker"
        assert payload["blocker"] is not None
        assert payload["item_id"] is None

    def test_blocker_when_lock_held(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [{"id": "plan:T1", "title": "Work", "status": "pending"}],
        )
        lock = acquire_lock(state_path.parent, run_id="other-run", timeout_minutes=60)
        try:
            result = CliRunner().invoke(
                app,
                [
                    "cron-gate",
                    "--state", str(state_path),
                    "--project-root", str(tmp_path),
                    "--worker-id", "test-worker",
                    "--run-id", "run-abc",
                ],
            )
            assert result.exit_code == 0
            payload = _last_json_line(result.output)
            assert payload["wakeAgent"] is False
            assert payload["mode"] == "blocker"
            assert "lock" in payload["blocker"].lower()
        finally:
            release_lock(lock)

    def test_blocker_when_git_dirty(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [{"id": "plan:T1", "title": "Work", "status": "pending"}],
        )
        # Initialize a git repo so git status can detect dirty files
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path, capture_output=True,
        )
        # Create a dirty file in the project root
        dirty_file = tmp_path / "dirty.txt"
        dirty_file.write_text("uncommitted", encoding="utf-8")
        try:
            result = CliRunner().invoke(
                app,
                [
                    "cron-gate",
                    "--state", str(state_path),
                    "--project-root", str(tmp_path),
                    "--worker-id", "test-worker",
                    "--run-id", "run-abc",
                ],
            )
            assert result.exit_code == 0
            payload = _last_json_line(result.output)
            assert payload["wakeAgent"] is False
            assert payload["mode"] == "blocker"
            blk = payload["blocker"].lower()
            assert "git" in blk or "dirty" in blk
        finally:
            dirty_file.unlink(missing_ok=True)


class TestCronGateOutputFormat:
    """The JSON payload contains all required contract fields."""

    def test_payload_has_all_required_fields(self, tmp_path: Path) -> None:
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [{"id": "plan:T1", "title": "Work", "status": "pending"}],
        )
        result = CliRunner().invoke(
            app,
            [
                "cron-gate",
                "--state", str(state_path),
                "--project-root", str(tmp_path),
                "--worker-id", "my-worker",
                "--run-id", "run-xyz",
            ],
        )
        assert result.exit_code == 0
        payload = _last_json_line(result.output)
        required_fields = [
            "wakeAgent",
            "mode",
            "worker_id",
            "run_id",
            "project_root",
            "state_path",
            "item_id",
            "item_title",
            "item_status",
            "blocker",
            "complete",
            "message",
        ]
        missing = [f for f in required_fields if f not in payload]
        assert missing == [], f"missing required fields: {missing}"

    def test_stdin_does_not_affect_output(self, tmp_path: Path) -> None:
        """Stdin noise must not corrupt the JSON output."""
        state_path = tmp_path / "state.json"
        _write_state(
            state_path,
            [{"id": "plan:T1", "title": "Work", "status": "succeeded"}],
        )
        result = CliRunner().invoke(
            app,
            [
                "cron-gate",
                "--state", str(state_path),
                "--project-root", str(tmp_path),
                "--worker-id", "test-worker",
                "--run-id", "run-abc",
            ],
            input="some stdin noise\n",
        )
        assert result.exit_code == 0
        payload = _last_json_line(result.output)
        assert payload["mode"] == "skip"
        assert payload["complete"] is True


def _last_json_line(output: str) -> dict:
    """Extract the last non-empty line and parse it as JSON."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    last = lines[-1]
    return json.loads(last)
