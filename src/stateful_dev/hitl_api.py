from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from stateful_dev.hitl_models import HITLRequest, ValidationError
from stateful_dev.hitl_store import consume_event, list_pending_events, put_request

TokenVerifier = Callable[[str | None], str | None]


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {"status": status, "body": body}


def _authenticated_node(token: str | None, verify_token: TokenVerifier) -> str | None:
    return verify_token(token)


def create_request_handler(
    store_path: str | Path,
    *,
    token: str | None,
    body: dict[str, Any],
    verify_token: TokenVerifier,
) -> dict[str, Any]:
    node = _authenticated_node(token, verify_token)
    if node is None:
        return _response(401, {"ok": False, "error": "invalid node token"})

    try:
        request = HITLRequest.from_dict({**body, "node": node})
        put_request(store_path, request)
    except (ValidationError, ValueError) as error:
        return _response(400, {"ok": False, "error": str(error)})

    return _response(
        201,
        {"ok": True, "request_id": request.request_id, "node": request.node},
    )


def pending_events_handler(
    store_path: str | Path,
    *,
    token: str | None,
    worker: str | None = None,
    request_id: str | None = None,
    verify_token: TokenVerifier,
) -> dict[str, Any]:
    node = _authenticated_node(token, verify_token)
    if node is None:
        return _response(401, {"ok": False, "error": "invalid node token"})

    events = list_pending_events(
        store_path,
        node=node,
        worker=worker,
        request_id=request_id,
    )
    return _response(
        200,
        {"ok": True, "node": node, "events": [event.to_dict() for event in events]},
    )


def consume_event_handler(
    store_path: str | Path,
    *,
    token: str | None,
    event_id: str,
    verify_token: TokenVerifier,
) -> dict[str, Any]:
    node = _authenticated_node(token, verify_token)
    if node is None:
        return _response(401, {"ok": False, "error": "invalid node token"})

    event = consume_event(store_path, event_id=event_id, node=node)
    if event is None:
        return _response(404, {"ok": False, "error": "pending event not found"})
    return _response(200, {"ok": True, "node": node, "event": event.to_dict()})
