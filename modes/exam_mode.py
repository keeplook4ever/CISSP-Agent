"""模拟考试模式（简化 CAT 自适应）"""
from __future__ import annotations

import random
import time

from rich.console import Console
from rich.panel import Panel

from config.settings import settings
from config.domains import DOMAINS
from database.models import (
    create_session, finish_session, record_answer, update_daily_progress,
    get_ai_unattempted_questions, get_session_wrong_questions,
)
from ui.cli.display import print_question, print_result, get_user_answer
from ui.cli.tables import print_session_summary, print_wrong_review

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
            f"  正确率：{acc*100:.1f}%  通过线：{settings.EXAM_PASS_SCORE}分",
            title="📊 考试结果",
            border_style="green" if passed else "red",
        )
    )

    # 错题回顾
    if answered > 0 and correct_count < answered:
        wrong_qs = get_session_wrong_questions(session_id)
        print_wrong_review(wrong_qs)


def _load_exam_questions() -> list[dict]:
    """考试模式：100% 使用 AI 联网生成的、从未做过的题目。
    各域题量不足时自动调用 Claude 补充生成，直到凑齐目标数量。"""
    from ai.question_generator import generate_questions
    from config.domains import DOMAINS
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

    if not settings.is_online():
        console.print(
            "  [red]考试模式需要网络连接以获取全新 AI 题目，"
            "请检查 ANTHROPIC_API_KEY 配置[/red]"
        )
        return []

    all_questions = []
    total_domains = len(DOMAIN_ALLOCATION)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[cyan]{task.completed}/{task.total}[/cyan] 域"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        overall = progress.add_task("  准备题库...", total=total_domains)

        for domain_id, target in DOMAIN_ALLOCATION.items():
            domain = DOMAINS.get(domain_id, {})
            domain_name = domain.get("name", f"域{domain_id}")

            progress.update(overall, description=f"  [bold]域{domain_id}[/bold] {domain_name}")

            # 1. 查询当前库中未做过的 AI 题
            available = get_ai_unattempted_questions(
                domain_ids=[domain_id], limit=target + 30
            )
            shortage = target - len(available)

            # 2. 不足时联网生成新题（force=True 绕过子域阈值限制）
            if shortage > 0:
                subdomains = domain.get("subdomains", [domain.get("name", f"域{domain_id}")])
                generated_total = 0
                sub_idx = 0
                consecutive_failures = 0

                gen_task = progress.add_task(
                    f"    ↳ AI 生成中 (0/{shortage})",
                    total=shortage,
                )

                while generated_total < shortage and consecutive_failures < len(subdomains):
                    sub = subdomains[sub_idx % len(subdomains)]
                    batch = min(5, shortage - generated_total + 2)

                    progress.update(
                        gen_task,
                        description=f"    ↳ [{sub[:20]}] 生成 {generated_total}/{shortage}...",
                    )

                    new_qs = generate_questions(
                        domain_id, sub, count=batch,
                        min_difficulty=settings.AI_GEN_MIN_DIFFICULTY,
                        force=True,
                    )
                    if new_qs:
                        generated_total += len(new_qs)
                        consecutive_failures = 0
                        progress.update(gen_task, completed=min(generated_total, shortage))
                    else:
                        consecutive_failures += 1
                    sub_idx += 1

                progress.remove_task(gen_task)

                if generated_total == 0:
                    console.print(f"  [yellow]域{domain_id}: API 无响应，跳过该域[/yellow]")
                    progress.advance(overall)
                    continue

                # 重新获取（含刚生成的新题）
                available = get_ai_unattempted_questions(
                    domain_ids=[domain_id], limit=target + 30
                )

            if not available:
                console.print(f"  [yellow]域{domain_id}: 无可用新题，跳过[/yellow]")
                progress.advance(overall)
                continue

            # 3. 按难度比例选取（40% 易 / 40% 中 / 20% 难），不足时补全
            selected = _select_by_difficulty(available, target)
            console.print(
                f"  [green]✓[/green] 域{domain_id} {domain_name}：{len(selected)} 道题就绪"
                + (f" [dim](含 {min(shortage, len(selected))} 道新生成)[/dim]" if shortage > 0 else "")
            )
            all_questions.extend(selected)
            progress.advance(overall)

    random.shuffle(all_questions)
    return all_questions


def _select_by_difficulty(pool: list[dict], target: int) -> list[dict]:
    """按 40/40/20 难度比例从题池选取，总量不足时用剩余题目补全。"""
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

    if len(selected) < target:
        used_ids = {q["id"] for q in selected}
        remaining = [q for q in pool if q["id"] not in used_ids]
        random.shuffle(remaining)
        selected.extend(remaining[: target - len(selected)])

    return selected[:target]
