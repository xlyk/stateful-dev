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


def write_state(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "job_name": "sample-worker",
                "version": 1,
                "project_root": str(path.parent),
                "plan_paths": ["docs/plans/sample.md"],
                "counts": {"pending": 1},
                "items": [
                    {
                        "id": "sample:T1",
                        "title": "Sample task",
                        "status": "pending",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


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
