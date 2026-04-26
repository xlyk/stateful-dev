from typer.testing import CliRunner

from stateful_dev.cli import app


def test_cli_app_importable():
    assert app is not None


def test_cli_help_runs():
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Stateful development worker utilities" in result.output
