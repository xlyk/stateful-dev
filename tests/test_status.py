import json
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app


def _write_state(path: Path, items: list[dict[str, object]]) -> None:
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
    path.write_text(
        json.dumps(
            {
                "job_name": "demo-worker",
                "version": 1,
                "project_root": str(path.parent),
                "plan_paths": ["docs/plans/demo.md"],
                "counts": counts,
                "items": items,
            }
        ),
        encoding="utf-8",
    )


def test_status_json_reports_worker_lifecycle_decision_fields(tmp_path: Path):
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [
            {"id": "plan:T1-active", "title": "Active work", "status": "red_verified"},
            {"id": "plan:T2-next", "title": "Next work", "status": "failed_retryable"},
            {"id": "plan:T3-later", "title": "Later work", "status": "pending"},
        ],
    )
    lock_dir = tmp_path / "lock"
    lock_dir.mkdir()
    (lock_dir / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": "cron-run-123",
                "acquired_at": datetime(2026, 4, 26, tzinfo=UTC).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "20260426T213000Z.json").write_text(
        json.dumps({"run_id": "20260426T213000Z", "processed_items": ["plan:T0"]}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["status", "--state", str(state_path), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["counts"]["red_verified"] == 1
    assert payload["active_item"] == {
        "id": "plan:T1-active",
        "title": "Active work",
        "status": "red_verified",
    }
    assert payload["next_eligible_item"] == {
        "id": "plan:T2-next",
        "title": "Next work",
        "status": "failed_retryable",
    }
    assert payload["lock"] == {
        "held": True,
        "run_id": "cron-run-123",
        "acquired_at": "2026-04-26T00:00:00+00:00",
    }
    assert payload["complete"] is False
    assert payload["last_run_summary"] == {
        "path": str(runs_dir / "20260426T213000Z.json"),
        "summary": {"run_id": "20260426T213000Z", "processed_items": ["plan:T0"]},
    }
    assert payload["suggested_next_action"] == "continue active item plan:T1-active"


def test_status_plain_output_is_compact_and_actionable(tmp_path: Path):
    state_path = tmp_path / "state.json"
    _write_state(
        state_path,
        [
            {"id": "plan:T1-done", "title": "Done", "status": "succeeded"},
            {"id": "plan:T2-next", "title": "Next", "status": "pending"},
        ],
    )

    result = CliRunner().invoke(app, ["status", "--state", str(state_path)])

    assert result.exit_code == 0
    assert "demo-worker" in result.stdout
    assert "pending: 1" in result.stdout
    assert "active: none" in result.stdout
    assert "next: plan:T2-next — Next (pending)" in result.stdout
    assert "lock: clear" in result.stdout
    assert "complete: no" in result.stdout
    assert "next action: claim next eligible item plan:T2-next" in result.stdout
