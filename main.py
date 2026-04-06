#!/usr/bin/env python3
"""CISSP 中文学习系统 - CLI 入口"""
from __future__ import annotations

import sys
import click
from rich.console import Console

from config.settings import settings
from database.connection import init_database, close_connection
from questions.loader import ensure_questions_loaded
from database.models import get_current_day_number

console = Console()


def bootstrap() -> None:
    """初始化数据库和题库"""
    init_database()
    ensure_questions_loaded()


# ─── CLI 命令 ───────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """CISSP 中文学习系统"""
    if ctx.invoked_subcommand is None:
        # 默认进入交互式主菜单
        run_interactive()


@cli.command()
def init():
    """初始化：建库 + 导入题库 + 生成50天计划"""
    console.print("[bold]初始化 CISSP 学习系统...[/bold]")
    init_database()
    console.print("  ✅ 数据库已就绪")

    from questions.loader import load_all_banks
    count = load_all_banks()
    console.print(f"  ✅ 导入题目：{count} 道")

    from plan.study_plan import generate_plan
    from datetime import date
    plan = generate_plan(date.today())
    console.print(f"  ✅ 生成50天学习计划（从今天开始）")

    mode = "在线 AI 模式" if settings.is_online() else "离线模式（设置 ANTHROPIC_API_KEY 启用AI）"
    console.print(f"  ✅ 运行模式：{mode}")
    console.print("\n  [green]初始化完成！运行 [bold]python main.py[/bold] 开始学习[/green]\n")


@cli.command()
@click.option("--domain", "-d", multiple=True, type=int, help="指定域（可多次使用）")
@click.option("--difficulty", "-l", type=int, help="难度 1-3")
@click.option("--count", "-n", default=None, type=int, help="题目数量")
def practice(domain, difficulty, count):
    """练习模式：选域刷题"""
    bootstrap()
    from modes.practice_mode import run_practice
    domain_ids = list(domain) or None
    run_practice(domain_ids=domain_ids, difficulty=difficulty, count=count)


@cli.command()
def exam():
    """模拟考试：125题/3小时"""
    bootstrap()
    from modes.exam_mode import run_exam
    run_exam()


@cli.command()
def study():
    """学习模式：AI 知识点讲解（需要 API Key）"""
    bootstrap()
    from modes.study_mode import run_study
    run_study()


@cli.command()
def review():
    """错题复习 & 薄弱点强化"""
    bootstrap()
    from modes.review_mode import run_review
    run_review()


@cli.command()
def report():
    """查看学习报告"""
    bootstrap()
    from analysis.report_generator import show_overall_report
    show_overall_report()


@cli.command()
@click.option("--compact", is_flag=True, help="简洁视图")
def plan(compact):
    """查看50天学习计划"""
    bootstrap()
    from plan.study_plan import show_plan
    show_plan(compact=compact)


# ─── 交互式主菜单 ────────────────────────────────────────────────

def run_interactive() -> None:
    """交互式主菜单循环"""
    try:
        bootstrap()
    except Exception as e:
        console.print(f"[red]初始化失败：{e}[/red]")
        console.print("请先运行：[cyan]python main.py init[/cyan]")
        sys.exit(1)

    from ui.cli.menus import print_main_banner, print_main_menu, prompt_menu_choice
    from modes.daily_diagnostic import run_daily_diagnostic
    run_daily_diagnostic()

    while True:
        try:
            current_day = get_current_day_number()
            print_main_banner(current_day, settings.TOTAL_DAYS)
            print_main_menu(online=settings.is_online())

            choice = prompt_menu_choice(["0", "1", "2", "3", "4", "5", "6"])

            if choice == "0":
                console.print("\n  [dim]再见！祝考试顺利 🎓[/dim]\n")
                break
            elif choice == "1":
                from modes.study_mode import run_study
                run_study()
            elif choice == "2":
                from modes.practice_mode import run_practice
                run_practice()
            elif choice == "3":
                from modes.exam_mode import run_exam
                run_exam()
            elif choice == "4":
                from modes.review_mode import run_review
                run_review()
            elif choice == "5":
                from analysis.report_generator import show_overall_report
                show_overall_report()
            elif choice == "6":
                from plan.study_plan import show_plan
                show_plan()

        except KeyboardInterrupt:
            console.print("\n  [dim]按 0 退出[/dim]")
        except Exception as e:
            console.print(f"\n  [red]错误：{e}[/red]")
            import traceback
            if "--debug" in sys.argv:
                traceback.print_exc()

    close_connection()


if __name__ == "__main__":
    cli()
