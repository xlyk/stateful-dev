from copy import deepcopy
from typing import Any

from stateful_dev.state import VALID_STATUSES

LEGAL_TRANSITIONS = {
    "pending": {"in_progress", "needs_review", "blocked", "failed_retryable"},
    "failed_retryable": {"in_progress", "failed_final"},
    "in_progress": {"red_verified", "needs_review", "blocked", "failed_retryable"},
    "red_verified": {"green_verified", "failed_retryable", "needs_review"},
    "green_verified": {"succeeded", "failed_retryable", "needs_review"},
    "succeeded": set(),
    "needs_review": set(),
    "blocked": set(),
    "failed_final": set(),
    "skipped": set(),
}


class IllegalTransitionError(ValueError):
    pass


def _find_item(state: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in state.get("items", []):
        if item.get("id") == item_id:
            return item
    raise KeyError(f"unknown item id: {item_id}")


def _recompute_counts(state: dict[str, Any]) -> None:
    counts = dict.fromkeys(VALID_STATUSES, 0)
    for item in state.get("items", []):
        status = item.get("status")
        if status in counts:
            counts[status] += 1
    state["counts"] = counts


def _evidence_entries(item: dict[str, Any]) -> list[dict[str, Any]]:
    entries = item.get("evidence", [])
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _has_fields(payload: dict[str, Any] | None, required_fields: set[str]) -> bool:
    if not isinstance(payload, dict):
        return False
    return all(bool(payload.get(field)) for field in required_fields)


def _has_recorded_fields(item: dict[str, Any], required_fields: set[str]) -> bool:
    if _has_fields(item, required_fields):
        return True
    return any(_has_fields(entry, required_fields) for entry in _evidence_entries(item))


def _has_red_evidence(item: dict[str, Any]) -> bool:
    return _has_recorded_fields(item, {"focused_red_command", "focused_red_result"})


def _result_text(evidence: dict[str, Any] | None, field: str) -> str:
    if not isinstance(evidence, dict):
        return ""
    value = evidence.get(field)
    return value if isinstance(value, str) else ""


def _looks_successful(result: str) -> bool:
    lowered = result.lower()
    success_markers = (
        "exit 0",
        "exit_code: 0",
        "exit code 0",
        "passed",
        "success",
        "succeeded",
        "all checks passed",
    )
    return any(marker in lowered for marker in success_markers)


def _looks_failed(result: str) -> bool:
    lowered = result.lower()
    failure_markers = (
        "exit 1",
        "exit 2",
        "exit_code: 1",
        "exit_code: 2",
        "exit code 1",
        "exit code 2",
        "failed",
        "failure",
        "error",
        "traceback",
    )
    return any(marker in lowered for marker in failure_markers)


def _require_result_semantics(
    target_status: str, evidence: dict[str, Any] | None
) -> None:
    red_result = _result_text(evidence, "focused_red_result")
    if (
        target_status == "red_verified"
        and _looks_successful(red_result)
        and not _looks_failed(red_result)
    ):
        raise IllegalTransitionError("RED evidence result appears to be a success")

    if target_status == "green_verified" and _looks_failed(
        _result_text(evidence, "focused_green_result")
    ):
        raise IllegalTransitionError("GREEN evidence result appears to be a failure")

    if target_status == "succeeded" and _looks_failed(
        _result_text(evidence, "full_suite_result")
    ):
        raise IllegalTransitionError(
            "full suite evidence result appears to be a failure"
        )


def _require_transition_evidence(
    item: dict[str, Any], target_status: str, evidence: dict[str, Any] | None
) -> None:
    if target_status == "red_verified" and not _has_fields(
        evidence, {"focused_red_command", "focused_red_result"}
    ):
        raise IllegalTransitionError(
            "red_verified requires focused RED command and result evidence"
        )

    if target_status == "green_verified" and not _has_red_evidence(item):
        raise IllegalTransitionError("green_verified requires RED evidence")

    if target_status == "succeeded":
        if not _has_red_evidence(item):
            raise IllegalTransitionError("succeeded requires RED evidence")
        if not _has_recorded_fields(
            item, {"focused_green_command", "focused_green_result"}
        ):
            raise IllegalTransitionError("succeeded requires focused GREEN evidence")
        if not (
            _has_recorded_fields(item, {"full_suite_command", "full_suite_result"})
            or _has_fields(evidence, {"full_suite_command", "full_suite_result"})
        ):
            raise IllegalTransitionError("succeeded requires full suite evidence")

    _require_result_semantics(target_status, evidence)


def _apply_evidence_flags(
    item: dict[str, Any], target_status: str, evidence: dict[str, Any] | None
) -> None:
    if evidence is not None:
        item.setdefault("evidence", []).append(evidence)
    if target_status == "red_verified":
        item["red_verified"] = True
    elif target_status == "green_verified":
        item["green_verified"] = True
    elif target_status == "succeeded":
        item["full_suite_verified"] = True


def transition_item(
    state: dict[str, Any],
    item_id: str,
    target_status: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target_status not in VALID_STATUSES:
        raise IllegalTransitionError(f"unknown target status: {target_status}")

    updated_state = deepcopy(state)
    item = _find_item(updated_state, item_id)
    current_status = item.get("status")
    allowed = LEGAL_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise IllegalTransitionError(
            f"illegal transition: {current_status} -> {target_status}"
        )

    _require_transition_evidence(item, target_status, evidence)

    item["status"] = target_status
    _apply_evidence_flags(item, target_status, evidence)
    _recompute_counts(updated_state)
    return updated_state
