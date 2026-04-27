"""Poseidon HITL polling for stateful-dev cron-gate integration.

This module provides injectable Poseidon polling without requiring live network.
It is intentionally separate from the CLI to allow unit testing with fake transports.

Usage:
    from stateful_dev.hitl_poseidon import poll_poseidon, validate_event

    events = poll_poseidon(
        base_url="https://poseidon.example.com",
        node_token="secret",
        node_id="my-node",
        worker_id="my-worker",
        state_path_hash="sha256:...",
        active_request_ids=["req-1", "req-2"],
        transport=_FakeTransport(),
    )
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from os import PathLike

# --------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------


@dataclass(frozen=True)
class HITLEvent:
    """A validated HITL event staged for local consumption."""

    event_id: str
    request_id: str
    item_id: str
    event_type: str
    allowed_actions: tuple[str, ...]
    payload: dict[str, Any]
    created_at: str
    expires_at: str | None


@dataclass
class PollResult:
    """Result of a Poseidon poll operation."""

    ok: bool
    events: list[HITLEvent] = field(default_factory=list)
    error: str | None = None
    request_ids_found: list[str] = field(default_factory=list)


@dataclass
class EventValidation:
    """Validation result for a single raw event."""

    valid: bool
    event: HITLEvent | None = None
    error: str | None = None


# --------------------------------------------------------------------
# Transport interface
# --------------------------------------------------------------------


class PoseidonTransport:
    """Live network transport for Poseidon API."""

    def get(
        self, url: str, headers: dict[str, str], timeout: int = 15
    ) -> dict[str, Any] | None:
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError:
            return None

    def post(
        self, url: str, headers: dict[str, str], body: dict[str, Any], timeout: int = 15
    ) -> dict[str, Any] | None:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError:
            return None


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def compute_state_path_hash(state_path: str) -> str:
    """Compute the canonical sha256 state-path hash for HITL routing."""
    return f"sha256:{hashlib.sha256(state_path.encode('utf-8')).hexdigest()[:16]}"


def _parse_rfc3339(value: str | None) -> str | None:
    """Return the string if it looks parseable, else None."""
    if not value:
        return None
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    except ValueError:
        return None


# --------------------------------------------------------------------
# Core validation
# --------------------------------------------------------------------


def validate_event(
    raw: dict[str, Any],
    expected_worker_id: str,
    expected_state_path_hash: str,
    expected_item_id: str | None = None,
) -> EventValidation:
    """Validate a raw Poseidon event against routing constraints.

    Returns EventValidation with valid=True and a HITLEvent if all checks pass.
    Returns EventValidation with valid=False and an error message otherwise.
    """
    # Routing field checks
    event_worker_id = str(raw.get("worker_id", ""))
    event_state_path_hash = str(raw.get("state_path_hash", ""))
    request_id = str(raw.get("request_id", ""))
    item_id = str(raw.get("item_id", ""))

    if event_worker_id != expected_worker_id:
        return EventValidation(
            valid=False,
            error=f"worker_id mismatch: {event_worker_id!r} != {expected_worker_id!r}",
        )
    if event_state_path_hash != expected_state_path_hash:
        return EventValidation(
            valid=False,
            error=(
                f"state_path_hash mismatch: "
                f"{event_state_path_hash!r} != {expected_state_path_hash!r}"
            ),
        )
    if not request_id:
        return EventValidation(
            valid=False,
            error="missing request_id in event",
        )
    if expected_item_id and item_id != expected_item_id:
        return EventValidation(
            valid=False,
            error=f"item_id mismatch: {item_id!r} != {expected_item_id!r}",
        )

    # Content checks
    allowed_actions_raw = raw.get("allowed_actions", [])
    if not isinstance(allowed_actions_raw, list):
        return EventValidation(
            valid=False,
            error="allowed_actions must be a list",
        )
    allowed_actions = tuple(str(a) for a in allowed_actions_raw)

    event_type = str(raw.get("event_type", ""))
    if not event_type:
        return EventValidation(
            valid=False,
            error="missing event_type",
        )

    payload = raw.get("payload", {})
    if not isinstance(payload, dict):
        return EventValidation(
            valid=False,
            error="payload must be an object",
        )

    return EventValidation(
        valid=True,
        event=HITLEvent(
            event_id=str(raw.get("event_id", "")),
            request_id=request_id,
            item_id=item_id,
            event_type=event_type,
            allowed_actions=allowed_actions,
            payload=payload,
            created_at=_parse_rfc3339(str(raw.get("created_at", ""))) or "",
            expires_at=_parse_rfc3339(str(raw.get("expires_at", ""))) or None,
        ),
    )


# --------------------------------------------------------------------
# Polling
# --------------------------------------------------------------------


def poll_poseidon(
    base_url: str,
    node_token: str,
    node_id: str,
    worker_id: str,
    state_path_hash: str,
    active_request_ids: list[str],
    transport: PoseidonTransport | None = None,
    timeout: int = 15,
) -> PollResult:
    """Poll Poseidon for active HITL events matching this worker.

    Args:
        base_url: Poseidon API base URL (e.g. "https://poseidon.example.com")
        node_token: Node authentication token
        node_id: This node's identifier
        worker_id: This worker's stable identifier
        state_path_hash: Canonical hash of the state path for routing
        active_request_ids: Active request IDs to filter by
        transport: Injectable transport for testing; uses live HTTP if None
        timeout: Request timeout in seconds

    Returns:
        PollResult with ok=True and events if poll succeeded (even if 0 events).
        PollResult with ok=False and error if poll failed.
    """
    if not active_request_ids:
        return PollResult(ok=True, events=[], request_ids_found=[])

    if transport is None:
        transport = PoseidonTransport()

    headers = {
        "Authorization": f"Bearer {node_token}",
        "Content-Type": "application/json",
    }

    # Poll each active request ID narrowly
    all_events: list[HITLEvent] = []
    found_request_ids: list[str] = []

    for request_id in active_request_ids:
        url = f"{base_url.rstrip('/')}/v1/nodes/{node_id}/requests/{request_id}/events"
        response = transport.get(url, headers=headers, timeout=timeout)
        if response is None:
            # Network or auth error — fail closed
            return PollResult(
                ok=False,
                error=f"failed to poll request {request_id}: connection error",
            )

        events_raw = response.get("events", []) if isinstance(response, dict) else []
        if not isinstance(events_raw, list):
            events_raw = []

        for raw in events_raw:
            if not isinstance(raw, dict):
                continue
            # Attach routing context from the request-level fields
            enriched = dict(raw)
            enriched.setdefault("worker_id", worker_id)
            enriched.setdefault("state_path_hash", state_path_hash)

            validation = validate_event(
                enriched,
                expected_worker_id=worker_id,
                expected_state_path_hash=state_path_hash,
            )
            if validation.valid and validation.event:
                all_events.append(validation.event)
                if request_id not in found_request_ids:
                    found_request_ids.append(request_id)

    return PollResult(
        ok=True,
        events=all_events,
        request_ids_found=found_request_ids,
    )


# --------------------------------------------------------------------
# Staging
# --------------------------------------------------------------------


def stage_event(
    event: HITLEvent,
    inbox_dir: PathLike,
) -> None:
    """Write a validated HITL event to the local staging inbox.

    The event is written atomically to:
    <inbox_dir>/<request_id>/<event_id>.json

    Args:
        event: Validated HITL event to stage
        inbox_dir: Path to the worker hitl-inbox directory

    Raises:
        OSError: If the directory cannot be created or file written
    """
    request_dir = os.path.join(str(inbox_dir), event.request_id)
    os.makedirs(request_dir, exist_ok=True)
    event_path = os.path.join(request_dir, f"{event.event_id}.json")
    content = json.dumps(
        {
            "event_id": event.event_id,
            "request_id": event.request_id,
            "item_id": event.item_id,
            "event_type": event.event_type,
            "allowed_actions": list(event.allowed_actions),
            "payload": event.payload,
            "created_at": event.created_at,
            "expires_at": event.expires_at,
            "staged_at": datetime.now(UTC).isoformat(),
        },
        indent=2,
    )
    tmp = f"{event_path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, event_path)


# --------------------------------------------------------------------
# HITL enforcement helpers for claim
# --------------------------------------------------------------------


def hitl_enabled(state: dict[str, Any]) -> bool:
    """Return True if HITL is enabled in the state."""
    hitl = state.get("hitl")
    return isinstance(hitl, dict) and hitl.get("enabled") is True


def hitl_poll_ok_for_run(
    state: dict[str, Any],
    run_id: str,
) -> tuple[bool, str]:
    """Check whether the current run has a successful HITL poll marker.

    Returns (True, "") if no HITL is enabled or if the run has a successful marker.
    Returns (False, reason) if HITL is required but marker is absent or failed.
    """
    if not hitl_enabled(state):
        return True, ""

    hitl = state["hitl"]
    poll_policy = hitl.get("poll_policy", "required")
    if poll_policy == "optional":
        return True, ""

    # Look for a run marker with a successful HITL poll
    import os
    state_path = state.get("state_path")
    if not state_path:
        return False, "state_path not set in state"
    state_dir = os.path.dirname(state_path)
    run_marker_path = os.path.join(state_dir, "runs", f"{run_id}.json")
    if not os.path.exists(run_marker_path):
        return False, f"no poll marker for run {run_id}"

    try:
        with open(run_marker_path, encoding="utf-8") as f:
            marker = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False, f"failed to read poll marker for run {run_id}"

    hitl_poll = marker.get("hitl_poll", {})
    if not isinstance(hitl_poll, dict):
        return False, f"hitl_poll missing or invalid in run marker for {run_id}"

    if hitl_poll.get("required") is True and hitl_poll.get("ok") is not True:
        return False, f"hitl_poll.failed=true for run {run_id}"

    return True, ""
