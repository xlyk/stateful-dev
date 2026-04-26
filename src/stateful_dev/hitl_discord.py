from __future__ import annotations

from typing import Any

from stateful_dev.hitl_models import HITLRequest, OperatorEvent, ValidationError

_BUTTONS: dict[str, tuple[str, str]] = {
    "approve_recommendation": ("Use recommendation", "primary"),
    "use_recommendation": ("Use recommendation", "primary"),
    "answer": ("Answer", "secondary"),
    "approve": ("Approve", "success"),
    "deny": ("Deny", "danger"),
    "defer": ("Defer", "secondary"),
    "stop_worker": ("Stop worker", "danger"),
}


def operator_event_from_discord_interaction(
    interaction: dict[str, Any], request: HITLRequest
) -> OperatorEvent:
    """Normalize a Discord interaction payload into an OperatorEvent."""
    interaction_id = _require_nested_string(interaction, "id")
    actor_id = _require_nested_string(interaction, "user", "id")
    custom_id = _require_nested_string(interaction, "data", "custom_id")
    request_id, action = _parse_custom_id(custom_id)
    if request_id != request.request_id:
        raise ValidationError(f"Discord interaction request mismatch: {request_id}")
    if action not in request.allowed_actions:
        raise ValidationError(f"unsupported Discord HITL action: {action}")

    return OperatorEvent(
        event_id=f"discord:{interaction_id}",
        request_id=request.request_id,
        event_type=action,
        status="pending",
        actor_discord_id=actor_id,
        node=request.node,
        worker=request.worker,
        item_id=request.item_id,
        state_path_hash=request.state_path_hash,
        payload={
            "action": action,
            "interaction_id": interaction_id,
            "modal_fields": _modal_fields(interaction.get("data", {})),
        },
        constraints=list(request.constraints),
        created_at=_require_nested_string(interaction, "created_at"),
        consumed_at=None,
    )


def render_hitl_request_card(request: HITLRequest) -> dict[str, Any]:
    """Render a deterministic Discord card payload for a HITL request."""
    recommendation = str(
        request.payload.get("recommended_answer", "No recommendation provided.")
    )
    risk = request.payload.get("risk")
    risk_lines = []
    if risk:
        risk_lines.append(str(risk))
    risk_lines.extend(request.constraints)

    return {
        "content": f"Stateful worker needs operator input: {request.worker}",
        "embeds": [
            {
                "title": f"HITL {request.request_type} for {request.project}",
                "description": request.question,
                "color": 15158332,
                "fields": [
                    {"name": "Worker", "value": request.worker, "inline": True},
                    {"name": "Project", "value": request.project, "inline": True},
                    {"name": "Item", "value": request.item_id, "inline": False},
                    {
                        "name": "Recommendation",
                        "value": recommendation,
                        "inline": False,
                    },
                    {
                        "name": "Risk / constraints",
                        "value": "\n".join(risk_lines) if risk_lines else "None",
                        "inline": False,
                    },
                    {"name": "State", "value": request.state_path, "inline": False},
                ],
                "footer": {
                    "text": (
                        "Fallback handoff available for request "
                        f"{request.request_id}"
                    )
                },
            }
        ],
        "components": [_action_row(request)],
        "metadata": {
            "request_id": request.request_id,
            "worker": request.worker,
            "node": request.node,
            "item_id": request.item_id,
            "state_path_hash": request.state_path_hash,
            "allowed_actions": list(request.allowed_actions),
            "fallback_available": bool(request.fallback_context),
        },
    }


def _action_row(request: HITLRequest) -> dict[str, Any]:
    return {
        "type": "action_row",
        "components": [
            _button(request.request_id, action)
            for action in request.allowed_actions
            if action in _BUTTONS
        ],
    }


def _require_nested_string(data: dict[str, Any], *path: str) -> str:
    value: Any = data
    field_path = ".".join(path)
    for name in path:
        if not isinstance(value, dict) or name not in value:
            raise ValidationError(f"missing Discord interaction field: {field_path}")
        value = value[name]
    if not isinstance(value, str) or not value:
        raise ValidationError(
            f"Discord interaction field must be a string: {field_path}"
        )
    return value


def _parse_custom_id(custom_id: str) -> tuple[str, str]:
    parts = custom_id.split(":", 2)
    if len(parts) != 3 or parts[0] != "hitl" or not parts[1] or not parts[2]:
        raise ValidationError("invalid Discord HITL custom_id")
    return parts[1], parts[2]


def _modal_fields(data: dict[str, Any]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for component in data.get("components", []):
        if not isinstance(component, dict):
            continue
        for child in component.get("components", []):
            if not isinstance(child, dict):
                continue
            custom_id = child.get("custom_id")
            value = child.get("value")
            if isinstance(custom_id, str) and isinstance(value, str):
                fields[custom_id] = value
    return fields


def _button(request_id: str, action: str) -> dict[str, str]:
    label, style = _BUTTONS[action]
    return {
        "type": "button",
        "custom_id": f"hitl:{request_id}:{action}",
        "label": label,
        "style": style,
    }
