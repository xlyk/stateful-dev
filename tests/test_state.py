from stateful_dev.state import validate_state


def test_validate_state_recomputes_counts_and_reports_drift():
    data = {
        "job_name": "stateful-dev-worker",
        "version": 1,
        "project_root": "/tmp/project",
        "plan_paths": ["docs/plans/example.md"],
        "counts": {
            "pending": 99,
            "in_progress": 0,
            "red_verified": 0,
            "green_verified": 0,
            "succeeded": 0,
            "failed_retryable": 0,
            "failed_final": 0,
            "needs_review": 0,
            "blocked": 0,
            "skipped": 0,
        },
        "items": [
            {"id": "plan:T1-one", "status": "pending"},
            {"id": "plan:T2-two", "status": "succeeded"},
        ],
    }

    result = validate_state(data)

    assert result.ok is False
    assert result.counts["pending"] == 1
    assert result.counts["succeeded"] == 1
    assert "count drift for pending: expected 1, found 99" in result.errors


def test_validate_state_reports_duplicate_item_ids_and_bad_statuses():
    data = {
        "job_name": "stateful-dev-worker",
        "version": 1,
        "project_root": "/tmp/project",
        "plan_paths": ["docs/plans/example.md"],
        "counts": {},
        "items": [
            {"id": "plan:T1-one", "status": "pending"},
            {"id": "plan:T1-one", "status": "unknown"},
        ],
    }

    result = validate_state(data)

    assert result.ok is False
    assert "duplicate item id: plan:T1-one" in result.errors
    assert "invalid status for plan:T1-one: unknown" in result.errors
