from __future__ import annotations

from typing import Any

from stateful_dev.hitl_models import HITLRequest

_BUTTONS: dict[str, tuple[str, str]] = {
    "approve_recommendation": ("Use recommendation", "primary"),
    "use_recommendation": ("Use recommendation", "primary"),
    "answer": ("Answer", "secondary"),
    "approve": ("Approve", "success"),
    "deny": ("Deny", "danger"),
    "defer": ("Defer", "secondary"),
    "stop_worker": ("Stop worker", "danger"),
}


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


def _button(request_id: str, action: str) -> dict[str, str]:
    label, style = _BUTTONS[action]
    return {
        "type": "button",
        "custom_id": f"hitl:{request_id}:{action}",
        "label": label,
        "style": style,
    }
