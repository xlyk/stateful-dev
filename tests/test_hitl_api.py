from stateful_dev.hitl_api import create_request_handler, pending_events_handler
from stateful_dev.hitl_auth import hash_node_token, make_node_token_verifier
from stateful_dev.hitl_models import HITLRequest, OperatorEvent
from stateful_dev.hitl_store import (
    get_request,
    init_store,
    put_operator_event,
    put_request,
)


def test_create_request_handler_validates_node_token(tmp_path):
    db_path = tmp_path / "operator-inbox.sqlite3"
    request_payload = {
        "request_id": "hitl_1",
        "worker": "stateful-dev-worker",
        "node": "caller-supplied-node",
        "project": "stateful-dev",
        "project_root": "/Users/xlyk/Code/stateful-dev",
        "state_path": (
            "/Users/xlyk/Code/stateful-dev/.agent-state/"
            "stateful-dev-worker/state.json"
        ),
        "state_path_hash": "sha256:abc123",
        "plan_path": "docs/plans/poseidon.md",
        "item_id": "poseidon:T1",
        "request_type": "clarification",
        "status": "open",
        "question": "Continue with the recommended fix?",
        "allowed_actions": ["approve_recommendation", "deny"],
        "constraints": ["do not push"],
        "payload": {"allowed_next_action": "resume item"},
        "fallback_context": "Fresh agent handoff",
        "created_at": "2026-04-26T20:00:00Z",
        "expires_at": "2026-04-26T21:00:00Z",
    }

    def verify_token(token: str | None) -> str | None:
        if token == "valid-token":
            return "mini.lan"
        return None

    rejected = create_request_handler(
        db_path,
        token=None,
        body=request_payload,
        verify_token=verify_token,
    )
    assert rejected == {
        "status": 401,
        "body": {"ok": False, "error": "invalid node token"},
    }

    accepted = create_request_handler(
        db_path,
        token="valid-token",
        body=request_payload,
        verify_token=verify_token,
    )

    assert accepted == {
        "status": 201,
        "body": {"ok": True, "request_id": "hitl_1", "node": "mini.lan"},
    }
    stored = get_request(db_path, "hitl_1")
    assert stored is not None
    assert stored.node == "mini.lan"


def _request_for_node(request_id: str, node: str) -> HITLRequest:
    return HITLRequest(
        request_id=request_id,
        worker="stateful-dev-worker",
        node=node,
        project="stateful-dev",
        project_root="/Users/xlyk/Code/stateful-dev",
        state_path=(
            "/Users/xlyk/Code/stateful-dev/.agent-state/"
            "stateful-dev-worker/state.json"
        ),
        state_path_hash="sha256:abc123",
        plan_path="docs/plans/poseidon.md",
        item_id="poseidon:T1",
        request_type="clarification",
        status="open",
        question="Continue with the recommended fix?",
        allowed_actions=["approve_recommendation", "deny"],
        constraints=["do not push"],
        payload={"allowed_next_action": "resume item"},
        fallback_context="Fresh agent handoff",
        created_at="2026-04-26T20:00:00Z",
        expires_at="2026-04-26T21:00:00Z",
    )


def _event_for_node(event_id: str, request_id: str, node: str) -> OperatorEvent:
    return OperatorEvent(
        event_id=event_id,
        request_id=request_id,
        event_type="approve_recommendation",
        status="pending",
        actor_discord_id="discord-user-1",
        node=node,
        worker="stateful-dev-worker",
        item_id="poseidon:T1",
        state_path_hash="sha256:abc123",
        payload={"answer": "approved"},
        constraints=["do not push"],
        created_at="2026-04-26T20:05:00Z",
        consumed_at=None,
    )


def test_pending_events_are_scoped_to_authenticated_node(tmp_path):
    db_path = tmp_path / "operator-inbox.sqlite3"
    mini_request = _request_for_node("hitl_mini", "mini.lan")
    builder_request = _request_for_node("hitl_builder", "builder.lan")
    mini_event = _event_for_node("opevt_mini", "hitl_mini", "mini.lan")
    builder_event = _event_for_node("opevt_builder", "hitl_builder", "builder.lan")
    verify_token = make_node_token_verifier(
        {
            "mini.lan": "test-token:mini-token",
            "builder.lan": hash_node_token("builder-token"),
        }
    )

    init_store(db_path)
    put_request(db_path, mini_request)
    put_request(db_path, builder_request)
    put_operator_event(db_path, mini_event)
    put_operator_event(db_path, builder_event)

    rejected = pending_events_handler(
        db_path,
        token="wrong-token",
        verify_token=verify_token,
    )
    assert rejected == {
        "status": 401,
        "body": {"ok": False, "error": "invalid node token"},
    }

    mini_response = pending_events_handler(
        db_path,
        token="mini-token",
        verify_token=verify_token,
    )
    assert mini_response == {
        "status": 200,
        "body": {"ok": True, "node": "mini.lan", "events": [mini_event.to_dict()]},
    }

    builder_response = pending_events_handler(
        db_path,
        token="builder-token",
        verify_token=verify_token,
    )
    assert builder_response == {
        "status": 200,
        "body": {
            "ok": True,
            "node": "builder.lan",
            "events": [builder_event.to_dict()],
        },
    }
