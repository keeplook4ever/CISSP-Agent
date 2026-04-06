"""薄弱点 AI 分析"""
from __future__ import annotations

from ai.client import stream_chat
from ai.prompts import WEAKNESS_ANALYSIS
from config.domains import DOMAINS


def analyze_weaknesses(
    domain_stats: list[dict],
    wrong_questions: list[dict],
    on_chunk=None,
) -> str:
    """根据答题数据生成个性化薄弱点分析报告"""
    # 构建域统计摘要
    stats_lines = []
    for s in domain_stats:
        d = DOMAINS.get(s["domain_id"], {})
        acc = s.get("accuracy_rate", 0) * 100
        total = s.get("total_attempts", 0)
        stats_lines.append(
            f"域{s['domain_id']} {d.get('name','')}：正确率{acc:.0f}%，答题{total}题"
        )

    # 近期错题摘要
    wrong_lines = []
    for w in wrong_questions[:10]:
        wrong_lines.append(
            f"- 域{w.get('domain_id')} {w.get('subdomain','')}：{w.get('question','')[:40]}…"
        )

    user_msg = f"""以下是学习者的CISSP答题数据：

【各域正确率】
{chr(10).join(stats_lines) or '暂无数据'}

【近期错题（共{len(wrong_questions)}道）】
{chr(10).join(wrong_lines) or '暂无错题'}

请提供详细的薄弱点分析和个性化学习建议。"""

    return stream_chat(WEAKNESS_ANALYSIS, user_msg, on_chunk=on_chunk)
