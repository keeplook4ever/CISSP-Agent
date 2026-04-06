"""学习模式：AI 知识点讲解"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from config.domains import DOMAINS
from config.settings import settings
from ai.client import stream_chat
from ai.prompts import STUDY_GUIDE
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

    console.print(f"\n  [bold]AI 正在讲解：{topic}[/bold]\n")
    console.print("─" * 50)

    user_msg = f"请详细讲解CISSP域{domain_id}【{domain_name}】中关于【{topic}】的知识点。"

    stream_chat(
        STUDY_GUIDE,
        user_msg,
        on_chunk=lambda t: console.print(t, end=""),
    )
    console.print("\n" + "─" * 50)
    console.print("  [dim]按回车返回菜单[/dim]")
    try:
        console.input("")
    except (EOFError, KeyboardInterrupt):
        pass


def _select_subdomain(domain_name: str, subdomains: list[str]) -> str:
    if not subdomains:
        return domain_name
    console.print(f"\n  【{domain_name}】子域列表：")
    console.print("  [dim]0[/dim]  整体概述")
    for i, sub in enumerate(subdomains, 1):
        console.print(f"  [dim]{i}[/dim]  {sub}")
    while True:
        try:
            raw = console.input("\n  [cyan]选择子域[/cyan]（回车=整体概述）：").strip()
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
    console.print(f"\n  【{subdomain}】相关概念：")
    console.print(f"  [dim]0[/dim]  {subdomain}（综合讲解）")
    for i, concept in enumerate(key_concepts, 1):
        console.print(f"  [dim]{i}[/dim]  {concept}")
    while True:
        try:
            raw = console.input("\n  [cyan]选择具体概念[/cyan]（回车=综合讲解）：").strip()
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
