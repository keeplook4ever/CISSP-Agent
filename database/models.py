"""数据库 CRUD 操作封装"""
import json
import sqlite3
from datetime import date, datetime
from typing import Optional

from database.connection import get_connection
from database.player_manager import get_current_player_id


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
    """返回当前玩家至少答对过一次的题目 ID 列表"""
    conn = get_connection()
    pid = get_current_player_id()
    cur = conn.execute(
        """SELECT DISTINCT ar.question_id FROM answer_records ar
           JOIN study_sessions ss ON ar.session_id = ss.id
           WHERE ar.is_correct = 1 AND ss.player_id = ?""",
        (pid,),
    )
    return [row["question_id"] for row in cur.fetchall()]


def get_questions_balanced(
    domain_ids: Optional[list[int]] = None,
    difficulty: Optional[int] = None,
    exclude_ids: Optional[list[int]] = None,
    limit: int = 20,
    new_ratio: float = 0.8,
) -> list[dict]:
    """按 new_ratio/wrong_ratio 出题（按当前玩家答题记录过滤）"""
    import random as _random
    conn = get_connection()
    pid = get_current_player_id()
    n_new = max(1, int(limit * new_ratio))
    n_wrong = limit - n_new

    base_conds = ["q.is_active = 1"]
    base_params: list = []
    if domain_ids:
        ph = ",".join("?" * len(domain_ids))
        base_conds.append(f"q.domain_id IN ({ph})")
        base_params.extend(domain_ids)
    if difficulty is not None:
        base_conds.append("q.difficulty = ?")
        base_params.append(difficulty)
    if exclude_ids:
        ph = ",".join("?" * len(exclude_ids))
        base_conds.append(f"q.id NOT IN ({ph})")
        base_params.extend(exclude_ids)

    new_qs = _fetch_balanced(
        conn, base_conds, base_params, pid,
        extra="(qs.question_id IS NULL OR qs.is_attempted = 0)",
        use_join=True,
        limit=n_new + 10,
    )
    wrong_qs = _fetch_balanced(
        conn, base_conds, base_params, pid,
        extra="qs.last_result = 0",
        use_join=True,
        limit=n_wrong + 10,
        extra_exclude=[q["id"] for q in new_qs],
    )

    selected = (
        _random.sample(new_qs, min(n_new, len(new_qs)))
        + _random.sample(wrong_qs, min(n_wrong, len(wrong_qs)))
    )

    shortage = limit - len(selected)
    if shortage > 0:
        have_ids = [q["id"] for q in selected]
        fallback = _fetch_balanced(
            conn, base_conds, base_params, pid,
            extra=None,
            use_join=False,
            limit=shortage + 10,
            extra_exclude=have_ids,
        )
        selected.extend(_random.sample(fallback, min(shortage, len(fallback))))

    _random.shuffle(selected)
    return selected[:limit]


def _fetch_balanced(
    conn,
    base_conds: list,
    base_params: list,
    player_id: int,
    extra: Optional[str],
    use_join: bool,
    limit: int,
    extra_exclude: Optional[list[int]] = None,
) -> list[dict]:
    conds = list(base_conds)
    params = list(base_params)
    if extra_exclude:
        ph = ",".join("?" * len(extra_exclude))
        conds.append(f"q.id NOT IN ({ph})")
        params.extend(extra_exclude)
    if extra:
        conds.append(extra)
    where = " AND ".join(conds)
    if use_join:
        # JOIN 条件加入 player_id，使 LEFT JOIN 对当前玩家透明
        sql = (
            "SELECT q.* FROM questions q "
            f"LEFT JOIN question_stats qs ON q.id = qs.question_id AND qs.player_id = ? "
            f"WHERE {where} ORDER BY RANDOM() LIMIT ?"
        )
        cur = conn.execute(sql, [player_id] + params + [limit])
    else:
        sql = f"SELECT q.* FROM questions q WHERE {where} ORDER BY RANDOM() LIMIT ?"
        cur = conn.execute(sql, params + [limit])
    return [dict(row) for row in cur.fetchall()]


def get_wrong_questions(
    domain_ids: Optional[list[int]] = None,
    difficulty: Optional[int] = None,
    exclude_ids: Optional[list[int]] = None,
    limit: int = 50,
) -> list[dict]:
    """返回当前玩家历史错题（最近一次作答结果为错：last_result=0）"""
    conn = get_connection()
    pid = get_current_player_id()
    conds = ["q.is_active = 1", "qs.last_result = 0", "qs.player_id = ?"]
    params: list = [pid]
    if domain_ids:
        ph = ",".join("?" * len(domain_ids))
        conds.append(f"q.domain_id IN ({ph})")
        params.extend(domain_ids)
    if difficulty is not None:
        conds.append("q.difficulty = ?")
        params.append(difficulty)
    if exclude_ids:
        ph = ",".join("?" * len(exclude_ids))
        conds.append(f"q.id NOT IN ({ph})")
        params.extend(exclude_ids)
    where = " AND ".join(conds)
    cur = conn.execute(
        f"SELECT q.* FROM questions q "
        f"JOIN question_stats qs ON q.id = qs.question_id "
        f"WHERE {where} ORDER BY RANDOM() LIMIT ?",
        params + [limit],
    )
    return [dict(row) for row in cur.fetchall()]


def get_ai_unattempted_questions(
    domain_ids: Optional[list[int]] = None,
    difficulty: Optional[int] = None,
    exclude_ids: Optional[list[int]] = None,
    limit: int = 50,
) -> list[dict]:
    """返回 AI 生成且当前玩家从未作答的题目"""
    conn = get_connection()
    pid = get_current_player_id()
    conds = [
        "q.is_active = 1",
        "q.source = 'claude'",
        "(qs.question_id IS NULL OR qs.is_attempted = 0)",
    ]
    params: list = []
    if domain_ids:
        ph = ",".join("?" * len(domain_ids))
        conds.append(f"q.domain_id IN ({ph})")
        params.extend(domain_ids)
    if difficulty is not None:
        conds.append("q.difficulty = ?")
        params.append(difficulty)
    if exclude_ids:
        ph = ",".join("?" * len(exclude_ids))
        conds.append(f"q.id NOT IN ({ph})")
        params.extend(exclude_ids)
    where = " AND ".join(conds)
    cur = conn.execute(
        f"SELECT q.* FROM questions q "
        f"LEFT JOIN question_stats qs ON q.id = qs.question_id AND qs.player_id = ? "
        f"WHERE {where} ORDER BY RANDOM() LIMIT ?",
        [pid] + params + [limit],
    )
    return [dict(row) for row in cur.fetchall()]


def count_unattempted_by_domain(domain_id: int) -> int:
    """返回当前玩家在某域未做过的题目数量"""
    conn = get_connection()
    pid = get_current_player_id()
    cur = conn.execute(
        """SELECT COUNT(*) as cnt FROM questions q
           LEFT JOIN question_stats qs ON q.id = qs.question_id AND qs.player_id = ?
           WHERE q.domain_id = ? AND q.is_active = 1
             AND (qs.question_id IS NULL OR qs.is_attempted = 0)""",
        (pid, domain_id),
    )
    row = cur.fetchone()
    return row["cnt"] if row else 0


def count_questions_by_domain() -> dict[int, int]:
    conn = get_connection()
    cur = conn.execute(
        "SELECT domain_id, COUNT(*) as cnt FROM questions WHERE is_active=1 GROUP BY domain_id"
    )
    return {row["domain_id"]: row["cnt"] for row in cur.fetchall()}


# ───────────── 会话操作 ─────────────

def create_session(session_type: str, domain_filter: list[int] = None) -> int:
    conn = get_connection()
    pid = get_current_player_id()
    cur = conn.execute(
        "INSERT INTO study_sessions (session_type, domain_filter, player_id) VALUES (?,?,?)",
        (session_type, json.dumps(domain_filter or []), pid),
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
    pid = get_current_player_id()
    conn.execute(
        """INSERT INTO answer_records
           (session_id, question_id, domain_id, subdomain, difficulty,
            user_answer, correct_answer, is_correct, time_spent_sec)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (session_id, question_id, domain_id, subdomain, difficulty,
         user_answer, correct_answer, int(is_correct), time_spent),
    )
    _update_domain_stats(conn, pid, domain_id, is_correct, time_spent)
    _upsert_question_stats(conn, pid, question_id, is_correct)
    conn.commit()


def _upsert_question_stats(conn: sqlite3.Connection, player_id: int, question_id: int, is_correct: bool) -> None:
    wrong_delta = 0 if is_correct else 1
    conn.execute(
        """INSERT INTO question_stats
               (player_id, question_id, is_attempted, last_result, last_answered_at,
                attempt_count, correct_count, wrong_count)
           VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP, 1, ?, ?)
           ON CONFLICT(player_id, question_id) DO UPDATE SET
               is_attempted     = 1,
               last_result      = excluded.last_result,
               last_answered_at = CURRENT_TIMESTAMP,
               attempt_count    = attempt_count + 1,
               correct_count    = correct_count + excluded.correct_count,
               wrong_count      = wrong_count + excluded.wrong_count,
               updated_at       = CURRENT_TIMESTAMP""",
        (player_id, question_id, int(is_correct), int(is_correct), wrong_delta),
    )


def _update_domain_stats(conn: sqlite3.Connection, player_id: int, domain_id: int, is_correct: bool, time_spent: int) -> None:
    conn.execute(
        """UPDATE domain_stats SET
           total_attempts = total_attempts + 1,
           correct_count = correct_count + ?,
           accuracy_rate = CAST(correct_count + ? AS REAL) / (total_attempts + 1),
           avg_time_sec = (avg_time_sec * total_attempts + ?) / (total_attempts + 1),
           last_practiced = CURRENT_TIMESTAMP,
           updated_at = CURRENT_TIMESTAMP
           WHERE player_id = ? AND domain_id = ?""",
        (int(is_correct), int(is_correct), time_spent, player_id, domain_id),
    )


# ───────────── 域统计 ─────────────

def get_domain_stats(domain_id: Optional[int] = None) -> list[dict]:
    conn = get_connection()
    pid = get_current_player_id()
    if domain_id:
        cur = conn.execute(
            "SELECT * FROM domain_stats WHERE player_id=? AND domain_id=?",
            (pid, domain_id),
        )
        row = cur.fetchone()
        return [dict(row)] if row else []
    cur = conn.execute(
        "SELECT * FROM domain_stats WHERE player_id=? ORDER BY domain_id",
        (pid,),
    )
    return [dict(row) for row in cur.fetchall()]


def get_recent_wrong_questions(days: int = 14, limit: int = 50) -> list[dict]:
    conn = get_connection()
    pid = get_current_player_id()
    cur = conn.execute(
        """SELECT q.id, q.domain_id, q.subdomain, q.difficulty, q.source,
                  q.question, q.option_a, q.option_b, q.option_c, q.option_d,
                  q.correct, q.explanation, q.tags,
                  ar.user_answer, ar.answered_at
           FROM answer_records ar
           JOIN questions q ON ar.question_id = q.id
           JOIN study_sessions ss ON ar.session_id = ss.id
           WHERE ar.is_correct = 0
             AND ss.player_id = ?
             AND ar.answered_at >= datetime('now', ?)
           ORDER BY ar.answered_at DESC
           LIMIT ?""",
        (pid, f"-{days} days", limit),
    )
    return [dict(row) for row in cur.fetchall()]


# ───────────── 每日进度 ─────────────

def update_daily_progress(questions_done: int, correct: int, minutes: int) -> None:
    conn = get_connection()
    pid = get_current_player_id()
    today = date.today().isoformat()
    conn.execute(
        """INSERT INTO daily_progress (player_id, study_date, questions_done, correct_count, minutes_studied, sessions_count)
           VALUES (?, ?, ?, ?, ?, 1)
           ON CONFLICT(player_id, study_date) DO UPDATE SET
               questions_done  = questions_done  + excluded.questions_done,
               correct_count   = correct_count   + excluded.correct_count,
               minutes_studied = minutes_studied + excluded.minutes_studied,
               sessions_count  = sessions_count  + 1""",
        (pid, today, questions_done, correct, minutes),
    )
    conn.commit()


def get_daily_progress(days: int = 7) -> list[dict]:
    conn = get_connection()
    pid = get_current_player_id()
    cur = conn.execute(
        "SELECT * FROM daily_progress WHERE player_id=? ORDER BY study_date DESC LIMIT ?",
        (pid, days),
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


def get_sprint_pool(domain_ids: Optional[list[int]] = None) -> tuple[list[dict], list[dict]]:
    """获取当前玩家冲刺题池：
    返回 (wrong_questions, unattempted_medium_hard)
    """
    conn = get_connection()
    pid = get_current_player_id()

    conds_w = ["q.is_active = 1", "qs.last_result = 0", "qs.player_id = ?"]
    params_w: list = [pid]
    if domain_ids:
        ph = ",".join("?" * len(domain_ids))
        conds_w.append(f"q.domain_id IN ({ph})")
        params_w.extend(domain_ids)
    where_w = " AND ".join(conds_w)
    cur = conn.execute(
        f"SELECT q.*, qs.wrong_count FROM questions q "
        f"JOIN question_stats qs ON q.id = qs.question_id "
        f"WHERE {where_w} ORDER BY qs.wrong_count DESC, q.difficulty DESC",
        params_w,
    )
    wrong = [dict(row) for row in cur.fetchall()]

    conds_n = [
        "q.is_active = 1",
        "q.difficulty >= 2",
        "(qs.question_id IS NULL OR qs.is_attempted = 0)",
    ]
    params_n: list = []
    if domain_ids:
        ph = ",".join("?" * len(domain_ids))
        conds_n.append(f"q.domain_id IN ({ph})")
        params_n.extend(domain_ids)
    where_n = " AND ".join(conds_n)
    cur = conn.execute(
        f"SELECT q.* FROM questions q "
        f"LEFT JOIN question_stats qs ON q.id = qs.question_id AND qs.player_id = ? "
        f"WHERE {where_n} ORDER BY q.difficulty DESC, RANDOM()",
        [pid] + params_n,
    )
    unattempted = [dict(row) for row in cur.fetchall()]

    return wrong, unattempted


def get_sprint_stats(domain_ids: Optional[list[int]] = None) -> dict:
    """统计冲刺池信息，用于仪表盘展示"""
    wrong, unattempted = get_sprint_pool(domain_ids=domain_ids)
    breakdown: dict[int, dict] = {}
    for q in wrong:
        did = q.get("domain_id", 0)
        breakdown.setdefault(did, {"wrong": 0, "unattempted": 0})
        breakdown[did]["wrong"] += 1
    for q in unattempted:
        did = q.get("domain_id", 0)
        breakdown.setdefault(did, {"wrong": 0, "unattempted": 0})
        breakdown[did]["unattempted"] += 1
    return {
        "wrong_count": len(wrong),
        "unattempted_count": len(unattempted),
        "total": len(wrong) + len(unattempted),
        "domain_breakdown": breakdown,
    }


def get_exam_sessions(limit: int = 10) -> list[dict]:
    conn = get_connection()
    pid = get_current_player_id()
    cur = conn.execute(
        """SELECT * FROM study_sessions
           WHERE session_type='exam' AND is_completed=1 AND player_id=?
           ORDER BY started_at DESC LIMIT ?""",
        (pid, limit),
    )
    return [dict(row) for row in cur.fetchall()]


def get_session_wrong_questions(session_id: int) -> list[dict]:
    """返回指定会话中答错的题目（含题目全量信息），按答题顺序排列"""
    conn = get_connection()
    cur = conn.execute(
        """SELECT q.*, ar.user_answer, ar.correct_answer AS ar_correct
           FROM answer_records ar
           JOIN questions q ON ar.question_id = q.id
           WHERE ar.session_id = ? AND ar.is_correct = 0
           ORDER BY ar.id""",
        (session_id,),
    )
    return [dict(row) for row in cur.fetchall()]
