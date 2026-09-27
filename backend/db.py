import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent.parent / "bot_users.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            requests_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def track_user(telegram_id: int, username: str | None, first_name: str | None, last_name: str | None):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    existing = conn.execute(
        "SELECT telegram_id FROM bot_users WHERE telegram_id = ?", (telegram_id,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE bot_users
            SET username = ?, first_name = ?, last_name = ?, last_seen = ?, requests_count = requests_count + 1
            WHERE telegram_id = ?
        """, (username, first_name, last_name, now, telegram_id))
    else:
        conn.execute("""
            INSERT INTO bot_users (telegram_id, username, first_name, last_name, first_seen, last_seen, requests_count)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (telegram_id, username, first_name, last_name, now, now))

    conn.commit()
    conn.close()


def list_users():
    conn = get_connection()
    rows = conn.execute("""
        SELECT telegram_id, username, first_name, last_name, first_seen, last_seen, requests_count
        FROM bot_users
        ORDER BY last_seen DESC
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]