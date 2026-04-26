from dataclasses import dataclass
from typing import Any

VALID_STATUSES = {
    "pending",
    "in_progress",
    "red_verified",
    "green_verified",
    "succeeded",
    "needs_review",
    "blocked",
    "failed_retryable",
    "failed_final",
    "skipped",
}
REQUIRED_TOP_LEVEL_KEYS = {
    "job_name",
    "version",
    "project_root",
    "plan_paths",
    "counts",
    "items",
}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]
    warnings: list[str]
    counts: dict[str, int]


def _empty_counts() -> dict[str, int]:
    return dict.fromkeys(VALID_STATUSES, 0)


def _item_label(item: dict[str, Any], index: int) -> str:
    item_id = item.get("id")
    if isinstance(item_id, str) and item_id:
        return item_id
    return f"item at index {index}"


def _recompute_counts(items: list[Any], errors: list[str]) -> dict[str, int]:
    counts = _empty_counts()
    seen_ids: set[str] = set()

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"item at index {index} is not an object")
            continue

        label = _item_label(item, index)
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            errors.append(f"missing item id: {label}")
        elif item_id in seen_ids:
            errors.append(f"duplicate item id: {item_id}")
        else:
            seen_ids.add(item_id)

        status = item.get("status")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            errors.append(f"invalid status for {label}: {status}")
            continue
        counts[status] += 1

    return counts


def validate_state(data: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ValidationResult(
            ok=False,
            errors=["state must be an object"],
            warnings=[],
            counts=_empty_counts(),
        )

    for key in sorted(REQUIRED_TOP_LEVEL_KEYS):
        if key not in data:
            errors.append(f"missing required key: {key}")

    items = data.get("items", [])
    if not isinstance(items, list):
        errors.append("items must be a list")
        items = []

    counts = _recompute_counts(items, errors)

    configured_counts = data.get("counts", {})
    if not isinstance(configured_counts, dict):
        errors.append("counts must be an object")
        configured_counts = {}

    for status, expected in counts.items():
        found = configured_counts.get(status, 0)
        if found != expected:
            errors.append(
                f"count drift for {status}: expected {expected}, found {found}"
            )

    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        counts=counts,
    )
