import json
from pathlib import Path
from typing import Any

from stateful_dev.reports import render_batch_report
from stateful_dev.state import validate_state

DOCTOR_SCHEMA = {"state": "path"}
REPORT_SCHEMA = {"state": "path", "run_summary": "object"}


def _read_state(state_path: Path) -> dict[str, Any]:
    return json.loads(state_path.read_text(encoding="utf-8"))


def stateful_dev_doctor(payload: dict[str, str]) -> dict[str, object]:
    state_path = Path(payload["state"])
    result = validate_state(_read_state(state_path))
    return {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
        "counts": result.counts,
    }


def stateful_dev_report(payload: dict[str, Any]) -> dict[str, str]:
    state_path = Path(payload["state"])
    run_summary = payload.get("run_summary", {})
    if not isinstance(run_summary, dict):
        run_summary = {}
    return {"text": render_batch_report(_read_state(state_path), run_summary)}


def register(ctx) -> None:
    ctx.tool(
        "stateful_dev_doctor",
        stateful_dev_doctor,
        schema=DOCTOR_SCHEMA,
        description="Validate a durable worker state file.",
    )
    ctx.tool(
        "stateful_dev_report",
        stateful_dev_report,
        schema=REPORT_SCHEMA,
        description="Render a compact stateful development batch report.",
    )
