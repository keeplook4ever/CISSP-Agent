"""练习模式：选域刷题，即时反馈"""
from __future__ import annotations

import time

from rich.console import Console

from config.settings import settings
from database.models import (
    get_questions_balanced,
    create_session, finish_session, record_answer, update_daily_progress,
    get_wrong_questions, get_ai_unattempted_questions, get_session_wrong_questions,
)
from ui.cli.display import print_question, print_result, get_user_answer, shuffle_question
from ui.cli.tables import print_session_summary, print_wrong_review
from ui.cli.menus import select_domain, select_difficulty
from analysis.weakness_detector import detect_and_save_weaknesses

console = Console()


def run_practice(domain_ids: list[int] = None, difficulty: int = None, count: int = None) -> None:
    """运行练习模式"""
    # 选择配置
    if domain_ids is None:
        domain_ids = select_domain(multi=True)
    if difficulty is None:
        difficulty = select_difficulty()
    if count is None:
        count = _select_count()

    # 加载题目：历史错题优先，不足时补充 AI 新题
    questions = _load_practice_questions(domain_ids, difficulty, count)

    count = len(questions)
    session_id = create_session("practice", domain_ids)
    start_time = time.time()
    correct_count = 0
    answered = 0

    console.print(f"\n  [bold]开始练习：{count} 题[/bold]  按 Ctrl+C 可提前结束\n")

    try:
        for i, q in enumerate(questions, 1):
            q = shuffle_question(q)
            q_start = time.time()
            print_question(q, i, count)
            user_ans = get_user_answer()
            time_spent = int(time.time() - q_start)

            correct = q.get("correct", "")
            is_correct = user_ans == correct

            if is_correct:
                correct_count += 1

            print_result(q, user_ans, is_correct)
            answered += 1

            # 记录答题
            record_answer(
                session_id=session_id,
                question_id=q["id"],
                domain_id=q.get("domain_id", 0),
                subdomain=q.get("subdomain", ""),
                difficulty=q.get("difficulty", 2),
                user_answer=user_ans,
                correct_answer=correct,
                is_correct=is_correct,
                time_spent=time_spent,
            )

            if i < count:
                try:
                    console.input("  [dim]按回车继续...[/dim]")
                except (EOFError, KeyboardInterrupt):
                    break

    except KeyboardInterrupt:
        console.print("\n  [yellow]练习已中断[/yellow]")

    # 结束会话
    duration = int(time.time() - start_time)
    finish_session(session_id, answered, correct_count, duration)
    update_daily_progress(answered, correct_count, duration // 60)

    print_session_summary(answered, correct_count, duration, "练习")

    # 错题回顾
    if answered > 0 and correct_count < answered:
        wrong_qs = get_session_wrong_questions(session_id)
        print_wrong_review(wrong_qs)

    # 薄弱点检测
    if answered > 0:
        weaknesses = detect_and_save_weaknesses()
        if weaknesses:
            console.print(f"  [yellow]⚠️  发现 {len(weaknesses)} 个薄弱点，建议重点复习[/yellow]")
            for w in weaknesses[:3]:
                console.print(
                    f"    · 域{w['domain_id']} {w['subdomain']}  "
                    f"掌握分 [red]{w['weakness_score']:.0f}[/red]"
                )


def _select_count() -> int:
    """选择练习题数"""
    console.print(f"\n  练习题数 [dim]（默认{settings.DEFAULT_PRACTICE_COUNT}）[/dim]：", end="")
    try:
        raw = console.input("").strip()
        val = int(raw) if raw else settings.DEFAULT_PRACTICE_COUNT
        return max(1, min(val, 200))
    except ValueError:
        return settings.DEFAULT_PRACTICE_COUNT


def _load_practice_questions(
    domain_ids: list[int] | None,
    difficulty: int | None,
    count: int,
) -> list[dict]:
    """练习题目加载：历史错题优先，不足时补充 AI 新题，最后兜底本地未做题"""
    import random as _random
    excl: list[int] = []

    # 1. 历史错题
    wrong = get_wrong_questions(domain_ids=domain_ids, difficulty=difficulty, limit=count + 10)
    picked: list[dict] = _random.sample(wrong, min(count, len(wrong))) if wrong else []
    excl += [q["id"] for q in picked]

    # 2. 不足时取 AI 已生成但未做过的题
    shortage = count - len(picked)
    if shortage > 0:
        ai_qs = get_ai_unattempted_questions(
            domain_ids=domain_ids, difficulty=difficulty,
            exclude_ids=excl or None, limit=shortage + 10,
        )
        extra = _random.sample(ai_qs, min(shortage, len(ai_qs))) if ai_qs else []
        picked.extend(extra)
        excl += [q["id"] for q in extra]

    # 3. 仍不足且在线时，调用 AI 生成新题再取
    shortage = count - len(picked)
    if shortage > 0 and settings.is_online():
        try:
            from ai.question_generator import generate_questions
            domain_id = _random.choice(domain_ids) if domain_ids else 1
            console.print(f"  [dim]AI 生成补充题目中...[/dim]")
            generate_questions(
                domain_id,
                difficulty=difficulty,
                count=shortage + 3,
                min_difficulty=settings.AI_GEN_MIN_DIFFICULTY,
            )
        except Exception:
            pass
        ai_qs2 = get_ai_unattempted_questions(
            domain_ids=domain_ids, difficulty=difficulty,
            exclude_ids=excl or None, limit=shortage + 10,
        )
        extra2 = _random.sample(ai_qs2, min(shortage, len(ai_qs2))) if ai_qs2 else []
        picked.extend(extra2)
        excl += [q["id"] for q in extra2]

    # 4. 最终兜底：本地未做过的题（不含答对过的）
    shortage = count - len(picked)
    if shortage > 0:
        fallback = get_questions_balanced(
            domain_ids=domain_ids, difficulty=difficulty,
            exclude_ids=excl or None, limit=shortage + 10, new_ratio=1.0,
        )
        extra3 = _random.sample(fallback, min(shortage, len(fallback))) if fallback else []
        picked.extend(extra3)

    _random.shuffle(picked)
    return picked
