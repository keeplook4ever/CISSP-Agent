"""知识点内容缓存管理：命中本地则直接展示，内容不足时在线补充并更新缓存"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from config.settings import settings
from ai.client import stream_chat
from ai.prompts import STUDY_GUIDE
from database.models import get_cached_study_content, save_study_content

console = Console()


def get_or_fetch_content(domain_id: int, domain_name: str, topic: str) -> None:
    """
    展示知识点内容：
    - 本地缓存充足 → 直接展示，可选在线刷新
    - 本地缓存不完整 → 展示已有内容，在线补充并更新缓存
    - 无缓存且在线 → 在线获取并缓存
    - 无缓存且离线 → 提示用户联网
    """
    cached = get_cached_study_content(domain_id, topic)
    sufficient = cached and len(cached) >= settings.MIN_CONTENT_CHARS

    if sufficient:
        _display_cached(cached, topic)
        if settings.is_online():
            _maybe_refresh(domain_id, domain_name, topic)
        return

    if cached:
        console.print(
            Panel(
                f"[yellow]本地缓存内容不完整（{len(cached)} 字），将在线补充...[/yellow]",
                border_style="yellow",
                padding=(0, 1),
            )
        )

    if not settings.is_online():
        if cached:
            _display_cached(cached, topic)
        else:
            console.print(
                Panel(
                    "  本地无缓存，且当前为离线模式\n"
                    "  请设置环境变量 [cyan]ANTHROPIC_API_KEY[/cyan] 后在线获取",
                    title="⚠️  无可用内容",
                    border_style="yellow",
                )
            )
        return

    _fetch_and_cache(domain_id, domain_name, topic)


def _display_cached(content: str, topic: str) -> None:
    console.print(Panel("[dim]📦 内容来自本地缓存[/dim]", border_style="dim", padding=(0, 1)))
    console.print(content)


def _maybe_refresh(domain_id: int, domain_name: str, topic: str) -> None:
    try:
        raw = console.input("\n  [dim]按 [r] 在线刷新内容，其他键跳过：[/dim]").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if raw == "r":
        console.print()
        _fetch_and_cache(domain_id, domain_name, topic)


def _fetch_and_cache(domain_id: int, domain_name: str, topic: str) -> None:
    user_msg = f"请详细讲解CISSP域{domain_id}【{domain_name}】中关于【{topic}】的知识点。"
    full_content = stream_chat(
        STUDY_GUIDE,
        user_msg,
        on_chunk=lambda t: console.print(t, end=""),
    )
    if full_content and len(full_content) >= settings.MIN_CONTENT_CHARS:
        save_study_content(domain_id, topic, full_content)
        console.print("\n  [dim]✓ 已保存至本地缓存[/dim]")
