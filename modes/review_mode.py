"""错题复习模式"""
from __future__ import annotations

import time

from rich.console import Console

from database.models import (
    get_recent_wrong_questions, get_weaknesses,
    create_session, finish_session, record_answer, update_daily_progress,
)
from ui.cli.display import print_question, print_result, get_user_answer
from ui.cli.tables import print_session_summary, print_weakness_table
from analysis.weakness_detector import detect_and_save_weaknesses
from config.settings import settings
from ai.weakness_analyzer import analyze_weaknesses
from database.models import get_domain_stats

console = Console()


def run_review() -> None:
    """运行错题复习模式"""
    console.print("\n  [bold]错题复习 & 薄弱点强化[/bold]\n")

    # 显示当前薄弱点
    weaknesses = detect_and_save_weaknesses()
    print_weakness_table(weaknesses)

    # AI 薄弱点分析
    if weaknesses and settings.is_online():
        console.print("\n  [dim]正在生成 AI 薄弱点分析...[/dim]")
        stats = get_domain_stats()
        wrong = get_recent_wrong_questions(days=30, limit=20)
        console.print("\n" + "─" * 50)
        analyze_weaknesses(stats, wrong, on_chunk=lambda t: console.print(t, end=""))
        console.print("\n" + "─" * 50 + "\n")

    # 选择复习方式
    console.print("  复习方式：")
    console.print("  [dim]1[/dim]  近14天错题（最多50题）")
    console.print("  [dim]2[/dim]  薄弱域专项练习")
    console.print("  [dim]0[/dim]  返回")

    try:
        choice = console.input("\n  [cyan]请选择：[/cyan]").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "1":
        _review_wrong_questions()
    elif choice == "2":
        _review_weak_domains(weaknesses)


def _review_wrong_questions() -> None:
    """复习近期错题"""
    wrong = get_recent_wrong_questions(days=14, limit=50)
    if not wrong:
        console.print("  [green]近14天没有错题，继续加油！[/green]")
        return

    console.print(f"\n  共 {len(wrong)} 道错题，开始复习\n")
    _run_review_session(wrong, "错题复习")


def _review_weak_domains(weaknesses: list[dict]) -> None:
    """薄弱域专项练习"""
    if not weaknesses:
        console.print("  [green]暂无明显薄弱域[/green]")
        return

    weak_domain_ids = list({w["domain_id"] for w in weaknesses})

    from database.models import get_questions
    questions = get_questions(domain_ids=weak_domain_ids, limit=20)
    if not questions:
        console.print("  [yellow]薄弱域暂无题目[/yellow]")
        return

    console.print(f"\n  薄弱域专项：{len(questions)} 道题\n")
    _run_review_session(questions, "薄弱点强化")


def _run_review_session(questions: list[dict], session_label: str) -> None:
    """通用复习会话"""
    session_id = create_session("review")
    start_time = time.time()
    correct_count = 0
    answered = 0

    try:
        for i, q in enumerate(questions, 1):
            q_start = time.time()
            print_question(q, i, len(questions))
            user_ans = get_user_answer()
            time_spent = int(time.time() - q_start)

            correct = q.get("correct", "")
            is_correct = user_ans == correct
            if is_correct:
                correct_count += 1

            print_result(q, user_ans, is_correct, show_explanation=not is_correct)
            answered += 1

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

            if i < len(questions):
                try:
                    console.input("  [dim]按回车继续...[/dim]")
                except (EOFError, KeyboardInterrupt):
                    break

    except KeyboardInterrupt:
        pass

    duration = int(time.time() - start_time)
    finish_session(session_id, answered, correct_count, duration)
    update_daily_progress(answered, correct_count, duration // 60)
    print_session_summary(answered, correct_count, duration, session_label)
