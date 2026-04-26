import json
from pathlib import Path

from typer.testing import CliRunner

from stateful_dev.cli import app
from stateful_dev.locking import acquire_lock, release_lock

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "tests" / "fixtures" / "sample-plan.md"


def test_cli_app_importable():
    assert app is not None


def test_cli_help_runs():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Stateful development worker utilities" in result.output


def test_version_command_prints_version():
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output == "0.1.0\n"


def test_init_refuses_to_overwrite_existing_state_without_force(tmp_path: Path):
    state_path = tmp_path / "state.json"
    state_path.write_text('{"existing": true}\n', encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--plan",
            str(PLAN),
            "--state",
            str(state_path),
            "--job-name",
            "demo-worker",
            "--project-root",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "already exists" in result.output
    assert json.loads(state_path.read_text(encoding="utf-8")) == {"existing": True}


def test_transition_refuses_to_write_when_state_lock_is_held(tmp_path: Path):
    state_path = tmp_path / "state.json"
    init_result = CliRunner().invoke(
        app,
        [
            "init",
            "--plan",
            str(PLAN),
            "--state",
            str(state_path),
            "--job-name",
            "demo-worker",
            "--project-root",
            str(tmp_path),
            "--json",
        ],
    )
    item_id = json.loads(init_result.output)["items"][0]["id"]
    lock = acquire_lock(state_path.parent, run_id="other-run", timeout_minutes=60)

    try:
        result = CliRunner().invoke(
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
    finally:
        release_lock(lock)

    assert result.exit_code == 1
    assert "fresh lock is held by other-run" in result.output
    assert json.loads(state_path.read_text(encoding="utf-8"))["counts"]["pending"] == 1
