from stateful_dev.hitl_api import create_request_handler
from stateful_dev.hitl_store import get_request


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
