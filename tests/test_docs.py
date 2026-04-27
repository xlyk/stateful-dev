from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docs_and_fixtures_do_not_reference_legacy_cron_skill() -> None:
    checked_paths = [ROOT / "README.md"]
    checked_paths.extend((ROOT / "docs" / "plans").glob("*.md"))
    checked_paths.extend((ROOT / "tests" / "fixtures").glob("*.md"))

    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in checked_paths
        if "stateful-cron-development" in path.read_text()
    ]

    assert offenders == []


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
