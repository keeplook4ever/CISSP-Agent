"""学习进度追踪"""
from __future__ import annotations

from database.models import (
    get_daily_progress, get_domain_stats, get_exam_sessions,
    get_current_day_number, get_study_content_stats,
)
from config.domains import DOMAINS


def get_overall_progress() -> dict:
    """汇总总体学习进度"""
    stats = get_domain_stats()
    total_attempts = sum(s.get("total_attempts", 0) for s in stats)
    total_correct = sum(s.get("correct_count", 0) for s in stats)
    overall_acc = total_correct / total_attempts if total_attempts else 0.0

    daily = get_daily_progress(days=7)
    total_minutes = sum(d.get("minutes_studied", 0) for d in daily)

    exams = get_exam_sessions(limit=5)
    best_exam = max((e.get("exam_score", 0) for e in exams), default=0)

    current_day = get_current_day_number()

    study_stats = get_study_content_stats()

    return {
        "current_day": current_day,
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "overall_accuracy": overall_acc,
        "minutes_last_7_days": total_minutes,
        "best_exam_score": best_exam,
        "domain_stats": stats,
        "recent_daily": daily,
        "recent_exams": exams,
        "study_content_stats": study_stats,
        "total_topics_studied": sum(s["topics_studied"] for s in study_stats),
    }


def get_domains_needing_attention(threshold: float = 0.70) -> list[dict]:
    """返回正确率低于阈值的域（需要重点关注）"""
    stats = get_domain_stats()
    result = []
    for s in stats:
        if s.get("total_attempts", 0) > 0 and s.get("accuracy_rate", 0) < threshold:
            d = DOMAINS.get(s["domain_id"], {})
            result.append({
                "domain_id": s["domain_id"],
                "name": d.get("name", ""),
                "accuracy": s["accuracy_rate"],
                "total": s["total_attempts"],
            })
    return sorted(result, key=lambda x: x["accuracy"])
