"""学习报告生成"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich import box

from analysis.progress_tracker import get_overall_progress, get_domains_needing_attention
from analysis.weakness_detector import detect_and_save_weaknesses
from ui.cli.tables import print_domain_stats_table, print_weakness_table
from config.domains import DOMAINS
from config.settings import settings

console = Console()


def show_overall_report() -> None:
    """展示综合学习报告"""
    console.print("\n[bold]正在生成学习报告...[/bold]\n")
    prog = get_overall_progress()

    # 头部统计
    console.print(
        Panel(
            f"  📅 当前天数：第 [cyan]{prog['current_day']}[/cyan] / {settings.TOTAL_DAYS} 天\n"
            f"  📝 累计答题：[cyan]{prog['total_attempts']}[/cyan] 题\n"
            f"  ✅ 整体正确率：{'[green]' if prog['overall_accuracy']>=0.7 else '[red]'}"
            f"{prog['overall_accuracy']*100:.1f}%[/]\n"
            f"  ⏱  近7天学习：[cyan]{prog['minutes_last_7_days']}[/cyan] 分钟\n"
            f"  🏆 最高模考分：[cyan]{prog['best_exam_score']:.0f}[/cyan] / 1000",
            title="📊 总体进度",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )

    # 域详情表
    print_domain_stats_table(prog["domain_stats"])

    # 薄弱点
    console.print("\n[bold]正在检测薄弱点...[/bold]")
    weaknesses = detect_and_save_weaknesses()
    print_weakness_table(weaknesses)

    # 需要关注的域
    attention = get_domains_needing_attention()
    if attention:
        console.print("\n[bold red]⚠️  重点加强域：[/bold red]")
        for a in attention:
            console.print(
                f"  域{a['domain_id']} {a['name']}  "
                f"正确率 [red]{a['accuracy']*100:.1f}%[/red]（{a['total']}题）"
            )

    # 模考历史
    if prog["recent_exams"]:
        console.print("\n[bold]📝 近期模考记录：[/bold]")
        for e in prog["recent_exams"]:
            score = e.get("exam_score", 0) or 0
            acc = (e.get("correct_count", 0) / max(e.get("total_questions", 1), 1)) * 100
            result = "[green]通过✅[/green]" if score >= 700 else "[red]未通过❌[/red]"
            console.print(
                f"  {e.get('started_at','')[:10]}  "
                f"{e.get('total_questions',0)}题  "
                f"正确率{acc:.1f}%  "
                f"分数{score:.0f}  {result}"
            )
    console.print()
