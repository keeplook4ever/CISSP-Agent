"""Anthropic Claude API 客户端封装"""
from __future__ import annotations

import json
import threading
from typing import Optional

from config.settings import settings

# fill-bank 批量生成专用的快速模型（Haiku 速度快 5-10 倍）
FAST_MODEL = "claude-haiku-4-5-20251001"


def _get_client(timeout: float = 90.0):
    try:
        import anthropic
        return anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=timeout,
        )
    except ImportError:
        raise RuntimeError("请安装 anthropic 包: pip install anthropic")


def chat(system: str, user: str, max_tokens: int = None, model: str = None) -> str:
    """发送单轮对话，返回文本响应。内置线程级超时，防止代理挂起。"""
    if not settings.is_online():
        return ""

    result: dict = {}

    def _call():
        try:
            client = _get_client()
            resp = client.messages.create(
                model=model or settings.CLAUDE_MODEL,
                max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            result["text"] = resp.content[0].text.strip()
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=_call, daemon=True)
    t.start()
    t.join(timeout=90)  # 90 秒线程级超时，代理挂起时强制中断

    if t.is_alive():
        # 线程仍在运行，代理超时
        result["error"] = "timeout"

    if "error" in result:
        raise RuntimeError(f"API 调用失败: {result['error']}")

    return result.get("text", "")


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
