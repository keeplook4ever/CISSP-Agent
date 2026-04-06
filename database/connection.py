from __future__ import annotations

import sqlite3
from pathlib import Path
from config.settings import settings

_conn: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_database() -> None:
    sql_path = Path(__file__).parent / "migrations" / "v1_init.sql"
    conn = get_connection()
    conn.executescript(sql_path.read_text(encoding="utf-8"))
    conn.commit()


def close_connection() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None
