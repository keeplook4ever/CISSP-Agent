"""考前冲刺模式：错题 + 中高难度未做题集中突破"""
from __future__ import annotations

import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from config.domains import DOMAINS
from database.models import (
    get_sprint_pool, get_sprint_stats,
    create_session, finish_session, record_answer, update_daily_progress,
)
from ui.cli.display import print_question, print_result, get_user_answer
from ui.cli.tables import print_session_summary
from analysis.weakness_detector import detect_and_save_weaknesses

console = Console()


def run_sprint() -> None:
    """运行考前冲刺模式"""
    _print_sprint_banner()

    stats = get_sprint_stats()
    _print_sprint_dashboard(stats)

    if stats["total"] == 0:
        console.print(
            Panel(
                "  [bold green]🎉 太棒了！冲刺池已清空，错题全部巩固，中高难度题全部做过！[/bold green]\n"
                "  [dim]建议做一次模拟考试（选项3）检验整体水平[/dim]",
                border_style="green",
            )
        )
        return

    console.print("\n  冲刺选项：")
    console.print("  [bold]1[/bold]  全量冲刺（错题优先 → 高难度 → 中难度）")
    console.print("  [bold]2[/bold]  只做错题（重点巩固，共 "
                  f"[red]{stats['wrong_count']}[/red] 道）")
    console.print("  [bold]3[/bold]  只做中高难度未做题（共 "
                  f"[yellow]{stats['unattempted_count']}[/yellow] 道）")
    console.print("  [bold]0[/bold]  返回主菜单")

    try:
        choice = console.input("\n  [cyan]请选择：[/cyan]").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice not in ("1", "2", "3"):
        return

    wrong, unattempted = get_sprint_pool()

    if choice == "1":
        questions = wrong + unattempted
        label = "全量冲刺"
    elif choice == "2":
        questions = wrong
        label = "错题冲刺"
        if not questions:
            console.print("\n  [green]没有未纠正的错题，全部答对过了！[/green]")
            return
    else:
        questions = unattempted
        label = "中高难度冲刺"
        if not questions:
            console.print("\n  [green]中高难度题已全部做过！[/green]")
            return

    pool_total = len(questions)
    count = _select_sprint_count(pool_total)
    _run_sprint_session(questions[:count], label, pool_total)


def _print_sprint_banner() -> None:
    console.print()
    console.print(
        Panel(
            "[bold red]⚡  CISSP 考前冲刺模式  ⚡[/bold red]\n"
            "[dim]聚焦错题 + 中高难度未做题，答题后即时显示解析，冲刺效率最大化[/dim]",
            border_style="red",
            box=box.DOUBLE_EDGE,
            padding=(0, 4),
        )
    )


def _print_sprint_dashboard(stats: dict) -> None:
    """打印冲刺池概览仪表盘"""
    wrong_cnt = stats["wrong_count"]
    unattempted_cnt = stats["unattempted_count"]
    total = stats["total"]

    overview = (
        f"  错题（需巩固）：  [bold red]{wrong_cnt}[/bold red] 道\n"
        f"  中高难度未做：    [bold yellow]{unattempted_cnt}[/bold yellow] 道\n"
        f"  冲刺池合计：      [bold cyan]{total}[/bold cyan] 道"
    )
    console.print(Panel(overview, title="冲刺池概览", border_style="cyan", box=box.ROUNDED))

    breakdown = stats.get("domain_breakdown", {})
    if not breakdown:
        return

    table = Table(title="各域冲刺题分布", box=box.SIMPLE_HEAVY, border_style="dim")
    table.add_column("域", style="cyan", width=4)
    table.add_column("名称", min_width=14)
    table.add_column("错题", justify="right", style="red")
    table.add_column("未做中高难", justify="right", style="yellow")
    table.add_column("小计", justify="right", style="bold")

    for did in sorted(breakdown.keys()):
        d = DOMAINS.get(did, {})
        b = breakdown[did]
        w = b.get("wrong", 0)
        u = b.get("unattempted", 0)
        table.add_row(
            str(did),
            d.get("name", f"域{did}"),
            str(w) if w else "—",
            str(u) if u else "—",
            str(w + u),
        )
    console.print(table)


def _select_sprint_count(available: int) -> int:
    """选择本次冲刺做题数"""
    half = max(1, available // 2)
    console.print(f"\n  可用题数：[bold]{available}[/bold] 道")
    console.print(f"  建议：今天做 {half} 道，明天做剩余 {available - half} 道")
    console.print(f"\n  输入本次题数（1-{available}），回车=全做：", end="")
    try:
        raw = console.input("").strip()
        val = int(raw) if raw else available
        return max(1, min(val, available))
    except ValueError:
        return available


def _run_sprint_session(questions: list[dict], label: str, pool_total: int) -> None:
    """执行冲刺答题会话"""
    session_id = create_session("sprint")
    start_time = time.time()
    correct_count = 0
    answered = 0
    count = len(questions)

    console.print(
        f"\n  [bold red]⚡ {label}：{count} 题[/bold red]  "
        f"[dim]冲刺池共 {pool_total} 题  ·  每题答完即显示解析[/dim]\n"
    )

    try:
        for i, q in enumerate(questions, 1):
            q_start = time.time()
            print_question(q, i, count)
            user_ans = get_user_answer()
            time_spent = int(time.time() - q_start)

            correct = q.get("correct", "")
            is_correct = user_ans == correct
            if is_correct:
                correct_count += 1

            # 冲刺模式：无论对错都显示解析，强化记忆
            print_result(q, user_ans, is_correct, show_explanation=True)
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

            if i < count:
                done_bar = "█" * (i * 20 // count)
                todo_bar = "░" * (20 - i * 20 // count)
                console.print(
                    f"  [dim][{done_bar}{todo_bar}] {i}/{count}  "
                    f"正确率 {correct_count / i * 100:.0f}%[/dim]"
                )
                try:
                    console.input("  [dim]按回车继续...[/dim]")
                except (EOFError, KeyboardInterrupt):
                    break

    except KeyboardInterrupt:
        console.print("\n  [yellow]冲刺已暂停，进度已保存[/yellow]")

    duration = int(time.time() - start_time)
    finish_session(session_id, answered, correct_count, duration)
    update_daily_progress(answered, correct_count, duration // 60)

    print_session_summary(answered, correct_count, duration, label)

    # 刷新剩余冲刺池
    remaining_stats = get_sprint_stats()
    remaining = remaining_stats["total"]
    msg = (
        f"  本次完成：[bold]{answered}[/bold] 题    "
        f"正确：[green]{correct_count}[/green]    "
        f"错误：[red]{answered - correct_count}[/red]\n\n"
        f"  冲刺池剩余：[bold yellow]{remaining}[/bold yellow] 道"
    )
    if remaining == 0:
        msg += "\n\n  [bold green]🎉 冲刺池已全部清空！可以去做模拟考试了！[/bold green]"
    else:
        msg += f"\n  [dim]明天继续！还剩 {remaining} 题[/dim]"

    console.print(Panel(msg, title="冲刺进度", border_style="cyan", box=box.ROUNDED))

    if answered > 0:
        weaknesses = detect_and_save_weaknesses()
        if weaknesses:
            console.print(f"\n  [yellow]⚠️  发现 {len(weaknesses)} 个薄弱知识点[/yellow]")
            for w in weaknesses[:3]:
                console.print(
                    f"    · 域{w['domain_id']} {w['subdomain']}  "
                    f"掌握分 [red]{w['weakness_score']:.0f}[/red]"
                )
