from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from stateful_dev.hitl_models import HITLRequest, OperatorEvent

REQUEST_STATUS_OPEN = "open"
REQUEST_STATUS_CANCELLED = "cancelled"
REQUEST_STATUS_EXPIRED = "expired"
EVENT_STATUS_PENDING = "pending"
EVENT_STATUS_CONSUMED = "consumed"

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS hitl_requests (
        request_id TEXT PRIMARY KEY,
        worker TEXT NOT NULL,
        node TEXT NOT NULL,
        project TEXT NOT NULL,
        state_path_hash TEXT NOT NULL,
        item_id TEXT NOT NULL,
        request_type TEXT NOT NULL,
        status TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS operator_events (
        event_id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL,
        node TEXT NOT NULL,
        worker TEXT NOT NULL,
        item_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        status TEXT NOT NULL,
        actor_discord_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        consumed_at TEXT,
        FOREIGN KEY (request_id) REFERENCES hitl_requests(request_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS discord_messages (
        message_id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY (request_id) REFERENCES hitl_requests(request_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
)


def init_store(path: str | Path) -> None:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.commit()


def _request_json(request: HITLRequest) -> str:
    return json.dumps(request.to_dict(), sort_keys=True, separators=(",", ":"))


def _event_json(event: OperatorEvent) -> str:
    return json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))


def _discord_message_json(message: dict[str, object]) -> str:
    return json.dumps(message, sort_keys=True, separators=(",", ":"))


def _audit_payload(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _write_audit(
    connection: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: str,
    action: str,
    payload: dict[str, object] | None = None,
    created_at: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_log (
            entity_type,
            entity_id,
            action,
            payload_json,
            created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            entity_type,
            entity_id,
            action,
            _audit_payload(payload or {}),
            created_at or datetime.now(UTC).isoformat(),
        ),
    )


def _request_with_status(request: HITLRequest, status: str) -> HITLRequest:
    return HITLRequest.from_dict({**request.to_dict(), "status": status})


def get_audit_records(path: str | Path) -> list[dict[str, object]]:
    init_store(path)
    with sqlite3.connect(Path(path)) as connection:
        rows = connection.execute(
            """
            SELECT entity_type, entity_id, action, payload_json, created_at
            FROM audit_log
            ORDER BY audit_id
            """
        ).fetchall()
    return [
        {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "payload": json.loads(payload_json),
            "created_at": created_at,
        }
        for entity_type, entity_id, action, payload_json, created_at in rows
    ]


def put_request(path: str | Path, request: HITLRequest) -> None:
    init_store(path)
    payload_json = _request_json(request)
    with sqlite3.connect(Path(path)) as connection:
        row = connection.execute(
            "SELECT payload_json FROM hitl_requests WHERE request_id = ?",
            (request.request_id,),
        ).fetchone()
        if row is not None:
            if row[0] == payload_json:
                return
            raise ValueError(
                f"duplicate request_id with different payload: {request.request_id}"
            )
        connection.execute(
            """
            INSERT INTO hitl_requests (
                request_id,
                worker,
                node,
                project,
                state_path_hash,
                item_id,
                request_type,
                status,
                payload_json,
                created_at,
                expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request.request_id,
                request.worker,
                request.node,
                request.project,
                request.state_path_hash,
                request.item_id,
                request.request_type,
                request.status,
                payload_json,
                request.created_at,
                request.expires_at,
            ),
        )
        _write_audit(
            connection,
            entity_type="request",
            entity_id=request.request_id,
            action="request_created",
            payload={"status": request.status},
            created_at=request.created_at,
        )
        connection.commit()


def get_request(path: str | Path, request_id: str) -> HITLRequest | None:
    init_store(path)
    with sqlite3.connect(Path(path)) as connection:
        row = connection.execute(
            "SELECT payload_json FROM hitl_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
    if row is None:
        return None
    return HITLRequest.from_dict(json.loads(row[0]))


def put_discord_message(
    path: str | Path,
    *,
    channel_id: str,
    message_id: str,
    request_id: str,
    render_version: int,
    card_status: str,
    created_at: str | None = None,
) -> None:
    init_store(path)
    timestamp = created_at or datetime.now(UTC).isoformat()
    message: dict[str, object] = {
        "channel_id": channel_id,
        "message_id": message_id,
        "request_id": request_id,
        "render_version": render_version,
        "card_status": card_status,
        "created_at": timestamp,
        "updated_at": None,
    }
    payload_json = _discord_message_json(message)
    with sqlite3.connect(Path(path)) as connection:
        row = connection.execute(
            "SELECT payload_json FROM discord_messages WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        if row is not None:
            if row[0] == payload_json:
                return
            raise ValueError(
                f"duplicate message_id with different payload: {message_id}"
            )
        connection.execute(
            """
            INSERT INTO discord_messages (
                message_id,
                request_id,
                channel_id,
                payload_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (message_id, request_id, channel_id, payload_json, timestamp, None),
        )
        _write_audit(
            connection,
            entity_type="discord_message",
            entity_id=message_id,
            action="discord_message_recorded",
            payload={"request_id": request_id, "card_status": card_status},
            created_at=timestamp,
        )
        connection.commit()


def get_discord_message(
    path: str | Path,
    *,
    message_id: str,
) -> dict[str, object] | None:
    init_store(path)
    with sqlite3.connect(Path(path)) as connection:
        row = connection.execute(
            "SELECT payload_json FROM discord_messages WHERE message_id = ?",
            (message_id,),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def update_discord_message_status(
    path: str | Path,
    *,
    message_id: str,
    card_status: str,
    updated_at: str | None = None,
) -> dict[str, object] | None:
    init_store(path)
    timestamp = updated_at or datetime.now(UTC).isoformat()
    with sqlite3.connect(Path(path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT payload_json FROM discord_messages WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            connection.rollback()
            return None
        message = json.loads(row[0])
        message["card_status"] = card_status
        message["updated_at"] = timestamp
        payload_json = _discord_message_json(message)
        connection.execute(
            """
            UPDATE discord_messages
            SET payload_json = ?, updated_at = ?
            WHERE message_id = ?
            """,
            (payload_json, timestamp, message_id),
        )
        _write_audit(
            connection,
            entity_type="discord_message",
            entity_id=message_id,
            action="discord_message_status_updated",
            payload={
                "request_id": str(message["request_id"]),
                "card_status": card_status,
            },
            created_at=timestamp,
        )
        connection.commit()
    return message


def list_open_requests(path: str | Path) -> list[HITLRequest]:
    init_store(path)
    with sqlite3.connect(Path(path)) as connection:
        rows = connection.execute(
            """
            SELECT payload_json
            FROM hitl_requests
            WHERE status = 'open'
            ORDER BY created_at, request_id
            """
        ).fetchall()
    return [HITLRequest.from_dict(json.loads(row[0])) for row in rows]


def put_operator_event(path: str | Path, event: OperatorEvent) -> None:
    init_store(path)
    payload_json = _event_json(event)
    with sqlite3.connect(Path(path)) as connection:
        row = connection.execute(
            "SELECT payload_json FROM operator_events WHERE event_id = ?",
            (event.event_id,),
        ).fetchone()
        if row is not None:
            if row[0] == payload_json:
                return
            raise ValueError(
                f"duplicate event_id with different payload: {event.event_id}"
            )
        connection.execute(
            """
            INSERT INTO operator_events (
                event_id,
                request_id,
                node,
                worker,
                item_id,
                event_type,
                status,
                actor_discord_id,
                payload_json,
                created_at,
                consumed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.request_id,
                event.node,
                event.worker,
                event.item_id,
                event.event_type,
                event.status,
                event.actor_discord_id,
                payload_json,
                event.created_at,
                event.consumed_at,
            ),
        )
        _write_audit(
            connection,
            entity_type="event",
            entity_id=event.event_id,
            action="event_created",
            payload={"request_id": event.request_id, "status": event.status},
            created_at=event.created_at,
        )
        connection.commit()


def list_pending_events(
    path: str | Path,
    *,
    node: str,
    worker: str | None = None,
    request_id: str | None = None,
) -> list[OperatorEvent]:
    init_store(path)
    clauses = [
        f"event.status = '{EVENT_STATUS_PENDING}'",
        "event.node = ?",
        f"request.status = '{REQUEST_STATUS_OPEN}'",
    ]
    params: list[str] = [node]
    if worker is not None:
        clauses.append("event.worker = ?")
        params.append(worker)
    if request_id is not None:
        clauses.append("event.request_id = ?")
        params.append(request_id)
    where_clause = " AND ".join(clauses)
    with sqlite3.connect(Path(path)) as connection:
        rows = connection.execute(
            f"""
            SELECT event.payload_json
            FROM operator_events AS event
            JOIN hitl_requests AS request
              ON request.request_id = event.request_id
            WHERE {where_clause}
            ORDER BY event.created_at, event.event_id
            """,
            params,
        ).fetchall()
    return [OperatorEvent.from_dict(json.loads(row[0])) for row in rows]


def consume_event(
    path: str | Path,
    *,
    event_id: str,
    node: str,
    consumed_at: str | None = None,
) -> OperatorEvent | None:
    init_store(path)
    consumed_timestamp = consumed_at or datetime.now(UTC).isoformat()
    with sqlite3.connect(Path(path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT payload_json
            FROM operator_events
            WHERE event_id = ?
              AND node = ?
              AND status = 'pending'
            """,
            (event_id, node),
        ).fetchone()
        if row is None:
            connection.rollback()
            return None
        event = OperatorEvent.from_dict(json.loads(row[0]))
        consumed_event = OperatorEvent.from_dict(
            {
                **event.to_dict(),
                "status": EVENT_STATUS_CONSUMED,
                "consumed_at": consumed_timestamp,
            }
        )
        payload_json = _event_json(consumed_event)
        connection.execute(
            """
            UPDATE operator_events
            SET status = 'consumed', consumed_at = ?, payload_json = ?
            WHERE event_id = ?
              AND node = ?
              AND status = 'pending'
            """,
            (consumed_timestamp, payload_json, event_id, node),
        )
        _write_audit(
            connection,
            entity_type="event",
            entity_id=event_id,
            action="event_consumed",
            payload={"node": node, "request_id": event.request_id},
            created_at=consumed_timestamp,
        )
        connection.commit()
    return consumed_event


def _set_request_terminal_status(
    path: str | Path,
    *,
    request_id: str,
    status: str,
    action: str,
    timestamp: str | None,
) -> HITLRequest | None:
    init_store(path)
    changed_at = timestamp or datetime.now(UTC).isoformat()
    with sqlite3.connect(Path(path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT payload_json
            FROM hitl_requests
            WHERE request_id = ?
              AND status = 'open'
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            connection.rollback()
            return None
        request = HITLRequest.from_dict(json.loads(row[0]))
        updated = _request_with_status(request, status)
        connection.execute(
            """
            UPDATE hitl_requests
            SET status = ?, payload_json = ?
            WHERE request_id = ?
              AND status = 'open'
            """,
            (status, _request_json(updated), request_id),
        )
        _write_audit(
            connection,
            entity_type="request",
            entity_id=request_id,
            action=action,
            payload={"status": status},
            created_at=changed_at,
        )
        connection.commit()
    return updated


def expire_request(
    path: str | Path,
    *,
    request_id: str,
    expired_at: str | None = None,
) -> HITLRequest | None:
    return _set_request_terminal_status(
        path,
        request_id=request_id,
        status=REQUEST_STATUS_EXPIRED,
        action="request_expired",
        timestamp=expired_at,
    )


def cancel_request(
    path: str | Path,
    *,
    request_id: str,
    cancelled_at: str | None = None,
) -> HITLRequest | None:
    return _set_request_terminal_status(
        path,
        request_id=request_id,
        status=REQUEST_STATUS_CANCELLED,
        action="request_cancelled",
        timestamp=cancelled_at,
    )
