"""菜单和选择组件"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich import box

from config.domains import DOMAINS

console = Console()


def print_main_banner(current_day: int, total_days: int) -> None:
    """打印主界面横幅"""
    console.print()
    console.print(
        Panel(
            f"[bold cyan]CISSP 中文学习系统[/bold cyan]\n"
            f"[dim]第 {current_day} / {total_days} 天  ·  2024 年版考纲[/dim]",
            box=box.DOUBLE_EDGE,
            border_style="cyan",
            padding=(0, 4),
        )
    )


def print_main_menu(online: bool = False) -> None:
    """打印主菜单"""
    mode = "[green]在线 AI[/green]" if online else "[yellow]离线[/yellow]"
    console.print(f"\n  模式：{mode}\n")
    options = [
        ("[bold]1[/bold]", "📖 学习模式", "知识点讲解（AI）"),
        ("[bold]2[/bold]", "✏️  练习模式", "选域刷题"),
        ("[bold]3[/bold]", "🎯 模拟考试", "125题/3小时 CAT"),
        ("[bold]4[/bold]", "🔄 错题复习", "薄弱点强化"),
        ("[bold]5[/bold]", "📊 学习报告", "进度统计"),
        ("[bold]6[/bold]", "📅 50天计划", "查看/生成"),
        ("[bold]0[/bold]", "🚪 退出", ""),
    ]
    for key, label, hint in options:
        hint_str = f"  [dim]{hint}[/dim]" if hint else ""
        console.print(f"  {key}  {label}{hint_str}")
    console.print()


def prompt_menu_choice(choices: list[str], prompt: str = "请选择") -> str:
    """通用菜单选择"""
    while True:
        try:
            val = console.input(f"  [bold cyan]{prompt}：[/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            return "0"
        if val in choices:
            return val
        console.print(f"  [red]请输入有效选项：{'/'.join(choices)}[/red]")


def select_domain(multi: bool = False) -> list[int]:
    """选择学习域（支持多选）"""
    console.print("\n  [bold]可选学习域：[/bold]")
    console.print("  [dim]0[/dim]  全部域（随机混合）")
    for did, d in DOMAINS.items():
        weight_str = f"{d['weight']*100:.0f}%"
        console.print(
            f"  [dim]{did}[/dim]  {d['name']}  [dim]{d['name_en']}  权重{weight_str}[/dim]"
        )

    if multi:
        console.print("  [dim]可输入多个域号，用逗号分隔，如 1,3,5[/dim]")

    while True:
        try:
            raw = console.input("\n  [cyan]请选择域[/cyan]（回车=全部）：").strip()
        except (EOFError, KeyboardInterrupt):
            return list(DOMAINS.keys())

        if not raw or raw == "0":
            return list(DOMAINS.keys())

        try:
            ids = [int(x.strip()) for x in raw.split(",")]
            valid = [i for i in ids if i in DOMAINS]
            if valid:
                return valid
        except ValueError:
            pass
        console.print("  [red]请输入有效域号[/red]")


def select_difficulty() -> int | None:
    """选择难度（可选）"""
    console.print("\n  难度选择：[dim]1=基础  2=中级  3=高级  0=混合[/dim]")
    while True:
        try:
            raw = console.input("  [cyan]请选择难度[/cyan]（回车=混合）：").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not raw or raw == "0":
            return None
        if raw in ("1", "2", "3"):
            return int(raw)
        console.print("  [red]请输入 0-3[/red]")


def confirm(prompt: str = "确认？") -> bool:
    """Y/N 确认"""
    while True:
        try:
            raw = console.input(f"  [cyan]{prompt} [Y/n]：[/cyan]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if raw in ("", "y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
