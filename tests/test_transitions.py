import pytest

from stateful_dev.transitions import IllegalTransitionError, transition_item

FOCUSED_TRANSITION_COMMAND = "uv run pytest tests/test_transitions.py -q"


def _counts(status: str) -> dict[str, int]:
    statuses = [
        "pending",
        "in_progress",
        "red_verified",
        "green_verified",
        "succeeded",
        "failed_retryable",
        "failed_final",
        "needs_review",
        "blocked",
        "skipped",
    ]
    counts = {key: 0 for key in statuses}
    counts[status] = 1
    return counts


def _state(status: str, evidence: list[dict] | None = None) -> dict:
    item = {
        "id": "plan:T1-one",
        "status": status,
    }
    if evidence is not None:
        item["evidence"] = evidence
    return {"items": [item], "counts": _counts(status)}


def _red_evidence(result: str = "exit 1; AssertionError") -> dict:
    return {
        "focused_red_command": FOCUSED_TRANSITION_COMMAND,
        "focused_red_result": result,
    }


def _green_evidence(result: str = "exit 0; 1 passed") -> dict:
    return {
        "focused_green_command": FOCUSED_TRANSITION_COMMAND,
        "focused_green_result": result,
    }


def _full_suite_evidence(result: str = "exit 0; all tests passed") -> dict:
    return {
        "full_suite_command": "uv run pytest -q",
        "full_suite_result": result,
    }


def test_pending_cannot_jump_to_succeeded():
    state = _state("pending")

    with pytest.raises(IllegalTransitionError, match="pending -> succeeded"):
        transition_item(state, "plan:T1-one", "succeeded")

    assert state["items"][0]["status"] == "pending"


def test_green_requires_red_evidence():
    state = _state("red_verified")

    with pytest.raises(
        IllegalTransitionError,
        match="green_verified requires RED evidence",
    ):
        transition_item(
            state,
            "plan:T1-one",
            "green_verified",
            evidence=_green_evidence(),
        )

    assert state["items"][0]["status"] == "red_verified"


def test_red_transition_accepts_previously_recorded_red_evidence():
    state = _state("in_progress", evidence=[_red_evidence()])

    updated = transition_item(state, "plan:T1-one", "red_verified")

    assert updated["items"][0]["status"] == "red_verified"
    assert updated["items"][0]["red_verified"] is True


def test_green_requires_focused_green_evidence():
    state = _state("red_verified", evidence=[_red_evidence()])

    with pytest.raises(
        IllegalTransitionError,
        match="green_verified requires focused GREEN evidence",
    ):
        transition_item(state, "plan:T1-one", "green_verified")


def test_green_rejects_recorded_failed_green_evidence():
    state = _state("red_verified", evidence=[_red_evidence(), _green_evidence("exit 1; failed")])

    with pytest.raises(
        IllegalTransitionError,
        match="GREEN evidence result appears to be a failure",
    ):
        transition_item(state, "plan:T1-one", "green_verified")


def test_red_evidence_rejects_obvious_success_result():
    state = _state("in_progress")

    with pytest.raises(
        IllegalTransitionError,
        match="RED evidence result appears to be a success",
    ):
        transition_item(
            state,
            "plan:T1-one",
            "red_verified",
            evidence=_red_evidence("exit 0; 1 passed"),
        )


def test_green_evidence_rejects_obvious_failure_result():
    state = _state("red_verified", evidence=[_red_evidence()])

    with pytest.raises(
        IllegalTransitionError,
        match="GREEN evidence result appears to be a failure",
    ):
        transition_item(
            state,
            "plan:T1-one",
            "green_verified",
            evidence=_green_evidence("exit 1; failed"),
        )


def test_full_suite_evidence_rejects_obvious_failure_result():
    state = _state("green_verified", evidence=[_red_evidence(), _green_evidence()])

    with pytest.raises(
        IllegalTransitionError,
        match="full suite evidence result appears to be a failure",
    ):
        transition_item(
            state,
            "plan:T1-one",
            "succeeded",
            evidence=_full_suite_evidence("exit 2; 3 failed"),
        )


def test_succeeded_rejects_recorded_failed_full_suite_evidence():
    state = _state(
        "green_verified",
        evidence=[
            _red_evidence(),
            _green_evidence(),
            _full_suite_evidence("exit 2; 3 failed"),
        ],
    )

    with pytest.raises(
        IllegalTransitionError,
        match="full suite evidence result appears to be a failure",
    ):
        transition_item(state, "plan:T1-one", "succeeded")



def test_green_result_with_no_errors_is_not_treated_as_failure():
    state = _state(
        "red_verified",
        evidence=[
            {"focused_red_command": "pytest red", "focused_red_result": "exit 1"},
        ],
    )

    updated = transition_item(
        state,
        "plan:T1-one",
        "green_verified",
        {
            "focused_green_command": "pytest green",
            "focused_green_result": "exit 0; passed; no errors",
        },
    )

    assert updated["items"][0]["status"] == "green_verified"


def test_structured_exit_code_overrides_ambiguous_success_text():
    state = _state(
        "red_verified",
        evidence=[
            {"focused_red_command": "pytest red", "focused_red_result": "exit 1"},
        ],
    )

    with pytest.raises(IllegalTransitionError):
        transition_item(
            state,
            "plan:T1-one",
            "green_verified",
            {
                "focused_green_command": "pytest green",
                "focused_green_result": "exit 0; passed before cleanup failure",
                "exit_code": 1,
            },
        )
