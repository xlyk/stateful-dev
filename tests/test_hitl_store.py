import sqlite3

import pytest

from stateful_dev.hitl_models import HITLRequest
from stateful_dev.hitl_store import (
    get_request,
    init_store,
    list_open_requests,
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
