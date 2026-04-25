"""题目展示和交互组件"""
from __future__ import annotations

import random

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()

OPTION_LABELS = ["A", "B", "C", "D"]
CORRECT_STYLE = "bold green"
WRONG_STYLE = "bold red"
HIGHLIGHT_STYLE = "bold cyan"


def print_question(
    q: dict,
    index: int,
    total: int,
    show_domain: bool = True,
) -> None:
    """打印单道题目"""
    opts = _get_options(q)
    domain_info = f"域{q.get('domain_id','')} · {q.get('subdomain','')}" if show_domain else ""
    diff_stars = "★" * q.get("difficulty", 1) + "☆" * (3 - q.get("difficulty", 1))

    title = f"第 {index}/{total} 题  {diff_stars}"
    if domain_info:
        title += f"  [{domain_info}]"

    body = Text()
    body.append(f"\n{q.get('question', '')}\n\n", style="bold white")
    for label in OPTION_LABELS:
        body.append(f"  {label}. {opts.get(label, '')}\n")

    console.print(Panel(body, title=title, border_style="blue", box=box.ROUNDED))


def print_result(
    q: dict,
    user_answer: str,
    is_correct: bool,
    show_explanation: bool = True,
) -> None:
    """打印答题结果"""
    opts = _get_options(q)
    correct = q.get("correct", "")

    if is_correct:
        console.print(f"\n  ✅ [bold green]正确！[/bold green]")
    else:
        console.print(
            f"\n  ❌ [bold red]错误[/bold red]  你选了 [red]{user_answer}[/red]，"
            f"正确答案是 [green]{correct}[/green]"
        )
        console.print(f"     [green]{correct}. {opts.get(correct, '')}[/green]")

    if show_explanation and q.get("explanation"):
        explanation = _remap_explanation(q["explanation"], q.get("_label_map"))
        console.print(
            Panel(
                explanation,
                title="💡 解析",
                border_style="yellow",
                padding=(0, 1),
            )
        )


def get_user_answer(timeout_hint: str = "") -> str:
    """获取用户输入的选项（A/B/C/D）"""
    hint = f" {timeout_hint}" if timeout_hint else ""
    while True:
        try:
            ans = console.input(f"\n  [bold cyan]请选择 [A/B/C/D]{hint}：[/bold cyan] ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            raise KeyboardInterrupt
        if ans in OPTION_LABELS:
            return ans
        console.print("  [red]请输入 A、B、C 或 D[/red]")


def shuffle_question(q: dict) -> dict:
    """随机打乱题目选项顺序，返回新的题目字典（含更新后的 correct 字段）。
    不修改原始 dict，避免影响数据库记录。"""
    opts = _get_options(q)
    original_correct = q.get("correct", "A")
    correct_text = opts.get(original_correct, "")

    labels = list(OPTION_LABELS)
    random.shuffle(labels)

    # labels[i] 是 old_label，OPTION_LABELS[i] 是 new_label
    old_to_new = {old: new for new, old in zip(OPTION_LABELS, labels)}

    new_opts = {new_label: opts[old_label] for new_label, old_label in zip(OPTION_LABELS, labels)}
    new_correct = old_to_new[original_correct]

    shuffled = dict(q)
    shuffled["options"] = new_opts
    shuffled["option_a"] = new_opts["A"]
    shuffled["option_b"] = new_opts["B"]
    shuffled["option_c"] = new_opts["C"]
    shuffled["option_d"] = new_opts["D"]
    shuffled["correct"] = new_correct
    # 保存映射供解析文字替换使用
    shuffled["_label_map"] = old_to_new
    return shuffled


def _get_options(q: dict) -> dict:
    """统一获取选项字典"""
    if "options" in q and isinstance(q["options"], dict):
        return q["options"]
    return {
        "A": q.get("option_a", ""),
        "B": q.get("option_b", ""),
        "C": q.get("option_c", ""),
        "D": q.get("option_d", ""),
    }


def _remap_explanation(explanation: str, label_map: dict | None) -> str:
    """将解析文字中的旧选项字母（A项/B项/C项/D项）替换为打乱后的新字母。"""
    if not label_map:
        return explanation
    import re
    # 用占位符避免二次替换：先把所有字母替换成占位符，再统一换成新字母
    placeholder = {old: f"\x00{new}\x00" for old, new in label_map.items()}
    result = re.sub(
        r'\b([ABCD])(?=项)',
        lambda m: placeholder.get(m.group(1), m.group(1)),
        explanation,
    )
    return result.replace("\x00", "")
