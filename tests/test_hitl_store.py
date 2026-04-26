import sqlite3

from stateful_dev.hitl_store import init_store


def test_init_store_creates_request_and_event_tables(tmp_path):
    db_path = tmp_path / "operator-inbox.sqlite3"

    init_store(db_path)

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "hitl_requests",
        "operator_events",
        "discord_messages",
        "audit_log",
    } <= table_names
