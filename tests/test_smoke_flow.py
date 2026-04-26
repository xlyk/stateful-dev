import json
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app

ROOT = Path(__file__).resolve().parents[1]


def test_disposable_state_flow(tmp_path: Path) -> None:
    runner = CliRunner()
    plan = ROOT / "tests" / "fixtures" / "sample-plan.md"
    state_path = tmp_path / "demo-state.json"

    init_result = runner.invoke(
        app,
        [
            "init",
            "--plan",
            str(plan),
            "--state",
            str(state_path),
            "--job-name",
            "demo-worker",
            "--project-root",
            str(tmp_path),
            "--json",
        ],
    )

    assert init_result.exit_code == 0, init_result.output
    init_payload = json.loads(init_result.output)
    item_id = init_payload["items"][0]["id"]
    assert state_path.exists()
    assert init_payload["counts"]["pending"] == 1

    doctor_result = runner.invoke(app, ["doctor", "--state", str(state_path), "--json"])

    assert doctor_result.exit_code == 0, doctor_result.output
    assert json.loads(doctor_result.output)["ok"] is True

    runner.invoke(
        app,
        [
            "transition",
            "--state",
            str(state_path),
            "--item-id",
            item_id,
            "--status",
            "in_progress",
        ],
    )
    red_result = runner.invoke(
        app,
        [
            "transition",
            "--state",
            str(state_path),
            "--item-id",
            item_id,
            "--status",
            "red_verified",
            "--evidence-json",
            json.dumps(
                {
                    "focused_red_command": (
                        "uv run pytest "
                        "tests/test_smoke_flow.py::test_disposable_state_flow -q"
                    ),
                    "focused_red_result": "exit 1; expected missing composed flow",
                }
            ),
        ],
    )
    green_result = runner.invoke(
        app,
        [
            "transition",
            "--state",
            str(state_path),
            "--item-id",
            item_id,
            "--status",
            "green_verified",
            "--evidence-json",
            json.dumps(
                {
                    "focused_green_command": (
                        "uv run pytest "
                        "tests/test_smoke_flow.py::test_disposable_state_flow -q"
                    ),
                    "focused_green_result": "exit 0; 1 passed",
                }
            ),
        ],
    )
    succeeded_result = runner.invoke(
        app,
        [
            "transition",
            "--state",
            str(state_path),
            "--item-id",
            item_id,
            "--status",
            "succeeded",
            "--evidence-json",
            json.dumps(
                {
                    "full_suite_command": "uv run pytest -q",
                    "full_suite_result": "exit 0; smoke fixture passed",
                }
            ),
        ],
    )

    assert red_result.exit_code == 0, red_result.output
    assert green_result.exit_code == 0, green_result.output
    assert succeeded_result.exit_code == 0, succeeded_result.output

    summary_path = tmp_path / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "plan": str(plan),
                "processed": [
                    {
                        "id": item_id,
                        "title": "Prove disposable flow",
                        "status": "succeeded",
                        "commit_sha": "no commit",
                    }
                ],
                "gates": {"focused": "pass", "full suite": "pass", "lint": "not run"},
                "state_path": str(state_path),
                "next_action": "complete",
            }
        ),
        encoding="utf-8",
    )
    report_result = runner.invoke(
        app, ["report", "--state", str(state_path), "--summary", str(summary_path)]
    )

    assert report_result.exit_code == 0, report_result.output
    assert "demo-worker development batch" in report_result.output
    assert "Succeeded: 1" in report_result.output
    assert f"State: {state_path}" in report_result.output
    assert "Next: complete" in report_result.output
