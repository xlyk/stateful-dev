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

    item["status"] = target_status
    if evidence is not None:
        item.setdefault("evidence", []).append(evidence)
    _recompute_counts(updated_state)
    return updated_state
