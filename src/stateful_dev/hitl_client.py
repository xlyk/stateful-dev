from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from stateful_dev.hitl_models import HITLRequest, OperatorEvent

Transport = Callable[[dict[str, Any]], dict[str, Any]]


class PoseidonHitlClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class PoseidonHitlClient:
    base_url: str
    node_token: str
    transport: Transport | None = None
    timeout_seconds: int = 30

    def create_request(self, request: HITLRequest) -> str:
        response = self._send(
            "POST",
            "/hitl/requests",
            json_body=request.to_dict(),
        )
        request_id = response.get("request_id")
        if not isinstance(request_id, str):
            raise PoseidonHitlClientError("Poseidon response missing request_id")
        return request_id

    def pending_events(
        self,
        *,
        worker: str | None = None,
        request_id: str | None = None,
    ) -> list[OperatorEvent]:
        query = {
            name: value
            for name, value in {"worker": worker, "request_id": request_id}.items()
            if value is not None
        }
        path = "/hitl/events"
        if query:
            path = f"{path}?{urlencode(query)}"
        response = self._send("GET", path)
        events = response.get("events", [])
        if not isinstance(events, list):
            raise PoseidonHitlClientError("Poseidon response events must be a list")
        return [OperatorEvent.from_dict(event) for event in events]

    def consume_event(self, event_id: str) -> OperatorEvent:
        response = self._send("POST", f"/hitl/events/{event_id}/consume")
        event = response.get("event")
        if not isinstance(event, dict):
            raise PoseidonHitlClientError("Poseidon response missing event")
        return OperatorEvent.from_dict(event)

    def health(self) -> dict[str, Any]:
        return self._send("GET", "/health")

    def _send(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request = {
            "method": method,
            "url": f"{self.base_url.rstrip('/')}{path}",
            "headers": {"Authorization": f"Bearer {self.node_token}"},
            "json": json_body,
            "timeout_seconds": self.timeout_seconds,
        }
        raw_response = (self.transport or _stdlib_transport)(request)
        return _validated_body(raw_response)


def _validated_body(response: dict[str, Any]) -> dict[str, Any]:
    status = response.get("status")
    body = response.get("body")
    if not isinstance(status, int):
        raise PoseidonHitlClientError("Poseidon response missing status")
    if not isinstance(body, dict):
        raise PoseidonHitlClientError("Poseidon response body must be an object")
    if status >= 400 or body.get("ok") is False:
        error = body.get("error", "request failed")
        raise PoseidonHitlClientError(f"Poseidon request failed: {status} {error}")
    return body


def _stdlib_transport(request: dict[str, Any]) -> dict[str, Any]:
    data = None
    headers = dict(request["headers"])
    if request["json"] is not None:
        data = json.dumps(request["json"]).encode("utf-8")
        headers["Content-Type"] = "application/json"
    http_request = Request(
        request["url"],
        data=data,
        headers=headers,
        method=request["method"],
    )
    with urlopen(http_request, timeout=request["timeout_seconds"]) as response:
        payload = response.read().decode("utf-8")
        body = json.loads(payload) if payload else {}
        return {"status": response.status, "body": body}
