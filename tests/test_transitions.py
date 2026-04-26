import pytest

from stateful_dev.transitions import IllegalTransitionError, transition_item


def test_pending_cannot_jump_to_succeeded():
    state = {
        "items": [
            {
                "id": "plan:T1-one",
                "status": "pending",
            }
        ],
        "counts": {
            "pending": 1,
            "in_progress": 0,
            "red_verified": 0,
            "green_verified": 0,
            "succeeded": 0,
            "failed_retryable": 0,
            "failed_final": 0,
            "needs_review": 0,
            "blocked": 0,
            "skipped": 0,
        },
    }

    with pytest.raises(IllegalTransitionError, match="pending -> succeeded"):
        transition_item(state, "plan:T1-one", "succeeded")

    assert state["items"][0]["status"] == "pending"
