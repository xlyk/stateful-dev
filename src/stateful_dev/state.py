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


def _is_int(value: Any) -> bool:
    return type(value) is int


def _item_label(item: dict[str, Any], index: int) -> str:
    item_id = item.get("id")
    if isinstance(item_id, str) and item_id:
        return item_id
    return f"item at index {index}"


def _validate_top_level_types(data: dict[str, Any], errors: list[str]) -> None:
    if "job_name" in data and not isinstance(data["job_name"], str):
        errors.append("job_name must be a string")
    if "version" in data and not _is_int(data["version"]):
        errors.append("version must be an integer")
    if "project_root" in data and not isinstance(data["project_root"], str):
        errors.append("project_root must be a string")

    plan_paths = data.get("plan_paths")
    if "plan_paths" in data:
        if not isinstance(plan_paths, list):
            errors.append("plan_paths must be a list")
        else:
            for index, plan_path in enumerate(plan_paths):
                if not isinstance(plan_path, str):
                    errors.append(f"plan_paths[{index}] must be a string")


def _validate_optional_item_fields(
    item: dict[str, Any], label: str, errors: list[str]
) -> None:
    for field in ("plan_path", "title"):
        if field in item and not isinstance(item[field], str):
            errors.append(f"{field} for {label} must be a string")

    if "attempts" in item and not _is_int(item["attempts"]):
        errors.append(f"attempts for {label} must be an integer")

    for field in (
        "red_verified",
        "green_verified",
        "full_suite_verified",
        "needs_operator",
    ):
        if field in item and type(item[field]) is not bool:
            errors.append(f"{field} for {label} must be a boolean")

    for field in ("files_touched", "test_commands"):
        if field in item and not isinstance(item[field], list):
            errors.append(f"{field} for {label} must be a list")

    for field in ("commit_sha", "result"):
        value = item.get(field)
        if field in item and value is not None and not isinstance(value, str):
            errors.append(f"{field} for {label} must be a string or null")


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
        _validate_optional_item_fields(item, label, errors)

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

    _validate_top_level_types(data, errors)

    items = data.get("items", [])
    if not isinstance(items, list):
        errors.append("items must be a list")
        items = []

    counts = _recompute_counts(items, errors)

    configured_counts = data.get("counts", {})
    if not isinstance(configured_counts, dict):
        errors.append("counts must be an object")
        configured_counts = {}

    # HITL block is optional; validate shape when present
    hitl = data.get("hitl")
    if hitl is not None:
        if not isinstance(hitl, dict):
            errors.append("hitl must be an object when present")
        else:
            if hitl.get("enabled") is True:
                for field in ("provider", "node_id", "worker_id", "poll_policy"):
                    if not hitl.get(field):
                        errors.append(f"hitl.enabled=true requires hitl.{field}")
                poll_policy = hitl.get("poll_policy")
                if poll_policy not in ("required", "optional"):
                    errors.append(
                        "hitl.poll_policy must be 'required' or 'optional', "
                        f"got: {poll_policy!r}"
                    )
            active_requests = hitl.get("active_requests")
            if active_requests is not None and not isinstance(active_requests, list):
                errors.append("hitl.active_requests must be a list when present")

    for status, expected in counts.items():
        found = configured_counts.get(status, 0)
        if not _is_int(found):
            errors.append(f"count for {status} must be an integer")
            found = 0
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
