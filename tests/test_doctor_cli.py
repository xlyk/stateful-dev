import json

from typer.testing import CliRunner

from stateful_dev.cli import app


def test_doctor_reports_invalid_state_json(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "job_name": "stateful-dev-worker",
                "version": 1,
                "project_root": str(tmp_path),
                "plan_paths": ["docs/plans/example.md"],
                "counts": {"pending": 2},
                "items": [{"id": "plan:T1-one", "status": "pending"}],
            }
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["doctor", "--state", str(state_path), "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["counts"]["pending"] == 1
    assert "count drift for pending: expected 1, found 2" in payload["errors"]
