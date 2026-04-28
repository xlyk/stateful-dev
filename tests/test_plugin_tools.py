import importlib.util
import json
from pathlib import Path


def load_plugin_tools():
    tools_path = Path("plugins/stateful-dev/tools.py")
    spec = importlib.util.spec_from_file_location(
        "stateful_dev_plugin_tools", tools_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_state(path: Path, data: dict | None = None) -> None:
    if data is None:
        data = {
            "job_name": "sample-worker",
            "version": 1,
            "project_root": str(path.parent),
            "plan_paths": ["docs/plans/sample.md"],
            "counts": {"pending": 1, "in_progress": 0, "red_verified": 0, "green_verified": 0, "succeeded": 0, "needs_review": 0, "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0},
            "items": [
                {
                    "id": "sample:T1",
                    "title": "Sample task",
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
    path.write_text(json.dumps(data), encoding="utf-8")


def test_plugin_doctor_returns_json_payload(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    tools = load_plugin_tools()

    payload = tools.stateful_dev_doctor({"state": str(state_path)})

    json.dumps(payload)
    assert payload == {
        "ok": True,
        "errors": [],
        "warnings": [],
        "counts": {
            "pending": 1,
            "in_progress": 0,
            "red_verified": 0,
            "green_verified": 0,
            "succeeded": 0,
            "needs_review": 0,
            "blocked": 0,
            "failed_retryable": 0,
            "failed_final": 0,
            "skipped": 0,
        },
    }
    assert callable(tools.stateful_dev_report)


def test_plugin_report_returns_rendered_text(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    tools = load_plugin_tools()

    payload = tools.stateful_dev_report(
        {
            "state": str(state_path),
            "run_summary": {
                "plan": "docs/plans/sample.md",
                "processed": [],
                "gates": {"focused": "pass"},
                "state_path": str(state_path),
                "next_action": "will continue",
            },
        }
    )

    json.dumps(payload)
    assert payload["text"].startswith("sample-worker development batch")
    assert "Remaining: 1" in payload["text"]


# ---------------------------------------------------------------------------
# Tests for new T21 plugin tools
# ---------------------------------------------------------------------------


def test_plugin_status_returns_ok_and_counts(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    tools = load_plugin_tools()

    payload = tools.stateful_dev_status({"state": str(state_path)})

    assert payload["ok"] is True
    assert "counts" in payload
    assert "rendered" in payload
    assert payload["counts"]["pending"] == 1


def test_plugin_record_red_evidence(tmp_path):
    state_path = tmp_path / "state.json"
    # Item must be in_progress for recording evidence
    write_state(state_path, {
        "job_name": "sample-worker",
        "version": 1,
        "project_root": str(tmp_path),
        "plan_paths": ["docs/plans/sample.md"],
        "counts": {"pending": 0, "in_progress": 1, "red_verified": 0, "green_verified": 0, "succeeded": 0, "needs_review": 0, "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0},
        "items": [
            {
                "id": "sample:T1",
                "title": "Sample task",
                "status": "in_progress",
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
                "evidence": [],
            }
        ],
    })
    tools = load_plugin_tools()

    result = tools.stateful_dev_record_red({
        "state": str(state_path),
        "item_id": "sample:T1",
        "command": "pytest tests/test_sample.py -v",
        "result": "FAILED — AssertionError",
    })

    assert result["ok"] is True
    assert result["item_id"] == "sample:T1"
    assert result["gate"] == "red"


def test_plugin_record_red_fails_for_nonexistent_item(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    tools = load_plugin_tools()

    result = tools.stateful_dev_record_red({
        "state": str(state_path),
        "item_id": "nonexistent:T99",
        "command": "pytest",
        "result": "FAILED",
    })

    assert result["ok"] is False
    assert "not found" in result["error"]


def test_plugin_record_green_requires_red(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, {
        "job_name": "sample-worker",
        "version": 1,
        "project_root": str(tmp_path),
        "plan_paths": ["docs/plans/sample.md"],
        "counts": {"pending": 0, "in_progress": 1, "red_verified": 0, "green_verified": 0, "succeeded": 0, "needs_review": 0, "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0},
        "items": [
            {
                "id": "sample:T1",
                "title": "Sample task",
                "status": "in_progress",
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
                "evidence": [],
            }
        ],
    })
    tools = load_plugin_tools()

    result = tools.stateful_dev_record_green({
        "state": str(state_path),
        "item_id": "sample:T1",
        "command": "pytest tests/test_sample.py -v",
        "result": "PASSED",
    })

    assert result["ok"] is False
    assert "RED evidence" in result["error"]


def test_plugin_record_full_suite_uses_cli_evidence_keys(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, {
        "job_name": "sample-worker",
        "version": 1,
        "project_root": str(tmp_path),
        "plan_paths": ["docs/plans/sample.md"],
        "counts": {"pending": 0, "in_progress": 0, "red_verified": 0, "green_verified": 1, "succeeded": 0, "needs_review": 0, "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0},
        "items": [
            {
                "id": "sample:T1",
                "title": "Sample task",
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
                    {"focused_red_command": "pytest red", "focused_red_result": "exit 1"},
                    {"focused_green_command": "pytest green", "focused_green_result": "exit 0"},
                ],
            }
        ],
    })
    tools = load_plugin_tools()

    result = tools.stateful_dev_record_full_suite({
        "state": str(state_path),
        "item_id": "sample:T1",
        "command": "pytest -q",
        "result": "exit 0; passed",
    })

    assert result["ok"] is True
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    evidence = saved["items"][0]["evidence"][-1]
    assert evidence == {
        "full_suite_command": "pytest -q",
        "full_suite_result": "exit 0; passed",
    }


def test_plugin_record_lint_uses_cli_evidence_keys(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    tools = load_plugin_tools()

    result = tools.stateful_dev_record_lint({
        "state": str(state_path),
        "item_id": "sample:T1",
        "command": "ruff check .",
        "result": "exit 0; All checks passed",
    })

    assert result["ok"] is True
    saved = json.loads(state_path.read_text(encoding="utf-8"))
    evidence = saved["items"][0]["evidence"][-1]
    assert evidence == {
        "lint_command": "ruff check .",
        "lint_result": "exit 0; All checks passed",
    }


def test_plugin_lock_recover_schema_does_not_offer_unsupported_force():
    tools = load_plugin_tools()

    assert "force" not in tools.LOCK_RECOVER_SCHEMA


def test_plugin_lock_recover_does_not_force_recover_fresh_lock(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    lock_dir = state_path.parent / "lock"
    lock_dir.mkdir()
    lock_dir.joinpath("metadata.json").write_text(
        json.dumps({"run_id": "fresh", "acquired_at": "2999-01-01T00:00:00+00:00"}),
        encoding="utf-8",
    )
    tools = load_plugin_tools()

    result = tools.stateful_dev_lock_recover({"state": str(state_path), "force": True})

    assert result["ok"] is False
    assert "force" not in result["error"].lower()
    assert lock_dir.exists()


def test_plugin_claim_returns_claimed_item(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    tools = load_plugin_tools()

    result = tools.stateful_dev_claim({
        "state": str(state_path),
        "run_id": "test-run-001",
    })

    assert result["ok"] is True
    assert result["claimed"] is True
    assert result["item"]["id"] == "sample:T1"
    assert result["item"]["status"] == "in_progress"
    assert result["run_id"] == "test-run-001"


def test_plugin_claim_prefers_failed_retryable_before_pending(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(
        state_path,
        {
            "job_name": "sample-worker",
            "version": 1,
            "project_root": str(tmp_path),
            "plan_paths": ["docs/plans/sample.md"],
            "counts": {
                "pending": 1,
                "in_progress": 0,
                "red_verified": 0,
                "green_verified": 0,
                "succeeded": 0,
                "needs_review": 0,
                "blocked": 0,
                "failed_retryable": 1,
                "failed_final": 0,
                "skipped": 0,
            },
            "items": [
                {"id": "sample:T1", "title": "Pending", "status": "pending"},
                {
                    "id": "sample:T2",
                    "title": "Retry",
                    "status": "failed_retryable",
                    "attempts": 1,
                },
            ],
        },
    )
    tools = load_plugin_tools()

    result = tools.stateful_dev_claim({"state": str(state_path), "run_id": "run-1"})

    assert result["ok"] is True
    assert result["item"]["id"] == "sample:T2"


def test_plugin_claim_refuses_hitl_required_without_poll_marker(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["hitl"] = {
        "enabled": True,
        "provider": "poseidon",
        "node_id": "test-node",
        "worker_id": "sample-worker",
        "state_path_hash": "sha256:abc123",
        "poll_policy": "required",
        "active_requests": [],
    }
    state_path.write_text(json.dumps(data), encoding="utf-8")
    tools = load_plugin_tools()

    result = tools.stateful_dev_claim({"state": str(state_path), "run_id": "run-1"})

    assert result["ok"] is False
    assert result["claimed"] is False
    assert "hitl poll required" in result["error"].lower()


def test_plugin_claim_returns_none_when_all_done(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, {
        "job_name": "sample-worker",
        "version": 1,
        "project_root": str(tmp_path),
        "plan_paths": ["docs/plans/sample.md"],
        "counts": {"pending": 0, "in_progress": 0, "red_verified": 0, "green_verified": 0, "succeeded": 1, "needs_review": 0, "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0},
        "items": [
            {
                "id": "sample:T1",
                "title": "Sample task",
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
                "evidence": [],
            }
        ],
    })
    tools = load_plugin_tools()

    result = tools.stateful_dev_claim({
        "state": str(state_path),
        "run_id": "test-run-001",
    })

    assert result["ok"] is True
    assert result["claimed"] is False
    assert result["item"] is None


def test_plugin_lock_status_none_held(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path)
    tools = load_plugin_tools()

    result = tools.stateful_dev_lock_status({"state": str(state_path)})

    assert result["locked"] is False
    assert result["stale"] is False


def test_plugin_complete_audit(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, {
        "job_name": "sample-worker",
        "version": 1,
        "project_root": str(tmp_path),
        "plan_paths": ["docs/plans/sample.md"],
        "counts": {"pending": 0, "in_progress": 0, "red_verified": 0, "green_verified": 0, "succeeded": 1, "needs_review": 0, "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0},
        "items": [
            {
                "id": "sample:T1",
                "title": "Sample task",
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
                "evidence": [],
            }
        ],
    })
    tools = load_plugin_tools()

    result = tools.stateful_dev_complete({"state": str(state_path)})

    assert result["shutdown_approved"] is True
    assert result["doctor_ok"] is True
    assert result["lock_clear"] is True
    assert result["active_count"] == 0
    assert result["active_or_retryable_count"] == 0


def test_plugin_handoff_renders_text(tmp_path):
    state_path = tmp_path / "state.json"
    write_state(state_path, {
        "job_name": "sample-worker",
        "version": 1,
        "project_root": str(tmp_path),
        "plan_paths": ["docs/plans/sample.md"],
        "counts": {"pending": 0, "in_progress": 0, "red_verified": 0, "green_verified": 0, "succeeded": 0, "needs_review": 1, "blocked": 0, "failed_retryable": 0, "failed_final": 0, "skipped": 0},
        "items": [
            {
                "id": "sample:T1",
                "title": "Sample task",
                "status": "needs_review",
                "attempts": 1,
                "max_attempts": 3,
                "red_verified": True,
                "green_verified": False,
                "full_suite_verified": False,
                "files_touched": [],
                "test_commands": [],
                "commit_sha": None,
                "needs_operator": True,
                "result": "stuck on design decision",
                "evidence": [],
            }
        ],
    })
    tools = load_plugin_tools()

    result = tools.stateful_dev_handoff({
        "job_name": "sample-worker",
        "question": "Should we use approach A or B?",
        "why": "Both approaches have tradeoffs around complexity and performance.",
        "recommended_answer": "Approach B for now, revisit if complexity becomes a problem.",
        "allowed_next_action": "approve_A | approve_B | defer",
        "project_root": str(tmp_path),
        "plan_path": "docs/plans/sample.md",
        "state_path": str(state_path),
        "item_id": "sample:T1",
        "title": "Sample task",
        "status": "needs_review",
        "evidence": [],
    })

    assert result["ok"] is True
    assert "text" in result
    assert len(result["text"]) > 0
