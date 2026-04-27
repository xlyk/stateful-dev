import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pytest_local_wrapper_marker_is_registered() -> None:
    """Opt-in live wrapper tests must not emit unknown-marker warnings."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    markers = (
        pyproject.get("tool", {})
        .get("pytest", {})
        .get("ini_options", {})
        .get("markers", [])
    )
    assert any(marker.startswith("local_wrapper:") for marker in markers)


def test_cron_gate_contract_doc_exists_and_defines_required_fields() -> None:
    """The cron-gate contract must exist and define all required wake/skip fields."""
    contract_path = ROOT / "docs" / "cron-gate-contract.md"
    content = contract_path.read_text()

    required_fields = [
        "wakeAgent",
        "mode",
        "worker_id",
        "run_id",
        "project_root",
        "state_path",
        "item_id",
        "item_title",
        "item_status",
        "blocker",
        "complete",
    ]
    missing = [f for f in required_fields if f not in content]
    assert missing == [], f"contract missing fields: {missing}"

    # Must document last-line JSON rule
    last_line_ok = (
        "last non-empty stdout line" in content.lower()
        or "last-line" in content.lower()
    )
    assert last_line_ok
    # Must document nonzero exit semantics
    assert "nonzero" in content.lower() and "exit" in content.lower()
    # Must document blocker vs script-bug behavior
    assert "blocker" in content.lower() and "script" in content.lower()
    assert "current hermes has no built-in mode" in content.lower()
    assert "exit nonzero" in content.lower()
    assert "script error" in content.lower()
    assert "No | No (delivery sent)" not in content

    # Must have example payloads for wake, skip, and blocker
    import json
    import re

    # Extract JSON objects from inside triple-backtick blocks, skipping language tags
    sections = content.split("```")
    payloads = []
    for section in sections[1:]:  # skip content before first ```
        lines = section.strip().splitlines()
        # Skip first line if it's a language tag (e.g., "json")
        start = 1 if lines and re.match(r"^[a-z]+$", lines[0].strip()) else 0
        joined = "\n".join(lines[start:])
        if joined.strip().startswith("{"):
            payloads.append(joined.strip())

    msg = (
        f"contract must contain at least 3 example JSON payloads, got {len(payloads)}"
    )
    assert len(payloads) >= 3, msg

    for payload_str in payloads:
        try:
            json.loads(payload_str)
        except json.JSONDecodeError as err:
            raise AssertionError(
                f"invalid JSON in contract examples:\n{payload_str[:200]}"
            ) from err


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


def test_cron_gate_runbook_exists_and_has_required_sections() -> None:
    """The cron-gate runbook must exist and cover all required operational topics."""
    runbook_path = ROOT / "docs" / "cron-gate.md"
    missing_msg = (
        "runbook not found. Create docs/cron-gate.md covering: "
        "architecture, wrapper examples, cron job config, "
        "wake/skip contract, failure modes, smoke tests, migration."
    )
    assert runbook_path.exists(), f"runbook not found at {runbook_path}. {missing_msg}"
    content = runbook_path.read_text()

    required_sections = [
        ("architecture", ["architecture"]),
        ("wrapper examples", ["wrapper", "script"]),
        ("cron job config", ["cron", "hermes"]),
        ("wake/skip contract", ["wakeagent", "wake", "skip"]),
        ("failure modes", ["failure", "blocker", "error"]),
        ("local smoke tests", ["smoke", "test"]),
        ("migration steps", ["migration", "migrate"]),
    ]

    missing = []
    for label, keywords in required_sections:
        if not any(kw.lower() in content.lower() for kw in keywords):
            missing.append(label)

    assert missing == [], f"runbook missing required sections: {missing}"


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
