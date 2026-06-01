"""玩家/用户管理 — 多人模式核心模块"""
from __future__ import annotations

from database.connection import get_connection

# ── 当前活跃玩家（模块级单例，进程内有效）────────────────────────
_current_player_id: int = 1
_current_player_name: str = "默认用户"


def get_current_player_id() -> int:
    return _current_player_id


def get_current_player_name() -> str:
    return _current_player_name


def set_current_player(player_id: int) -> bool:
    """切换当前玩家；返回 False 表示 player_id 不存在"""
    global _current_player_id, _current_player_name
    conn = get_connection()
    cur = conn.execute("SELECT id, name FROM players WHERE id = ?", (player_id,))
    row = cur.fetchone()
    if not row:
        return False
    _current_player_id = row["id"]
    _current_player_name = row["name"]
    conn.execute(
        "UPDATE players SET last_active = CURRENT_TIMESTAMP WHERE id = ?",
        (player_id,),
    )
    conn.commit()
    return True


# ── CRUD ─────────────────────────────────────────────────────────

def get_players() -> list[dict]:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM players ORDER BY last_active DESC")
    return [dict(row) for row in cur.fetchall()]


def get_player(player_id: int) -> dict | None:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def create_player(name: str) -> int:
    """新建玩家并初始化 domain_stats；名称重复返回 -1"""
    name = name.strip()
    if not name:
        return -1
    conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO players (name) VALUES (?)", (name,))
        player_id = cur.lastrowid
        _init_domain_stats(conn, player_id)
        conn.commit()
        return player_id
    except Exception:
        return -1


def _init_domain_stats(conn, player_id: int) -> None:
    for domain_id in range(1, 9):
        conn.execute(
            "INSERT OR IGNORE INTO domain_stats (player_id, domain_id) VALUES (?,?)",
            (player_id, domain_id),
        )


# ── 重置 / 删除 ───────────────────────────────────────────────────

def reset_player_data(player_id: int) -> dict:
    """清空指定玩家的全部答题记录，返回被清除的统计数量"""
    conn = get_connection()

    cur = conn.execute(
        "SELECT COUNT(*) AS cnt FROM study_sessions WHERE player_id = ?",
        (player_id,),
    )
    session_count = cur.fetchone()["cnt"]

    cur = conn.execute(
        """SELECT COUNT(*) AS cnt FROM answer_records ar
           JOIN study_sessions ss ON ar.session_id = ss.id
           WHERE ss.player_id = ?""",
        (player_id,),
    )
    answer_count = cur.fetchone()["cnt"]

    # 删除答题记录（通过 session 关联）
    conn.execute(
        """DELETE FROM answer_records WHERE session_id IN
           (SELECT id FROM study_sessions WHERE player_id = ?)""",
        (player_id,),
    )
    conn.execute("DELETE FROM study_sessions  WHERE player_id = ?", (player_id,))
    conn.execute("DELETE FROM question_stats  WHERE player_id = ?", (player_id,))
    conn.execute("DELETE FROM daily_progress  WHERE player_id = ?", (player_id,))
    conn.execute(
        """UPDATE domain_stats SET
               total_attempts = 0, correct_count = 0,
               accuracy_rate  = 0.0, avg_time_sec = 0.0,
               last_practiced = NULL, updated_at = CURRENT_TIMESTAMP
           WHERE player_id = ?""",
        (player_id,),
    )
    conn.commit()
    return {"sessions": session_count, "answers": answer_count}


def delete_player(player_id: int) -> bool:
    """删除玩家及其全部数据；最后一个玩家不可删除"""
    conn = get_connection()
    cur = conn.execute("SELECT COUNT(*) AS cnt FROM players")
    if cur.fetchone()["cnt"] <= 1:
        return False
    reset_player_data(player_id)
    conn.execute("DELETE FROM domain_stats WHERE player_id = ?", (player_id,))
    conn.execute("DELETE FROM players     WHERE id = ?", (player_id,))
    conn.commit()
    return True
