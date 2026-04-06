"""Anthropic Claude API 客户端封装"""
from __future__ import annotations

import json
from typing import Optional

from config.settings import settings


def _get_client():
    try:
        import anthropic
        return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    except ImportError:
        raise RuntimeError("请安装 anthropic 包: pip install anthropic")


def chat(system: str, user: str, max_tokens: int = None) -> str:
    """发送单轮对话，返回文本响应"""
    if not settings.is_online():
        return ""
    client = _get_client()
    resp = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


def stream_chat(system: str, user: str, on_chunk=None) -> str:
    """流式对话，可选回调逐字输出"""
    if not settings.is_online():
        return ""
    client = _get_client()
    full = []
    with client.messages.stream(
        model=settings.CLAUDE_MODEL,
        max_tokens=settings.CLAUDE_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text in stream.text_stream:
            full.append(text)
            if on_chunk:
                on_chunk(text)
    return "".join(full)
