from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_usage_docs_include_install_and_smoke_commands() -> None:
    usage = (ROOT / "docs" / "usage.md").read_text()
    readme = (ROOT / "README.md").read_text()

    required_snippets = [
        "uv tool install",
        "hermes tools enable",
        "stateful-dev doctor",
        "uv run stateful-dev --help",
        "disposable smoke flow",
    ]

    for snippet in required_snippets:
        assert snippet in usage

    assert "docs/usage.md" in readme
    assert "stateful-dev doctor" in readme
