from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_usage_docs_include_install_and_smoke_commands() -> None:
    usage = (ROOT / "docs" / "usage.md").read_text()
    readme = (ROOT / "README.md").read_text()

    required_snippets = [
        "uv tool install",
        "hermes tools enable ./plugins/stateful-dev",
        "stateful-dev init --plan /tmp/stateful-dev-smoke/plan.md",
        "stateful-dev doctor --state /tmp/stateful-dev-smoke/state.json --json",
        "stateful-dev transition --state /tmp/stateful-dev-smoke/state.json",
        "stateful-dev report --state /tmp/stateful-dev-smoke/state.json",
        "uv run stateful-dev --help",
        "disposable smoke flow",
        "path-enabled plugin",
    ]

    for snippet in required_snippets:
        assert snippet in usage

    real_state_command = (
        "stateful-dev doctor --state .agent-state/stateful-dev-worker/state.json"
    )
    assert real_state_command not in usage
    assert "docs/usage.md" in readme
    assert "stateful-dev doctor" in readme
    assert (
        "plugin manifest and registered plugin tools are mechanically checked" in readme
    )
