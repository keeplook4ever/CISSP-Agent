"""多人模式 — 玩家选择 & 管理界面"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from database.player_manager import (
    get_players,
    get_player,
    create_player,
    delete_player,
    reset_player_data,
    set_current_player,
    get_current_player_id,
    get_current_player_name,
)

console = Console()


# ── 启动时玩家选择（多玩家才显示）────────────────────────────────

def maybe_select_player() -> None:
    """启动时若有多个玩家，提示选择；否则静默使用默认玩家"""
    players = get_players()
    if len(players) <= 1:
        if players:
            set_current_player(players[0]["id"])
        return

    console.print()
    console.print(
        Panel(
            "[bold cyan]检测到多个玩家档案，请选择当前用户[/bold cyan]",
            border_style="cyan",
            padding=(0, 2),
        )
    )
    _show_player_table(players)
    console.print()

    pid_map = {str(i + 1): p["id"] for i, p in enumerate(players)}
    choices = list(pid_map.keys())

    while True:
        try:
            raw = console.input(
                f"  [cyan]请输入编号[/cyan]（1-{len(players)}，回车=继续上次）："
            ).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw:
            # 使用最近活跃玩家（列表第一个）
            set_current_player(players[0]["id"])
            console.print(f"  [dim]继续使用：{players[0]['name']}[/dim]")
            break

        if raw in choices:
            pid = pid_map[raw]
            set_current_player(pid)
            p = get_player(pid)
            console.print(f"  [green]已切换至玩家：{p['name']}[/green]")
            break

        console.print(f"  [red]请输入 1-{len(players)} 的编号[/red]")


# ── 主管理菜单 ────────────────────────────────────────────────────

def run_player_management() -> None:
    """玩家管理子菜单"""
    while True:
        players = get_players()
        cur_id = get_current_player_id()
        cur_name = get_current_player_name()

        console.print()
        console.print(
            Panel(
                f"[bold]多人模式 / 玩家管理[/bold]\n"
                f"[dim]当前玩家：[/dim][bold cyan]{cur_name}[/bold cyan]",
                border_style="cyan",
                padding=(0, 2),
            )
        )
        console.print("  [bold]1[/bold]  切换玩家       选择已有档案")
        console.print("  [bold]2[/bold]  新建玩家       创建新的答题档案")
        console.print("  [bold red]3[/bold red]  [bold red]一键重开[/bold red]       清空当前玩家全部答题记录")
        console.print("  [bold]4[/bold]  删除玩家       永久删除当前玩家及其数据")
        console.print("  [bold]0[/bold]  返回主菜单")
        console.print()

        try:
            choice = console.input("  [cyan]请选择：[/cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "0":
            break
        elif choice == "1":
            _switch_player(players)
        elif choice == "2":
            _create_player()
        elif choice == "3":
            _reset_current_player(cur_id, cur_name)
        elif choice == "4":
            _delete_current_player(cur_id, cur_name)
        else:
            console.print("  [red]请输入 0-4[/red]")


def _show_player_table(players: list[dict]) -> None:
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("编号", style="dim", width=4)
    table.add_column("玩家名称", style="bold")
    table.add_column("最近活跃")
    table.add_column("创建时间")

    for i, p in enumerate(players):
        last = (p.get("last_active") or "—")[:10]
        created = (p.get("created_at") or "—")[:10]
        style = "cyan" if p["id"] == get_current_player_id() else ""
        table.add_row(str(i + 1), p["name"], last, created, style=style)

    console.print(table)


def _switch_player(players: list[dict]) -> None:
    console.print()
    _show_player_table(players)

    pid_map = {str(i + 1): p["id"] for i, p in enumerate(players)}
    try:
        raw = console.input(f"  [cyan]输入编号[/cyan]（1-{len(players)}）：").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if raw in pid_map:
        pid = pid_map[raw]
        set_current_player(pid)
        p = get_player(pid)
        console.print(f"  [green]已切换至：{p['name']}[/green]")
    else:
        console.print("  [red]无效编号[/red]")


def _create_player() -> None:
    try:
        name = console.input("  [cyan]新玩家名称：[/cyan]").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not name:
        console.print("  [red]名称不能为空[/red]")
        return

    pid = create_player(name)
    if pid == -1:
        console.print(f"  [red]创建失败（名称已存在或非法）[/red]")
        return

    set_current_player(pid)
    console.print(f"  [green]玩家 [{name}] 创建成功，已自动切换[/green]")


def _reset_current_player(player_id: int, player_name: str) -> None:
    console.print()
    console.print(
        Panel(
            f"  [bold red]一键重开 — 即将清空玩家 [{player_name}] 的全部答题记录[/bold red]\n\n"
            "  • 所有历史会话 & 答题记录将被删除\n"
            "  • 题目作答状态（错题、掌握度）将重置\n"
            "  • 域统计数据将归零\n"
            "  • 题库 & 学习计划不受影响",
            border_style="red",
            padding=(0, 2),
        )
    )
    try:
        confirm = console.input("  [bold red]确认重开？[/bold red] 请输入玩家名称确认（回车取消）：").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [dim]已取消[/dim]")
        return

    if confirm != player_name:
        console.print("  [dim]名称不匹配，已取消[/dim]")
        return

    result = reset_player_data(player_id)
    console.print(
        f"\n  [green]重开完成！[/green] 已清除 "
        f"[cyan]{result['sessions']}[/cyan] 个会话 / "
        f"[cyan]{result['answers']}[/cyan] 条答题记录\n"
    )


def _delete_current_player(player_id: int, player_name: str) -> None:
    console.print()
    console.print(
        Panel(
            f"  [bold red]即将永久删除玩家 [{player_name}][/bold red]\n\n"
            "  此操作不可恢复！所有数据将彻底清除。\n"
            "  注意：不能删除唯一剩余的玩家。",
            border_style="red",
            padding=(0, 2),
        )
    )
    try:
        confirm = console.input("  确认删除？请输入玩家名称（回车取消）：").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("  [dim]已取消[/dim]")
        return

    if confirm != player_name:
        console.print("  [dim]名称不匹配，已取消[/dim]")
        return

    ok = delete_player(player_id)
    if not ok:
        console.print("  [red]无法删除：系统中只剩一个玩家[/red]")
        return

    # 自动切换到剩余玩家中最近活跃的
    players = get_players()
    if players:
        set_current_player(players[0]["id"])
        console.print(
            f"  [green]玩家 [{player_name}] 已删除，已切换至：{players[0]['name']}[/green]"
        )
