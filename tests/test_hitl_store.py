import sqlite3

import pytest

from stateful_dev.hitl_models import HITLRequest, OperatorEvent
from stateful_dev.hitl_store import (
    consume_event,
    get_request,
    init_store,
    list_open_requests,
    list_pending_events,
    put_operator_event,
    put_request,
)


def test_init_store_creates_request_and_event_tables(tmp_path):
    db_path = tmp_path / "operator-inbox.sqlite3"

    init_store(db_path)

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "hitl_requests",
        "operator_events",
        "discord_messages",
        "audit_log",
    } <= table_names


def make_request(request_id: str = "hitl_1", status: str = "open") -> HITLRequest:
    return HITLRequest(
        request_id=request_id,
        worker="stateful-dev-worker",
        node="mini.lan",
        project="stateful-dev",
        project_root="/Users/xlyk/Code/stateful-dev",
        state_path="/Users/xlyk/Code/stateful-dev/.agent-state/stateful-dev-worker/state.json",
        state_path_hash="sha256:abc123",
        plan_path="docs/plans/poseidon.md",
        item_id="poseidon:T1",
        request_type="clarification",
        status=status,
        question="Continue with the recommended fix?",
        allowed_actions=["approve_recommendation", "deny"],
        constraints=["do not push"],
        payload={"allowed_next_action": "resume item"},
        fallback_context="Fresh agent handoff",
        created_at="2026-04-26T20:00:00Z",
        expires_at="2026-04-26T21:00:00Z",
    )


def test_store_and_load_hitl_request(tmp_path):
    db_path = tmp_path / "operator-inbox.sqlite3"
    request = make_request()

    init_store(db_path)
    put_request(db_path, request)

    loaded = get_request(db_path, "hitl_1")
    assert loaded == request
    assert list_open_requests(db_path) == [request]

    put_request(db_path, request)
    changed_payload = HITLRequest.from_dict(
        {**request.to_dict(), "question": "Different?"}
    )
    with pytest.raises(ValueError, match="duplicate request_id"):
        put_request(db_path, changed_payload)


def make_event(event_id: str = "opevt_1", status: str = "pending") -> OperatorEvent:
    return OperatorEvent(
        event_id=event_id,
        request_id="hitl_1",
        event_type="approve_recommendation",
        status=status,
        actor_discord_id="discord-user-1",
        node="mini.lan",
        worker="stateful-dev-worker",
        item_id="poseidon:T1",
        state_path_hash="sha256:abc123",
        payload={"answer": "approved"},
        constraints=["do not push"],
        created_at="2026-04-26T20:05:00Z",
        consumed_at=None,
    )


def test_operator_event_can_be_consumed_once(tmp_path):
    db_path = tmp_path / "operator-inbox.sqlite3"
    request = make_request()
    event = make_event()

    init_store(db_path)
    put_request(db_path, request)
    put_operator_event(db_path, event)

    assert list_pending_events(db_path, node="mini.lan") == [event]
    assert list_pending_events(db_path, node="other.lan") == []
    assert list_pending_events(db_path, node="mini.lan", worker="other-worker") == []
    assert list_pending_events(db_path, node="mini.lan", request_id="other") == []

    consumed = consume_event(
        db_path,
        event_id="opevt_1",
        node="mini.lan",
        consumed_at="2026-04-26T20:06:00Z",
    )

    assert consumed == OperatorEvent.from_dict(
        {
            **event.to_dict(),
            "status": "consumed",
            "consumed_at": "2026-04-26T20:06:00Z",
        }
    )
    assert list_pending_events(db_path, node="mini.lan") == []
    assert consume_event(db_path, event_id="opevt_1", node="mini.lan") is None
    assert consume_event(db_path, event_id="opevt_1", node="other.lan") is None
