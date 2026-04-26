from stateful_dev.hitl_client import PoseidonHitlClient
from stateful_dev.hitl_models import OperatorEvent


def test_client_polls_pending_events_with_node_token():
    event = OperatorEvent(
        event_id="opevt_1",
        request_id="hitl_1",
        event_type="approve_recommendation",
        status="pending",
        actor_discord_id="discord-user-1",
        node="mini.lan",
        worker="stateful-dev-worker",
        item_id="poseidon:T1",
        state_path_hash="sha256:abc123",
        payload={"allowed_next_action": "resume item"},
        constraints=["do not push"],
        created_at="2026-04-26T20:05:00Z",
        consumed_at=None,
    )
    requests = []

    def transport(request):
        requests.append(request)
        return {"status": 200, "body": {"ok": True, "events": [event.to_dict()]}}

    client = PoseidonHitlClient(
        base_url="https://poseidon.example/api",
        node_token="secret-token",
        transport=transport,
        timeout_seconds=7,
    )

    events = client.pending_events(worker="stateful-dev-worker", request_id="hitl_1")

    assert events == [event]
    assert requests == [
        {
            "method": "GET",
            "url": (
                "https://poseidon.example/api/hitl/events?"
                "worker=stateful-dev-worker&request_id=hitl_1"
            ),
            "headers": {"Authorization": "Bearer secret-token"},
            "json": None,
            "timeout_seconds": 7,
        }
    ]
