from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from stateful_dev.hitl_models import HITLRequest

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
