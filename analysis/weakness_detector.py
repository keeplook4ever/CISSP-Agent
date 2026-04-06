"""多维度薄弱点计算"""
from __future__ import annotations

from database.models import get_domain_stats, get_recent_wrong_questions, upsert_weakness
from config.settings import settings


def compute_weakness_score(
    correct: int,
    total: int,
    avg_time: float,
    expected_time: float = 90.0,
) -> float:
    """
    综合掌握分（0-100，越低越弱）
    正确率权重60%，用时权重20%，其他20%（预留趋势分）
    """
    if total == 0:
        return 100.0  # 无数据不标记薄弱

    acc_score = (correct / total) * 100 * 0.6

    # 用时分：超出预期时间越多扣分越多
    if avg_time <= expected_time:
        time_score = 20.0
    else:
        over_ratio = min((avg_time - expected_time) / expected_time, 1.0)
        time_score = 20.0 * (1 - over_ratio)

    base_score = 20.0  # 基础分

    return round(acc_score + time_score + base_score, 1)


def detect_and_save_weaknesses() -> list[dict]:
    """计算所有子域薄弱点并存储，返回薄弱点列表"""
    from database.connection import get_connection
    conn = get_connection()

    # 按子域聚合答题记录
    cur = conn.execute(
        """SELECT domain_id, subdomain,
                  COUNT(*) as total,
                  SUM(is_correct) as correct,
                  AVG(time_spent_sec) as avg_time
           FROM answer_records
           GROUP BY domain_id, subdomain"""
    )
    rows = cur.fetchall()

    weaknesses = []
    for row in rows:
        domain_id = row["domain_id"]
        subdomain = row["subdomain"] or "综合"
        total = row["total"] or 0
        correct = row["correct"] or 0
        avg_time = row["avg_time"] or 0

        score = compute_weakness_score(correct, total, avg_time)
        upsert_weakness(
            domain_id=domain_id,
            subdomain=subdomain,
            score=score,
            q_count=total,
            err_count=total - correct,
        )

        if score < settings.WEAKNESS_THRESHOLD * 100:
            weaknesses.append({
                "domain_id": domain_id,
                "subdomain": subdomain,
                "weakness_score": score,
                "question_count": total,
                "error_count": total - correct,
            })

    return sorted(weaknesses, key=lambda x: x["weakness_score"])
