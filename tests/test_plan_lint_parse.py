"""Tests for plan lint, plan parse, and state sync-plans commands (T18)."""
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app

runner = CliRunner()

# Minimal valid state JSON used across tests
_MIN_STATE = (
    '{"job_name":"test","version":1,"project_root":"/tmp","plan_paths":[],'
    '"counts":{"pending":0,"in_progress":0,"red_verified":0,"green_verified":0,'
    '"succeeded":0,"needs_review":0,"blocked":0,"failed_retryable":0,'
    '"failed_final":0,"skipped":0},"items":[]}'
)


def test_plan_lint_command_exists(tmp_path: Path):
    """RED: plan lint command does not exist."""
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\n## Task 1: Foo\n\nBody.\n", encoding="utf-8")
    result = runner.invoke(app, ["plan", "lint", "--plan", str(plan)])
    assert result.exit_code != 2, (  # noqa: E501
        f"Expected command to exist, got exit {result.exit_code}"
    )


def test_plan_parse_command_exists(tmp_path: Path):
    """RED: plan parse command does not exist."""
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\n## Task 1: Foo\n\nBody.\n", encoding="utf-8")
    result = runner.invoke(app, ["plan", "parse", "--plan", str(plan)])
    assert result.exit_code != 2, (  # noqa: E501
        f"Expected command to exist, got exit {result.exit_code}"
    )


def test_sync_plans_command_exists(tmp_path: Path):
    """RED: state sync-plans command does not exist."""
    state = tmp_path / "state.json"
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\n## Task 1: Foo\n\nBody.\n", encoding="utf-8")
    state.write_text(_MIN_STATE, encoding="utf-8")
    result = runner.invoke(  # noqa: E501
        app, ["state", "sync-plans", "--state", str(state), "--plan", str(plan)]
    )
    assert result.exit_code != 2, (  # noqa: E501
        f"Expected command to exist, got exit {result.exit_code}"
    )


def test_plan_lint_detects_missing_task_headings(tmp_path: Path):
    """GREEN: plan lint detects plan with no task headings and exits non-zero."""
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\nNo tasks here.\n", encoding="utf-8")
    result = runner.invoke(app, ["plan", "lint", "--plan", str(plan)])
    assert result.exit_code == 1, (  # noqa: E501
        f"Expected lint to fail for empty plan, got exit {result.exit_code}"
    )
    assert "no task" in result.output.lower() or "missing" in result.output.lower()


def test_plan_lint_reports_clean_plan(tmp_path: Path):
    """GREEN: plan lint reports clean plan with valid task headings."""
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\n## Task 1: Do the thing\n\nBody.\n", encoding="utf-8")
    result = runner.invoke(app, ["plan", "lint", "--plan", str(plan), "--json"])
    assert result.exit_code == 0
    payload = result.output.strip()
    assert '"ok":true' in payload or "ok" in payload


def test_plan_parse_emits_json(tmp_path: Path):
    """GREEN: plan parse emits structured JSON for tasks."""
    plan = tmp_path / "plan.md"
    plan_text = (
        "# Plan\n\n## Task 1: Do the thing\n\nBody.\n\n"
        "## Task 2: Another\n\nBody two.\n"
    )
    plan.write_text(plan_text, encoding="utf-8")
    result = runner.invoke(app, ["plan", "parse", "--plan", str(plan), "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert "tasks" in data
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["number"] == 1
    assert data["tasks"][0]["title"] == "Do the thing"


def test_sync_plans_adds_missing_items(tmp_path: Path):
    """GREEN: sync-plans adds missing items from plan to state without duplicates."""
    state_path = tmp_path / "state.json"
    plan = tmp_path / "plan.md"
    plan_text = (
        "# Plan\n\n## Task 1: Foo\n\nBody.\n\n"
        "## Task 2: Bar\n\nBody.\n"
    )
    plan.write_text(plan_text, encoding="utf-8")
    state_path.write_text(_MIN_STATE, encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "state",
            "sync-plans",
            "--state",
            str(state_path),
            "--plan",
            str(plan),
            "--json",
        ],
    )
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["added"] == 2
    assert len(data["items"]) == 2
    ids = [item["id"] for item in data["items"]]
    assert any("T1-foo" in i for i in ids), f"expected T1-foo in {ids}"
    assert any("T2-bar" in i for i in ids), f"expected T2-bar in {ids}"


def test_sync_plans_detects_duplicate_generated_ids(tmp_path: Path):
    """GREEN: sync-plans detects duplicate item IDs generated from plan tasks."""
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n\n## Task 1: Foo\n\nBody.\n", encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(_MIN_STATE, encoding="utf-8")
    # Run once
    runner.invoke(
        app,
        [
            "state",
            "sync-plans",
            "--state",
            str(state_path),
            "--plan",
            str(plan),
        ],
    )
    # Run again - should not duplicate
    result = runner.invoke(
        app,
        [
            "state",
            "sync-plans",
            "--state",
            str(state_path),
            "--plan",
            str(plan),
            "--json",
        ],
    )
    import json

    data = json.loads(result.output)
    assert data["added"] == 0, "Should not add duplicate items on second sync"
