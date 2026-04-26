from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Self


class ValidationError(ValueError):
    pass


def _require_fields(data: dict[str, Any], required: set[str]) -> None:
    for name in sorted(required):
        if name not in data:
            raise ValidationError(f"missing required field: {name}")


def _require_string(data: dict[str, Any], name: str) -> str:
    value = data[name]
    if not isinstance(value, str) or not value:
        raise ValidationError(f"field must be a non-empty string: {name}")
    return value


def _require_optional_string(data: dict[str, Any], name: str) -> str | None:
    value = data[name]
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValidationError(f"field must be null or a non-empty string: {name}")
    return value


def _require_string_list(data: dict[str, Any], name: str) -> list[str]:
    value = data[name]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError(f"field must be a list of strings: {name}")
    return list(value)


def _require_object(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data[name]
    if not isinstance(value, dict):
        raise ValidationError(f"field must be an object: {name}")
    return dict(value)


def _dataclass_field_names(model: type[Any]) -> set[str]:
    return {field.name for field in fields(model)}


@dataclass(frozen=True)
class HITLRequest:
    request_id: str
    worker: str
    node: str
    project: str
    project_root: str
    state_path: str
    state_path_hash: str
    plan_path: str
    item_id: str
    request_type: str
    status: str
    question: str
    allowed_actions: list[str]
    constraints: list[str]
    payload: dict[str, Any]
    fallback_context: str
    created_at: str
    expires_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        _require_fields(data, _dataclass_field_names(cls))
        return cls(
            request_id=_require_string(data, "request_id"),
            worker=_require_string(data, "worker"),
            node=_require_string(data, "node"),
            project=_require_string(data, "project"),
            project_root=_require_string(data, "project_root"),
            state_path=_require_string(data, "state_path"),
            state_path_hash=_require_string(data, "state_path_hash"),
            plan_path=_require_string(data, "plan_path"),
            item_id=_require_string(data, "item_id"),
            request_type=_require_string(data, "request_type"),
            status=_require_string(data, "status"),
            question=_require_string(data, "question"),
            allowed_actions=_require_string_list(data, "allowed_actions"),
            constraints=_require_string_list(data, "constraints"),
            payload=_require_object(data, "payload"),
            fallback_context=_require_string(data, "fallback_context"),
            created_at=_require_string(data, "created_at"),
            expires_at=_require_string(data, "expires_at"),
        )


@dataclass(frozen=True)
class OperatorEvent:
    event_id: str
    request_id: str
    event_type: str
    status: str
    actor_discord_id: str
    node: str
    worker: str
    item_id: str
    state_path_hash: str
    payload: dict[str, Any]
    constraints: list[str]
    created_at: str
    consumed_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        _require_fields(data, _dataclass_field_names(cls))
        return cls(
            event_id=_require_string(data, "event_id"),
            request_id=_require_string(data, "request_id"),
            event_type=_require_string(data, "event_type"),
            status=_require_string(data, "status"),
            actor_discord_id=_require_string(data, "actor_discord_id"),
            node=_require_string(data, "node"),
            worker=_require_string(data, "worker"),
            item_id=_require_string(data, "item_id"),
            state_path_hash=_require_string(data, "state_path_hash"),
            payload=_require_object(data, "payload"),
            constraints=_require_string_list(data, "constraints"),
            created_at=_require_string(data, "created_at"),
            consumed_at=_require_optional_string(data, "consumed_at"),
        )


@dataclass(frozen=True)
class WorkerResume:
    request_id: str
    event_id: str
    worker: str
    node: str
    item_id: str
    state_path_hash: str
    allowed_next_action: str
    constraints: list[str]
    payload: dict[str, Any]
    consumed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        _require_fields(data, _dataclass_field_names(cls))
        return cls(
            request_id=_require_string(data, "request_id"),
            event_id=_require_string(data, "event_id"),
            worker=_require_string(data, "worker"),
            node=_require_string(data, "node"),
            item_id=_require_string(data, "item_id"),
            state_path_hash=_require_string(data, "state_path_hash"),
            allowed_next_action=_require_string(data, "allowed_next_action"),
            constraints=_require_string_list(data, "constraints"),
            payload=_require_object(data, "payload"),
            consumed_at=_require_string(data, "consumed_at"),
        )
