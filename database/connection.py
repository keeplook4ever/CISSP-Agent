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
    migrations_dir = Path(__file__).parent / "migrations"
    conn = get_connection()

    # 确保迁移记录表存在（用于幂等执行迁移）
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               version TEXT PRIMARY KEY,
               applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
           )"""
    )
    conn.commit()

    applied = {
        row[0]
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }

    for sql_file in sorted(migrations_dir.glob("v*.sql")):
        version = sql_file.stem  # 如 "v1_init"
        if version in applied:
            continue
        try:
            conn.executescript(sql_file.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
                (version,),
            )
            conn.commit()
        except Exception as exc:
            # 迁移失败时打印警告，不中断启动（避免已有数据库因重复 ALTER 崩溃）
            import warnings
            warnings.warn(f"Migration {version} failed (may already be applied): {exc}")


def close_connection() -> None:
    global _conn
    if _conn:
        _conn.close()
        _conn = None
