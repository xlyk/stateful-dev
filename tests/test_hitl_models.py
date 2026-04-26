import pytest

from stateful_dev.hitl_models import (
    HITLRequest,
    OperatorEvent,
    ValidationError,
    WorkerResume,
)


def test_hitl_request_round_trips_required_fields():
    request = HITLRequest(
        request_id="hitl_123",
        worker="stateful-dev-worker",
        node="mini.lan",
        project="stateful-dev",
        project_root="/Users/xlyk/Code/stateful-dev",
        state_path="/Users/xlyk/Code/stateful-dev/.agent-state/state.json",
        state_path_hash="abc123",
        plan_path="docs/plans/05.md",
        item_id="plan:T1-contracts",
        request_type="clarification",
        status="open",
        question="Should the worker accept this RED exception?",
        allowed_actions=["answer", "approve_recommendation", "stop_worker"],
        constraints=["do not push", "record locally before resume"],
        payload={"recommended_answer": "approve"},
        fallback_context="Fresh agent handoff...",
        created_at="2026-04-26T19:00:00Z",
        expires_at="2026-04-27T19:00:00Z",
    )

    restored_request = HITLRequest.from_dict(request.to_dict())

    assert restored_request == request
    assert restored_request.to_dict()["allowed_actions"] == [
        "answer",
        "approve_recommendation",
        "stop_worker",
    ]

    event = OperatorEvent(
        event_id="opevt_123",
        request_id=request.request_id,
        event_type="answer",
        status="pending",
        actor_discord_id="123456789",
        node=request.node,
        worker=request.worker,
        item_id=request.item_id,
        state_path_hash=request.state_path_hash,
        payload={"answer": "approve"},
        constraints=["dry-run-only"],
        created_at="2026-04-26T19:05:00Z",
        consumed_at=None,
    )

    restored_event = OperatorEvent.from_dict(event.to_dict())

    assert restored_event == event
    assert restored_event.to_dict()["consumed_at"] is None

    resume = WorkerResume(
        request_id=request.request_id,
        event_id=event.event_id,
        worker=request.worker,
        node=request.node,
        item_id=request.item_id,
        state_path_hash=request.state_path_hash,
        allowed_next_action="Record the event locally, then resume the blocked item.",
        constraints=["do not push"],
        payload={"answer": "approve"},
        consumed_at="2026-04-26T19:06:00Z",
    )

    assert WorkerResume.from_dict(resume.to_dict()) == resume

    bad_payload = request.to_dict()
    bad_payload.pop("question")

    with pytest.raises(ValidationError, match="missing required field: question"):
        HITLRequest.from_dict(bad_payload)
