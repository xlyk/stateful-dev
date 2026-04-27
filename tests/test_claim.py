"""Tests for the claim command.

These tests define the expected behavior of `stateful-dev claim`:
- validate state
- respect fresh locks
- return active item if one exists
- atomically claim one eligible item (failed_retryable before pending)
- increment attempts
- record run metadata
- emit compact JSON
"""
import json
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app
from stateful_dev.locking import acquire_lock, release_lock


def _write_state(
    path: Path, items: list[dict], *, job_name: str = "demo-worker"
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


def test_claim_rejects_fresh_lock(tmp_path: Path) -> None:
    """A held (non-stale) lock must cause claim to exit non-zero."""
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [{"id": "plan:T1-one", "title": "One", "status": "pending"}],
    )
    lock = acquire_lock(state_path.parent, run_id="other-run", timeout_minutes=60)
    try:
        result = CliRunner().invoke(
            app,
            ["claim", "--state", str(state_path), "--run-id", "this-run"],
        )
        assert result.exit_code == 1
        assert "fresh lock" in result.output or "held" in result.output.lower()
    finally:
        release_lock(lock)


def test_claim_returns_active_item_when_one_exists(tmp_path: Path) -> None:
    """If an item is in an active status, claim returns it without modifying state."""
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [
            {
                "id": "plan:T1-active",
                "title": "Active work",
                "status": "red_verified",
                "attempts": 1,
            },
            {"id": "plan:T2-pending", "title": "Pending work", "status": "pending"},
        ],
    )

    result = CliRunner().invoke(
        app,
        ["claim", "--state", str(state_path), "--run-id", "cron-run-abc"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["claimed"] is True
    assert payload["item"]["id"] == "plan:T1-active"
    assert payload["item"]["status"] == "red_verified"


def test_claim_atomic_transition_pending_to_in_progress(tmp_path: Path) -> None:
    """Claiming a pending item transitions it atomically to in_progress."""
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [
            {"id": "plan:T1-done", "title": "Done", "status": "succeeded"},
            {
                "id": "plan:T2-claim",
                "title": "Claim me",
                "status": "pending",
                "attempts": 0,
            },
        ],
    )

    result = CliRunner().invoke(
        app,
        ["claim", "--state", str(state_path), "--run-id", "cron-run-abc"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["claimed"] is True
    assert payload["item"]["id"] == "plan:T2-claim"
    assert payload["item"]["status"] == "in_progress"

    # Verify state file was updated
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    t2 = next(i for i in saved["items"] if i["id"] == "plan:T2-claim")
    assert t2["status"] == "in_progress"
    assert t2["attempts"] == 1
    assert saved["counts"]["pending"] == 0
    assert saved["counts"]["in_progress"] == 1


def test_claim_prefers_failed_retryable_before_pending(tmp_path: Path) -> None:
    """Eligible selection order is failed_retryable first, then pending."""
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [
            {"id": "plan:T1-pending", "title": "Pending item", "status": "pending"},
            {
                "id": "plan:T2-retry",
                "title": "Retry item",
                "status": "failed_retryable",
                "attempts": 1,
            },
        ],
    )

    result = CliRunner().invoke(
        app,
        ["claim", "--state", str(state_path), "--run-id", "cron-run-abc"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["item"]["id"] == "plan:T2-retry"


def test_claim_returns_null_when_no_eligible_items(tmp_path: Path) -> None:
    """When all items are terminal, claim returns claimed=false with no item."""
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [
            {"id": "plan:T1-done", "title": "Done", "status": "succeeded"},
            {"id": "plan:T2-blocked", "title": "Blocked", "status": "blocked"},
        ],
    )

    result = CliRunner().invoke(
        app,
        ["claim", "--state", str(state_path), "--run-id", "cron-run-abc"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["claimed"] is False
    assert payload["item"] is None


def test_claim_invalid_state_exits_nonzero(tmp_path: Path) -> None:
    """Invalid state causes a non-zero exit and informative output."""
    state_path = tmp_path / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"items": []}', encoding="utf-8")  # missing required keys

    result = CliRunner().invoke(
        app,
        ["claim", "--state", str(state_path), "--run-id", "cron-run-abc"],
    )

    assert result.exit_code != 0


def test_claim_json_shape(tmp_path: Path) -> None:
    """The claim output JSON has the expected fields."""
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [{"id": "plan:T1-test", "title": "Test", "status": "pending"}],
    )

    result = CliRunner().invoke(
        app,
        ["claim", "--state", str(state_path), "--run-id", "cron-run-abc"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    # Verify all required keys are present
    required = {"claimed", "item", "run_id"}
    assert required.issubset(payload.keys()), f"missing: {required - payload.keys()}"
    if payload["claimed"]:
        assert all(
            k in payload["item"] for k in ("id", "title", "status", "attempts")
        )


def test_claim_resumes_failed_retryable(tmp_path: Path) -> None:
    """A failed_retryable item can be claimed and resumes with incremented attempts."""
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [
            {
                "id": "plan:T1-failed",
                "title": "Failed once",
                "status": "failed_retryable",
                "attempts": 1,
                "max_attempts": 3,
            }
        ],
    )

    result = CliRunner().invoke(
        app,
        ["claim", "--state", str(state_path), "--run-id", "cron-run-abc"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["claimed"] is True
    assert payload["item"]["id"] == "plan:T1-failed"
    assert payload["item"]["status"] == "in_progress"
    assert payload["item"]["attempts"] == 2  # incremented

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    t1 = saved["items"][0]
    assert t1["status"] == "in_progress"
    assert t1["attempts"] == 2


def test_claim_records_active_run_id_and_claimed_at(tmp_path: Path) -> None:
    """When claiming a pending item, active_run_id and claimed_at are persisted."""
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [
            {
                "id": "plan:T1-test",
                "title": "Test item",
                "status": "pending",
                "attempts": 0,
            }
        ],
    )
    run_id = "cron-run-xyz-123"

    result = CliRunner().invoke(
        app,
        ["claim", "--state", str(state_path), "--run-id", run_id],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["claimed"] is True
    assert payload["item"]["id"] == "plan:T1-test"

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    t1 = saved["items"][0]
    assert t1["status"] == "in_progress"
    assert t1.get("active_run_id") == run_id
    assert t1.get("claimed_at") is not None
    # claimed_at should be a parseable ISO timestamp
    from datetime import datetime
    parsed = datetime.fromisoformat(t1["claimed_at"])
    assert parsed.tzinfo is not None  # must be timezone-aware UTC
