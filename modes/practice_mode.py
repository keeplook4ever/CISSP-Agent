"""练习模式：选域刷题，即时反馈"""
from __future__ import annotations

import time

from rich.console import Console

from config.settings import settings
from database.models import (
    get_questions, get_questions_balanced, count_unattempted_by_domain,
    create_session, finish_session, record_answer, update_daily_progress,
)
from ui.cli.display import print_question, print_result, get_user_answer, shuffle_question
from ui.cli.tables import print_session_summary
from ui.cli.menus import select_domain, select_difficulty, confirm
from analysis.weakness_detector import detect_and_save_weaknesses
from ai.answer_analyzer import explain_answer

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

    # 加载题目（80%新题 + 20%历史错题，不足时自动回退全量）
    questions = get_questions_balanced(
        domain_ids=domain_ids,
        difficulty=difficulty,
        limit=count,
        new_ratio=settings.QUESTION_NEW_RATIO,
    )

    if not questions:
        console.print("  [red]题库中暂无符合条件的题目，请先运行 init 导入题库[/red]")
        return

    # 某域新题已做完时，联网补充（难度 ≥ 中等）
    if len(questions) < count and settings.is_online():
        for did in (domain_ids or []):
            if count_unattempted_by_domain(did) == 0:
                console.print(f"  [dim]域{did}新题已做完，AI 生成补充中...[/dim]")
                _try_generate_extra([did], difficulty, 10, questions)
        # 补充后重新取题
        questions = get_questions_balanced(
            domain_ids=domain_ids,
            difficulty=difficulty,
            limit=count,
            new_ratio=settings.QUESTION_NEW_RATIO,
        )

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

            print_result(q, user_ans, is_correct, show_explanation=not is_correct)
            answered += 1

            # AI 深度解析（可选）
            if not is_correct and settings.is_online():
                if confirm("是否获取 AI 深度解析？"):
                    console.print("\n  [dim]AI 解析中...[/dim]")
                    explain_answer(q, user_ans, on_chunk=lambda t: console.print(t, end=""))
                    console.print()

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


def _try_generate_extra(domain_ids, difficulty, needed, existing):
    """AI 生成补充题目（导入但不加入本次 existing 列表），难度不低于中等"""
    try:
        from ai.question_generator import generate_questions
        import random
        domain_id = random.choice(domain_ids)
        generate_questions(
            domain_id,
            difficulty=difficulty,
            count=needed,
            min_difficulty=settings.AI_GEN_MIN_DIFFICULTY,
        )
    except Exception:
        pass
