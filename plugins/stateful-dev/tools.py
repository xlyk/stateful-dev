from pathlib import Path

from stateful_dev.state import validate_state

DOCTOR_SCHEMA = {"state": "path"}


def stateful_dev_doctor(payload: dict[str, str]) -> dict[str, object]:
    state_path = Path(payload["state"])
    result = validate_state_json(state_path)
    return {
        "ok": result.ok,
        "errors": result.errors,
        "warnings": result.warnings,
        "counts": result.counts,
    }


def validate_state_json(state_path: Path):
    import json

    data = json.loads(state_path.read_text(encoding="utf-8"))
    return validate_state(data)


def register(ctx) -> None:
    ctx.tool(
        "stateful_dev_doctor",
        stateful_dev_doctor,
        schema=DOCTOR_SCHEMA,
        description="Validate a durable worker state file.",
    )
