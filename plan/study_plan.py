"""50天学习计划生成与展示"""
from __future__ import annotations

from datetime import date, timedelta

from rich.console import Console
from rich.table import Table
from rich import box

from config.domains import DOMAINS
from database.models import save_study_plan, get_all_plan_days, get_current_day_number

console = Console()

# 50天学习安排：(domain_id, 天数)
_SCHEDULE = [
    (1, 8),   # 安全与风险管理（权重最高）
    (3, 6),   # 安全架构与工程
    (4, 6),   # 通信与网络安全
    (5, 6),   # 身份与访问管理
    (6, 5),   # 安全评估与测试
    (7, 6),   # 安全运营
    (2, 4),   # 资产安全
    (8, 4),   # 软件开发安全
    # 最后5天：综合冲刺
]
_COMPREHENSIVE_DAYS = 5

# 模拟考试安排（每7天一次）
_EXAM_DAYS = {7, 14, 21, 28, 35, 42, 49, 50}


def generate_plan(start_date: date = None) -> list[dict]:
    """生成50天学习计划"""
    if start_date is None:
        start_date = date.today()

    plan = []
    day = 1

    # 按域分配学习天数
    for domain_id, num_days in _SCHEDULE:
        domain = DOMAINS[domain_id]
        subdomains = domain.get("subdomains", [])
        for i in range(num_days):
            if day > 45:
                break
            sub_idx = i % max(len(subdomains), 1)
            sub_focus = subdomains[sub_idx] if subdomains else ""
            is_exam = day in _EXAM_DAYS
            plan.append({
                "day": day,
                "date": (start_date + timedelta(days=day - 1)).isoformat(),
                "domain_id": domain_id,
                "focus": sub_focus,
                "objectives": [
                    f"学习{sub_focus}核心概念",
                    "完成30道练习题",
                    "复习错题",
                ],
                "practice_count": 30,
                "is_exam_day": is_exam,
                "day_type": "exam" if is_exam else "study",
            })
            day += 1

    # 最后5天：综合冲刺
    for i in range(_COMPREHENSIVE_DAYS):
        if day > 50:
            break
        is_exam = day in _EXAM_DAYS
        plan.append({
            "day": day,
            "date": (start_date + timedelta(days=day - 1)).isoformat(),
            "domain_id": 1,  # 占位
            "focus": "全域综合冲刺",
            "objectives": ["模拟考试（125题）", "分析薄弱点", "针对性强化"],
            "practice_count": 125 if is_exam else 50,
            "is_exam_day": is_exam,
            "day_type": "exam" if is_exam else "review",
        })
        day += 1

    # 确保正好50天
    while len(plan) < 50:
        day = len(plan) + 1
        plan.append({
            "day": day,
            "date": (start_date + timedelta(days=day - 1)).isoformat(),
            "domain_id": 1,
            "focus": "综合复习",
            "objectives": ["自由复习"],
            "practice_count": 30,
            "is_exam_day": False,
            "day_type": "review",
        })

    save_study_plan(plan[:50])
    return plan[:50]


def show_plan(compact: bool = False) -> None:
    """展示学习计划"""
    plan = get_all_plan_days()
    if not plan:
        console.print("  [yellow]尚未生成学习计划，请先运行 init[/yellow]")
        return

    current_day = get_current_day_number()
    console.print(f"\n  当前：第 [cyan]{current_day}[/cyan] 天\n")

    if compact:
        _show_compact(plan, current_day)
    else:
        _show_full(plan, current_day)


def _show_compact(plan: list[dict], current_day: int) -> None:
    """简洁视图：只显示周围几天"""
    start = max(0, current_day - 3)
    end = min(len(plan), current_day + 7)
    for p in plan[start:end]:
        d = DOMAINS.get(p["domain_id"], {})
        status = "▶" if p["day_number"] == current_day else (" ✓" if p.get("is_completed") else "  ")
        exam_mark = " 🎯" if p.get("is_exam_day") else ""
        console.print(
            f"  {status} 第{p['day_number']:2d}天 {p.get('target_date','')}"
            f"  {d.get('name','综合')[:8]}  {p.get('subdomain_focus','')[:12]}{exam_mark}"
        )


def _show_full(plan: list[dict], current_day: int) -> None:
    """完整表格视图"""
    table = Table(title="📅 50天CISSP学习计划", box=box.SIMPLE, show_lines=False)
    table.add_column("天", width=4, justify="right")
    table.add_column("日期", width=10)
    table.add_column("学习域", min_width=12)
    table.add_column("重点子域", min_width=14)
    table.add_column("类型", width=6)
    table.add_column("状态", width=6)

    for p in plan:
        d = DOMAINS.get(p.get("domain_id", 0), {})
        day_num = p["day_number"]
        is_current = day_num == current_day
        is_done = bool(p.get("is_completed"))
        is_exam = bool(p.get("is_exam_day"))

        status = "[green]✓[/green]" if is_done else ("[cyan]▶[/cyan]" if is_current else "")
        day_style = "bold cyan" if is_current else ("dim" if is_done else "")
        type_str = "[yellow]考试🎯[/yellow]" if is_exam else ("复习" if p.get("day_type") == "review" else "学习")

        table.add_row(
            f"[{day_style}]{day_num}[/{day_style}]" if day_style else str(day_num),
            p.get("target_date", ""),
            d.get("name", "综合"),
            (p.get("subdomain_focus") or "")[:14],
            type_str,
            status,
        )

    console.print(table)
