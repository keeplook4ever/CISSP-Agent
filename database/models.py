"""数据库 CRUD 操作封装"""
import json
import sqlite3
from datetime import date, datetime
from typing import Optional

from database.connection import get_connection


# ───────────── 题库操作 ─────────────

def insert_question(q: dict) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT OR IGNORE INTO questions
           (qid, domain_id, subdomain, difficulty, source,
            question, option_a, option_b, option_c, option_d,
            correct, explanation, tags)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            q["id"], q["domain_id"], q.get("subdomain"), q.get("difficulty", 2),
            q.get("source", "local"), q["question"],
            q["options"]["A"], q["options"]["B"],
            q["options"]["C"], q["options"]["D"],
            q["correct"], q.get("explanation", ""),
            json.dumps(q.get("tags", []), ensure_ascii=False),
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_questions(
    domain_ids: Optional[list[int]] = None,
    difficulty: Optional[int] = None,
    exclude_ids: Optional[list[int]] = None,
    limit: int = 50,
) -> list[dict]:
    conn = get_connection()
    conditions = ["is_active = 1"]
    params: list = []

    if domain_ids:
        placeholders = ",".join("?" * len(domain_ids))
        conditions.append(f"domain_id IN ({placeholders})")
        params.extend(domain_ids)
    if difficulty:
        conditions.append("difficulty = ?")
        params.append(difficulty)
    if exclude_ids:
        placeholders = ",".join("?" * len(exclude_ids))
        conditions.append(f"id NOT IN ({placeholders})")
        params.extend(exclude_ids)

    where = " AND ".join(conditions)
    cur = conn.execute(
        f"SELECT * FROM questions WHERE {where} ORDER BY RANDOM() LIMIT ?",
        params + [limit],
    )
    return [dict(row) for row in cur.fetchall()]


def get_question_by_id(question_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_mastered_question_ids() -> list[int]:
    """返回至少答对过一次的题目 ID 列表（用于过滤已掌握题目）"""
    conn = get_connection()
    cur = conn.execute(
        "SELECT DISTINCT question_id FROM answer_records WHERE is_correct = 1"
    )
    return [row["question_id"] for row in cur.fetchall()]


def count_questions_by_domain() -> dict[int, int]:
    conn = get_connection()
    cur = conn.execute(
        "SELECT domain_id, COUNT(*) as cnt FROM questions WHERE is_active=1 GROUP BY domain_id"
    )
    return {row["domain_id"]: row["cnt"] for row in cur.fetchall()}


# ───────────── 会话操作 ─────────────

def create_session(session_type: str, domain_filter: list[int] = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO study_sessions (session_type, domain_filter) VALUES (?,?)",
        (session_type, json.dumps(domain_filter or [])),
    )
    conn.commit()
    return cur.lastrowid


def finish_session(
    session_id: int,
    total: int,
    correct: int,
    duration_sec: int,
    exam_score: Optional[float] = None,
) -> None:
    conn = get_connection()
    conn.execute(
        """UPDATE study_sessions SET
           ended_at=CURRENT_TIMESTAMP, duration_seconds=?, total_questions=?,
           correct_count=?, is_completed=1, exam_score=?
           WHERE id=?""",
        (duration_sec, total, correct, exam_score, session_id),
    )
    conn.commit()


# ───────────── 答题记录 ─────────────

def record_answer(
    session_id: int,
    question_id: int,
    domain_id: int,
    subdomain: str,
    difficulty: int,
    user_answer: str,
    correct_answer: str,
    is_correct: bool,
    time_spent: int,
) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO answer_records
           (session_id, question_id, domain_id, subdomain, difficulty,
            user_answer, correct_answer, is_correct, time_spent_sec)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (session_id, question_id, domain_id, subdomain, difficulty,
         user_answer, correct_answer, int(is_correct), time_spent),
    )
    # 更新域统计
    _update_domain_stats(conn, domain_id, is_correct, time_spent)
    conn.commit()


def _update_domain_stats(conn: sqlite3.Connection, domain_id: int, is_correct: bool, time_spent: int) -> None:
    conn.execute(
        """UPDATE domain_stats SET
           total_attempts = total_attempts + 1,
           correct_count = correct_count + ?,
           accuracy_rate = CAST(correct_count + ? AS REAL) / (total_attempts + 1),
           avg_time_sec = (avg_time_sec * total_attempts + ?) / (total_attempts + 1),
           last_practiced = CURRENT_TIMESTAMP,
           updated_at = CURRENT_TIMESTAMP
           WHERE domain_id = ?""",
        (int(is_correct), int(is_correct), time_spent, domain_id),
    )


# ───────────── 域统计 ─────────────

def get_domain_stats(domain_id: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    if domain_id:
        cur = conn.execute("SELECT * FROM domain_stats WHERE domain_id=?", (domain_id,))
        row = cur.fetchone()
        return [dict(row)] if row else []
    cur = conn.execute("SELECT * FROM domain_stats ORDER BY domain_id")
    return [dict(row) for row in cur.fetchall()]


def get_recent_wrong_questions(days: int = 14, limit: int = 50) -> list[dict]:
    conn = get_connection()
    cur = conn.execute(
        """SELECT ar.*, q.question, q.option_a, q.option_b, q.option_c, q.option_d,
                  q.explanation, q.subdomain as q_subdomain
           FROM answer_records ar
           JOIN questions q ON ar.question_id = q.id
           WHERE ar.is_correct = 0
             AND ar.answered_at >= datetime('now', ?)
           ORDER BY ar.answered_at DESC
           LIMIT ?""",
        (f"-{days} days", limit),
    )
    return [dict(row) for row in cur.fetchall()]


# ───────────── 每日进度 ─────────────

def update_daily_progress(questions_done: int, correct: int, minutes: int) -> None:
    conn = get_connection()
    today = date.today().isoformat()
    conn.execute(
        """INSERT INTO daily_progress (study_date, questions_done, correct_count, minutes_studied, sessions_count)
           VALUES (?, ?, ?, ?, 1)
           ON CONFLICT(study_date) DO UPDATE SET
               questions_done = questions_done + excluded.questions_done,
               correct_count  = correct_count  + excluded.correct_count,
               minutes_studied= minutes_studied + excluded.minutes_studied,
               sessions_count = sessions_count + 1""",
        (today, questions_done, correct, minutes),
    )
    conn.commit()


def get_daily_progress(days: int = 7) -> list[dict]:
    conn = get_connection()
    cur = conn.execute(
        "SELECT * FROM daily_progress ORDER BY study_date DESC LIMIT ?", (days,)
    )
    return [dict(row) for row in cur.fetchall()]


# ───────────── 薄弱点记录 ─────────────

def upsert_weakness(domain_id: int, subdomain: str, score: float, q_count: int, err_count: int, suggestion: str = "") -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO weakness_records (domain_id, subdomain, weakness_score, question_count, error_count, ai_suggestion)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(domain_id, subdomain) DO UPDATE SET
               weakness_score = excluded.weakness_score,
               question_count = excluded.question_count,
               error_count    = excluded.error_count,
               ai_suggestion  = excluded.ai_suggestion,
               identified_at  = CURRENT_TIMESTAMP""",
        (domain_id, subdomain or "综合", score, q_count, err_count, suggestion),
    )
    conn.commit()


def get_weaknesses(threshold: float = 70.0) -> list[dict]:
    conn = get_connection()
    cur = conn.execute(
        "SELECT * FROM weakness_records WHERE weakness_score < ? AND resolved_at IS NULL ORDER BY weakness_score ASC",
        (threshold,),
    )
    return [dict(row) for row in cur.fetchall()]


# ───────────── 学习计划 ─────────────

def save_study_plan(plan_days: list[dict]) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM study_plan")
    for day in plan_days:
        conn.execute(
            """INSERT INTO study_plan
               (day_number, target_date, domain_id, subdomain_focus,
                objectives, practice_count, is_exam_day, day_type)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                day["day"], day.get("date"), day["domain_id"],
                day.get("focus", ""), json.dumps(day.get("objectives", []), ensure_ascii=False),
                day.get("practice_count", 30), int(day.get("is_exam_day", False)),
                day.get("day_type", "study"),
            ),
        )
    conn.commit()


def get_plan_day(day_number: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM study_plan WHERE day_number=?", (day_number,))
    row = cur.fetchone()
    return dict(row) if row else None


def get_current_day_number(start_date_str: Optional[str] = None) -> int:
    conn = get_connection()
    cur = conn.execute("SELECT target_date FROM study_plan WHERE day_number=1")
    row = cur.fetchone()
    if not row or not row["target_date"]:
        return 1
    start = date.fromisoformat(row["target_date"])
    delta = (date.today() - start).days + 1
    return max(1, min(delta, 50))


def mark_plan_day_complete(day_number: int) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE study_plan SET is_completed=1, completed_at=CURRENT_TIMESTAMP WHERE day_number=?",
        (day_number,),
    )
    conn.commit()


def get_all_plan_days() -> list[dict]:
    conn = get_connection()
    cur = conn.execute("SELECT * FROM study_plan ORDER BY day_number")
    return [dict(row) for row in cur.fetchall()]


# ───────────── 知识点内容缓存 ─────────────

def get_cached_study_content(domain_id: int, topic: str) -> Optional[str]:
    cache_key = f"{domain_id}|{topic}"
    conn = get_connection()
    cur = conn.execute(
        "SELECT content FROM study_content_cache WHERE cache_key = ?", (cache_key,)
    )
    row = cur.fetchone()
    return row["content"] if row else None


def save_study_content(domain_id: int, topic: str, content: str) -> None:
    cache_key = f"{domain_id}|{topic}"
    conn = get_connection()
    conn.execute(
        """INSERT INTO study_content_cache (cache_key, domain_id, topic, content, char_count)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(cache_key) DO UPDATE SET
               content    = excluded.content,
               char_count = excluded.char_count,
               updated_at = CURRENT_TIMESTAMP""",
        (cache_key, domain_id, topic, content, len(content)),
    )
    conn.commit()


def get_study_content_stats() -> list[dict]:
    """按域统计知识点学习情况（来源：study_content_cache）"""
    conn = get_connection()
    cur = conn.execute(
        """SELECT domain_id,
                  COUNT(*)        AS topics_studied,
                  SUM(char_count) AS total_chars,
                  MAX(updated_at) AS last_studied_at
           FROM study_content_cache
           GROUP BY domain_id
           ORDER BY domain_id"""
    )
    return [dict(row) for row in cur.fetchall()]


def count_questions_by_subdomain(domain_id: int, subdomain: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "SELECT COUNT(*) as cnt FROM questions WHERE domain_id=? AND subdomain=? AND is_active=1",
        (domain_id, subdomain),
    )
    row = cur.fetchone()
    return row["cnt"] if row else 0


def get_exam_sessions(limit: int = 10) -> list[dict]:
    conn = get_connection()
    cur = conn.execute(
        """SELECT * FROM study_sessions
           WHERE session_type='exam' AND is_completed=1
           ORDER BY started_at DESC LIMIT ?""",
        (limit,),
    )
    return [dict(row) for row in cur.fetchall()]
