import pytest

from stateful_dev.transitions import IllegalTransitionError, transition_item

FOCUSED_TRANSITION_COMMAND = "uv run pytest tests/test_transitions.py -q"


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


def test_green_requires_red_evidence():
    state = {
        "items": [
            {
                "id": "plan:T1-one",
                "status": "red_verified",
            }
        ],
        "counts": {
            "pending": 0,
            "in_progress": 0,
            "red_verified": 1,
            "green_verified": 0,
            "succeeded": 0,
            "failed_retryable": 0,
            "failed_final": 0,
            "needs_review": 0,
            "blocked": 0,
            "skipped": 0,
        },
    }

    with pytest.raises(
        IllegalTransitionError,
        match="green_verified requires RED evidence",
    ):
        transition_item(
            state,
            "plan:T1-one",
            "green_verified",
            evidence={
                "focused_green_command": FOCUSED_TRANSITION_COMMAND,
                "focused_green_result": "1 passed",
            },
        )

    assert state["items"][0]["status"] == "red_verified"


def test_red_evidence_rejects_obvious_success_result():
    state = {
        "items": [
            {
                "id": "plan:T1-one",
                "status": "in_progress",
            }
        ],
        "counts": {
            "pending": 0,
            "in_progress": 1,
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

    with pytest.raises(
        IllegalTransitionError,
        match="RED evidence result appears to be a success",
    ):
        transition_item(
            state,
            "plan:T1-one",
            "red_verified",
            evidence={
                "focused_red_command": FOCUSED_TRANSITION_COMMAND,
                "focused_red_result": "exit 0; 1 passed",
            },
        )


def test_green_evidence_rejects_obvious_failure_result():
    state = {
        "items": [
            {
                "id": "plan:T1-one",
                "status": "red_verified",
                "evidence": [
                    {
                        "focused_red_command": FOCUSED_TRANSITION_COMMAND,
                        "focused_red_result": "exit 1; AssertionError",
                    }
                ],
            }
        ],
        "counts": {
            "pending": 0,
            "in_progress": 0,
            "red_verified": 1,
            "green_verified": 0,
            "succeeded": 0,
            "failed_retryable": 0,
            "failed_final": 0,
            "needs_review": 0,
            "blocked": 0,
            "skipped": 0,
        },
    }

    with pytest.raises(
        IllegalTransitionError,
        match="GREEN evidence result appears to be a failure",
    ):
        transition_item(
            state,
            "plan:T1-one",
            "green_verified",
            evidence={
                "focused_green_command": FOCUSED_TRANSITION_COMMAND,
                "focused_green_result": "exit 1; failed",
            },
        )


def test_full_suite_evidence_rejects_obvious_failure_result():
    state = {
        "items": [
            {
                "id": "plan:T1-one",
                "status": "green_verified",
                "evidence": [
                    {
                        "focused_red_command": FOCUSED_TRANSITION_COMMAND,
                        "focused_red_result": "exit 1; AssertionError",
                    },
                    {
                        "focused_green_command": FOCUSED_TRANSITION_COMMAND,
                        "focused_green_result": "exit 0; 1 passed",
                    },
                ],
            }
        ],
        "counts": {
            "pending": 0,
            "in_progress": 0,
            "red_verified": 0,
            "green_verified": 1,
            "succeeded": 0,
            "failed_retryable": 0,
            "failed_final": 0,
            "needs_review": 0,
            "blocked": 0,
            "skipped": 0,
        },
    }

    with pytest.raises(
        IllegalTransitionError,
        match="full suite evidence result appears to be a failure",
    ):
        transition_item(
            state,
            "plan:T1-one",
            "succeeded",
            evidence={
                "full_suite_command": "uv run pytest -q",
                "full_suite_result": "exit 2; 3 failed",
            },
        )
