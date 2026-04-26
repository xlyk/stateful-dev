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


def test_validate_state_reports_top_level_field_type_errors():
    data = {
        "job_name": 123,
        "version": "1",
        "project_root": None,
        "plan_paths": ["docs/plans/example.md", 99],
        "counts": {"pending": "1"},
        "items": [],
    }

    result = validate_state(data)

    assert result.ok is False
    assert "job_name must be a string" in result.errors
    assert "version must be an integer" in result.errors
    assert "project_root must be a string" in result.errors
    assert "plan_paths[1] must be a string" in result.errors
    assert "count for pending must be an integer" in result.errors


def test_validate_state_reports_optional_item_field_type_errors():
    data = {
        "job_name": "stateful-dev-worker",
        "version": 1,
        "project_root": "/tmp/project",
        "plan_paths": ["docs/plans/example.md"],
        "counts": {"pending": 1},
        "items": [
            {
                "id": "plan:T1-one",
                "status": "pending",
                "plan_path": 123,
                "title": None,
                "attempts": "0",
                "red_verified": "false",
                "green_verified": 0,
                "full_suite_verified": [],
                "files_touched": "src/file.py",
                "test_commands": {},
                "commit_sha": 42,
                "needs_operator": "no",
                "result": False,
            }
        ],
    }

    result = validate_state(data)

    assert result.ok is False
    assert "plan_path for plan:T1-one must be a string" in result.errors
    assert "title for plan:T1-one must be a string" in result.errors
    assert "attempts for plan:T1-one must be an integer" in result.errors
    assert "red_verified for plan:T1-one must be a boolean" in result.errors
    assert "green_verified for plan:T1-one must be a boolean" in result.errors
    assert "full_suite_verified for plan:T1-one must be a boolean" in result.errors
    assert "files_touched for plan:T1-one must be a list" in result.errors
    assert "test_commands for plan:T1-one must be a list" in result.errors
    assert "commit_sha for plan:T1-one must be a string or null" in result.errors
    assert "needs_operator for plan:T1-one must be a boolean" in result.errors
    assert "result for plan:T1-one must be a string or null" in result.errors
