import sqlite3

import pytest

from stateful_dev.hitl_models import HITLRequest, OperatorEvent
from stateful_dev.hitl_store import (
    cancel_request,
    consume_event,
    expire_request,
    get_audit_records,
    get_discord_message,
    get_request,
    init_store,
    list_open_requests,
    list_pending_events,
    put_discord_message,
    put_operator_event,
    put_request,
    update_discord_message_status,
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


def make_request(
    request_id: str = "hitl_1",
    status: str = "open",
    expires_at: str = "2026-04-26T21:00:00Z",
) -> HITLRequest:
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
        expires_at=expires_at,
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


def test_expired_request_does_not_return_pending_events(tmp_path):
    db_path = tmp_path / "operator-inbox.sqlite3"
    request = make_request(expires_at="2026-04-26T20:00:00Z")
    event = make_event()

    init_store(db_path)
    put_request(db_path, request)
    put_operator_event(db_path, event)

    assert list_pending_events(db_path, node="mini.lan") == [event]

    expired = expire_request(
        db_path,
        request_id="hitl_1",
        expired_at="2026-04-26T20:01:00Z",
    )

    assert expired == HITLRequest.from_dict({**request.to_dict(), "status": "expired"})
    assert get_request(db_path, "hitl_1") == expired
    assert list_open_requests(db_path) == []
    assert list_pending_events(db_path, node="mini.lan") == []

    cancelled = cancel_request(
        db_path,
        request_id="hitl_1",
        cancelled_at="2026-04-26T20:02:00Z",
    )
    assert cancelled is None

    audit_actions = [record["action"] for record in get_audit_records(db_path)]
    assert audit_actions == ["request_created", "event_created", "request_expired"]


def test_discord_message_metadata_round_trips(tmp_path):
    db_path = tmp_path / "operator-inbox.sqlite3"
    request = make_request()

    init_store(db_path)
    put_request(db_path, request)
    put_discord_message(
        db_path,
        channel_id="channel-1",
        message_id="message-1",
        request_id="hitl_1",
        render_version=2,
        card_status="posted",
        created_at="2026-04-26T20:10:00Z",
    )

    assert get_discord_message(db_path, message_id="message-1") == {
        "channel_id": "channel-1",
        "message_id": "message-1",
        "request_id": "hitl_1",
        "render_version": 2,
        "card_status": "posted",
        "created_at": "2026-04-26T20:10:00Z",
        "updated_at": None,
    }

    updated = update_discord_message_status(
        db_path,
        message_id="message-1",
        card_status="consumed",
        updated_at="2026-04-26T20:11:00Z",
    )

    assert updated == {
        "channel_id": "channel-1",
        "message_id": "message-1",
        "request_id": "hitl_1",
        "render_version": 2,
        "card_status": "consumed",
        "created_at": "2026-04-26T20:10:00Z",
        "updated_at": "2026-04-26T20:11:00Z",
    }
    assert get_discord_message(db_path, message_id="missing") is None
    assert update_discord_message_status(
        db_path,
        message_id="missing",
        card_status="consumed",
    ) is None

    audit_actions = [record["action"] for record in get_audit_records(db_path)]
    assert audit_actions == [
        "request_created",
        "discord_message_recorded",
        "discord_message_status_updated",
    ]
