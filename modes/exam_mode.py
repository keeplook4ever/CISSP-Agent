"""模拟考试模式（简化 CAT 自适应）"""
from __future__ import annotations

import random
import time

from rich.console import Console
from rich.panel import Panel

from config.settings import settings
from config.domains import DOMAINS
from database.models import (
    get_questions_balanced,
    create_session, finish_session, record_answer, update_daily_progress,
    get_wrong_questions, get_ai_unattempted_questions,
)
from ui.cli.display import print_question, print_result, get_user_answer, shuffle_question
from ui.cli.tables import print_session_summary

console = Console()

# 各域题目分配（按权重，共125题）
DOMAIN_ALLOCATION = {
    1: 20, 2: 13, 3: 16, 4: 16,
    5: 16, 6: 15, 7: 16, 8: 13,
}


def run_exam() -> None:
    """运行模拟考试"""
    console.print(
        Panel(
            "  📋 模拟考试规则\n\n"
            f"  · 共 {settings.EXAM_TOTAL_QUESTIONS} 题，限时 {settings.EXAM_TIME_MINUTES} 分钟\n"
            "  · 考试期间不显示答案解析（考后可查看错题）\n"
            "  · 700分为通过线（满分1000分）\n"
            "  · 按 Ctrl+C 可提前交卷\n",
            title="🎯 CISSP 模拟考试",
            border_style="yellow",
        )
    )

    try:
        raw = console.input("  按回车开始考试，输入 q 返回菜单：").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if raw == "q":
        return

    # 按域加载题目
    questions = _load_exam_questions()
    if len(questions) < 10:
        console.print("  [red]题库题目不足，请先完成各域练习或导入更多题目[/red]")
        return

    total = len(questions)
    session_id = create_session("exam", list(DOMAIN_ALLOCATION.keys()))
    start_time = time.time()
    deadline = start_time + settings.EXAM_TIME_MINUTES * 60

    correct_count = 0
    answered = 0

    # CAT 能力估计（-3到+3）
    ability = 0.0

    try:
        for i, q in enumerate(questions, 1):
            # 检查时间
            remaining = deadline - time.time()
            if remaining <= 0:
                console.print("\n  [bold red]⏰ 时间到！自动交卷[/bold red]")
                break

            mins_left = int(remaining // 60)
            secs_left = int(remaining % 60)
            time_hint = f"⏱ 剩余 {mins_left}:{secs_left:02d}"

            q_start = time.time()
            q = shuffle_question(q)
            print_question(q, i, total, show_domain=False)
            user_ans = get_user_answer(timeout_hint=f"[dim]{time_hint}[/dim]")
            time_spent = int(time.time() - q_start)

            correct = q.get("correct", "")
            is_correct = user_ans == correct

            if is_correct:
                correct_count += 1
                ability = min(3.0, ability + 0.3)
            else:
                ability = max(-3.0, ability - 0.2)

            # 考试模式不显示答题正确性与解析
            console.print(
                f"  📝  已作答  {time_hint}\n"
            )
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

    except KeyboardInterrupt:
        console.print("\n  [yellow]提前交卷[/yellow]")

    # 计算分数（简化换算：正确率 * 1000 * 调节系数）
    acc = correct_count / max(answered, 1)
    # 简单线性换算：60%对应700分
    exam_score = min(1000.0, max(0.0, acc * 1000 * 0.85 + ability * 20))

    duration = int(time.time() - start_time)
    finish_session(session_id, answered, correct_count, duration, exam_score)
    update_daily_progress(answered, correct_count, duration // 60)

    print_session_summary(answered, correct_count, duration, "模拟考试")

    passed = exam_score >= settings.EXAM_PASS_SCORE
    result_style = "bold green" if passed else "bold red"
    result_text = "🎉 通过！" if passed else "❌ 未通过，继续加油！"

    console.print(
        Panel(
            f"  换算分数：[{result_style}]{exam_score:.0f}[/{result_style}] / 1000\n"
            f"  [{result_style}]{result_text}[/{result_style}]\n"
            f"  正确率：{acc*100:.1f}%  通过线：{settings.EXAM_PASS_SCORE}分\n\n"
            "  提示：在'错题复习'模式中可查看本次错题解析",
            title="📊 考试结果",
            border_style="green" if passed else "red",
        )
    )


def _load_exam_questions() -> list[dict]:
    """按 80/20 比例从各域加载题目：80% 从未做过的新题 + 20% 历史错题，随机打乱"""
    all_questions = []
    for domain_id, target in DOMAIN_ALLOCATION.items():
        # 严格 80/20 配额
        n_wrong = max(1, round(target * 0.20))
        n_new   = target - n_wrong

        # --- 1. 取错题（严格限制在 n_wrong 以内）---
        wrong_pool = get_wrong_questions(domain_ids=[domain_id], limit=n_wrong + 10)
        wrong_selected = random.sample(wrong_pool, min(n_wrong, len(wrong_pool)))
        excl = [q["id"] for q in wrong_selected]

        # --- 2. 取新题（优先 AI 生成的未做过，再取普通未做过）---
        ai_new = get_ai_unattempted_questions(
            domain_ids=[domain_id], exclude_ids=excl or None, limit=n_new + 20,
        )
        excl += [q["id"] for q in ai_new]

        local_new = get_questions_balanced(
            domain_ids=[domain_id], exclude_ids=excl or None,
            limit=n_new + 20, new_ratio=1.0,
        )
        excl += [q["id"] for q in local_new]

        new_pool = ai_new + local_new
        new_selected = random.sample(new_pool, min(n_new, len(new_pool)))

        pool = wrong_selected + new_selected

        # --- 3. 总量不足时，继续从未做过的题补充（不引入已做对的旧题）---
        if len(pool) < target:
            shortage = target - len(pool)
            extra = get_questions_balanced(
                domain_ids=[domain_id], exclude_ids=excl or None,
                limit=shortage + 20, new_ratio=1.0,
            )
            pool += random.sample(extra, min(shortage, len(extra)))

        # 按难度混合：40%简单，40%中等，20%难
        easy   = [q for q in pool if q.get("difficulty") == 1]
        medium = [q for q in pool if q.get("difficulty") == 2]
        hard   = [q for q in pool if q.get("difficulty") == 3]
        n_easy   = int(target * 0.4)
        n_medium = int(target * 0.4)
        n_hard   = target - n_easy - n_medium

        selected = (
            random.sample(easy,   min(n_easy,   len(easy)))
            + random.sample(medium, min(n_medium, len(medium)))
            + random.sample(hard,   min(n_hard,   len(hard)))
        )
        used_ids = {q["id"] for q in selected}
        remaining = [q for q in pool if q["id"] not in used_ids]
        while len(selected) < target and remaining:
            selected.append(remaining.pop(0))

        actual_wrong = len(wrong_selected)
        actual_new   = len(new_selected)
        print(f"[DEBUG] 域{domain_id}: target={target}, wrong={actual_wrong}({actual_wrong/target*100:.0f}%), new={actual_new}({actual_new/target*100:.0f}%), pool={len(pool)}, selected={len(selected[:target])}")
        all_questions.extend(selected[:target])

    random.shuffle(all_questions)
    return all_questions
