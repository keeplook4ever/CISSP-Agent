"""答案深度解析"""
from __future__ import annotations

from ai.client import stream_chat
from ai.prompts import ANSWER_EXPLANATION


def explain_answer(question: dict, user_answer: str, on_chunk=None) -> str:
    """生成题目深度解析，支持流式输出"""
    opts = question.get("options") or {
        "A": question.get("option_a", ""),
        "B": question.get("option_b", ""),
        "C": question.get("option_c", ""),
        "D": question.get("option_d", ""),
    }
    correct = question.get("correct", "")
    explanation = question.get("explanation", "")

    user_msg = f"""题目：{question.get('question', '')}

选项：
A. {opts.get('A', '')}
B. {opts.get('B', '')}
C. {opts.get('C', '')}
D. {opts.get('D', '')}

用户选择：{user_answer}（{'正确' if user_answer == correct else '错误，正确答案为' + correct}）

基础解析：{explanation}

请提供更深入的解析，帮助理解和记忆。"""

    return stream_chat(ANSWER_EXPLANATION, user_msg, on_chunk=on_chunk)
