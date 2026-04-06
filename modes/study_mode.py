"""学习模式：AI 知识点讲解"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from config.domains import DOMAINS
from config.settings import settings
from ai.content_cache import get_or_fetch_content
from ui.cli.menus import select_domain

console = Console()


def run_study() -> None:
    """运行学习模式"""
    if not settings.is_online():
        console.print(
            Panel(
                "  学习模式需要 Claude API（在线模式）\n\n"
                "  请设置环境变量：\n"
                "  [cyan]export ANTHROPIC_API_KEY=your_key[/cyan]\n\n"
                "  或使用练习模式进行离线刷题",
                title="⚠️  需要 API Key",
                border_style="yellow",
            )
        )
        return

    domain_ids = select_domain(multi=False)
    domain_id = domain_ids[0]
    domain = DOMAINS.get(domain_id, {})
    domain_name = domain.get("name", "")

    # 选择子域
    subdomains = domain.get("subdomains", [])
    subdomain = _select_subdomain(domain_name, subdomains)

    # 选择学习内容
    topic = _select_topic(domain, subdomain)

    console.print(f"\n  [bold]讲解：{topic}[/bold]\n")
    console.print("─" * 50)

    get_or_fetch_content(domain_id, domain_name, topic)

    console.print("\n" + "─" * 50)
    console.print("  [dim]按回车返回菜单[/dim]")
    try:
        console.input("")
    except (EOFError, KeyboardInterrupt):
        pass


def _select_subdomain(domain_name: str, subdomains: list[str]) -> str:
    if not subdomains:
        return domain_name

    items = [("0", "整体概述")] + [(str(i), sub) for i, sub in enumerate(subdomains, 1)]
    console.print(_build_selection_table(f"【{domain_name}】子域列表", items))

    while True:
        try:
            raw = console.input("  [cyan]选择子域[/cyan]（回车=整体概述）：").strip()
        except (EOFError, KeyboardInterrupt):
            return domain_name
        if not raw or raw == "0":
            return f"{domain_name}整体概述"
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(subdomains):
                return subdomains[idx]
        except ValueError:
            pass
        console.print("  [red]请输入有效编号[/red]")


def _select_topic(domain: dict, subdomain: str) -> str:
    key_concepts = domain.get("key_concepts", [])
    if not key_concepts:
        return subdomain

    items = [("0", f"{subdomain}（综合讲解）")] + [
        (str(i), c) for i, c in enumerate(key_concepts, 1)
    ]
    console.print(_build_selection_table(f"【{subdomain}】相关概念", items))

    while True:
        try:
            raw = console.input("  [cyan]选择具体概念[/cyan]（回车=综合讲解）：").strip()
        except (EOFError, KeyboardInterrupt):
            return subdomain
        if not raw or raw == "0":
            return subdomain
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(key_concepts):
                return key_concepts[idx]
        except ValueError:
            pass
        console.print("  [red]请输入有效编号[/red]")


def _build_selection_table(title: str, items: list[tuple[str, str]]) -> Panel:
    """将选项列表渲染为两列 Table，放入 Panel 返回。"""
    mid = (len(items) + 1) // 2
    left_col = items[:mid]
    right_col = items[mid:]

    table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    table.add_column(ratio=1)
    table.add_column(ratio=1)

    for i in range(mid):
        left_idx, left_label = left_col[i]
        if i < len(right_col):
            right_idx, right_label = right_col[i]
            table.add_row(
                f"[dim]{left_idx}[/dim]  {left_label}",
                f"[dim]{right_idx}[/dim]  {right_label}",
            )
        else:
            table.add_row(f"[dim]{left_idx}[/dim]  {left_label}", "")

    return Panel(table, title=title, border_style="cyan", box=box.ROUNDED, padding=(0, 1))
