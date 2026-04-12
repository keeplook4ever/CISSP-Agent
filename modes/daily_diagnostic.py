"""每日诊断模式：启动时自动触发，30题覆盖8域，考后给出薄弱点学习建议"""
from __future__ import annotations

import random
import time
from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from config.domains import DOMAINS
from config.settings import settings
from database.models import (
    create_session, finish_session, record_answer,
    get_questions_balanced, get_domain_stats,
)
from analysis.weakness_detector import detect_and_save_weaknesses
from ui.cli.display import print_question, print_result, get_user_answer, shuffle_question
from ui.cli.tables import print_weakness_table

console = Console()


# ─── 公开入口 ────────────────────────────────────────────────────

def run_daily_diagnostic() -> None:
    """启动时调用：检查条件 → 提示 → 答题 → 结果+推荐"""
    if _check_all_passing():
        console.print(
            Panel(
                "  所有域正确率均已达标（≥ 70%），每日诊断已关闭\n"
                "  继续保持，冲击高分！",
                title="🎉 全部达标",
                border_style="green",
                box=box.ROUNDED,
            )
        )
        return

    if _is_today_done():
        console.print(
            Panel(
                "  今日诊断已完成，进入主菜单继续学习",
                title="✅ 每日诊断",
                border_style="dim",
                box=box.ROUNDED,
                padding=(0, 2),
            )
        )
        return

    # 提示界面
    console.print(
        Panel(
            "  每日诊断考试（30题 · 覆盖全部8个域）\n\n"
            "  答题结果将持续更新你的薄弱点数据\n"
            "  考后给出最值得学习的域和子域建议\n\n"
            "  [bold cyan][Enter][/bold cyan] 开始  "
            "[dim][s][/dim] 跳过进入主菜单",
            title="🩺 每日诊断",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )
    try:
        raw = console.input("  ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if raw == "s":
        return

    _run_diagnostic()


# ─── 内部实现 ────────────────────────────────────────────────────

def _run_diagnostic() -> None:
    total_count = settings.DAILY_DIAGNOSTIC_COUNT

    # 检查今日是否有未完成的会话（断点续答）
    resume = _get_today_incomplete_session()
    if resume:
        session_id, already_answered, answered_ids = resume
        remaining = total_count - already_answered
        console.print(
            Panel(
                f"  检测到今日诊断已答 [cyan]{already_answered}[/cyan] 题，"
                f"还剩 [yellow]{remaining}[/yellow] 题\n"
                "  继续上次进度...",
                title="🔄 断点续答",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )
    else:
        already_answered = 0
        answered_ids = []
        remaining = total_count
        session_id = create_session("diagnostic", list(DOMAINS.keys()))

    allocation = _allocate_questions(remaining)
    questions = _load_questions(allocation, exclude_ids=answered_ids)

    if not questions:
        console.print(
            Panel(
                "  本地题库暂无足够题目\n"
                "  请先运行 [cyan]python main.py init[/cyan] 导入题库",
                title="⚠️  题库不足",
                border_style="yellow",
            )
        )
        return

    start_time = time.time()
    results = _run_answer_loop(questions, session_id)
    elapsed = int(time.time() - start_time)

    total_answered = already_answered + results["total"]
    # 只有累计答题数达到配置总数才标记为完成
    if total_answered >= total_count:
        finish_session(session_id, total_answered, results["correct"], elapsed)

    weaknesses = detect_and_save_weaknesses()
    recs = _generate_recommendations(weaknesses)
    _show_results(results, weaknesses, recs)

    console.print("  [dim]按回车继续[/dim]")
    try:
        console.input("")
    except (EOFError, KeyboardInterrupt):
        pass


def _is_today_done() -> bool:
    """今日诊断已完成：存在 is_completed=1 且答题数达到配置总数的会话"""
    from database.connection import get_connection
    today = date.today().isoformat()
    conn = get_connection()
    cur = conn.execute(
        "SELECT id FROM study_sessions "
        "WHERE session_type='diagnostic' AND date(started_at)=? "
        "AND is_completed=1 AND total_questions >= ?",
        (today, settings.DAILY_DIAGNOSTIC_COUNT),
    )
    return cur.fetchone() is not None


def _get_today_incomplete_session() -> tuple[int, int, list[int]] | None:
    """返回今日未完成的诊断会话信息 (session_id, 已答题数, 已答题ID列表)，无则返回 None"""
    from database.connection import get_connection
    today = date.today().isoformat()
    conn = get_connection()
    cur = conn.execute(
        "SELECT id FROM study_sessions "
        "WHERE session_type='diagnostic' AND date(started_at)=? AND is_completed=0 "
        "ORDER BY started_at DESC LIMIT 1",
        (today,),
    )
    row = cur.fetchone()
    if not row:
        return None
    session_id = row["id"]
    cur2 = conn.execute(
        "SELECT question_id FROM answer_records WHERE session_id=?",
        (session_id,),
    )
    answered_ids = [r["question_id"] for r in cur2.fetchall()]
    return session_id, len(answered_ids), answered_ids


def _check_all_passing() -> bool:
    stats = get_domain_stats()
    if len(stats) < len(DOMAINS):
        return False
    return all(
        s.get("total_attempts", 0) >= settings.DOMAIN_PASS_MIN_ATTEMPTS
        and s.get("accuracy_rate", 0.0) >= settings.WEAKNESS_THRESHOLD
        for s in stats
    )


def _allocate_questions(total: int = 30) -> dict[int, int]:
    """按域权重用最大余数法分配题数，保证每域 ≥ 1 且合计恰好等于 total。"""
    weights = {did: DOMAINS[did]["weight"] for did in DOMAINS}
    total_w = sum(weights.values())
    raw = {did: w / total_w * total for did, w in weights.items()}
    alloc = {did: max(1, int(v)) for did, v in raw.items()}
    remainder = total - sum(alloc.values())
    # 按小数部分降序补充余量
    fracs = sorted(raw.items(), key=lambda x: x[1] - int(x[1]), reverse=True)
    for i in range(max(0, remainder)):
        alloc[fracs[i % len(fracs)][0]] += 1
    return alloc


def _load_questions(allocation: dict[int, int], exclude_ids: list[int] | None = None) -> list[dict]:
    """按域分配加载题目（80%新题+20%历史错题），本次已答题目强制排除"""
    all_qs: list[dict] = []
    for did, n in allocation.items():
        qs = get_questions_balanced(
            domain_ids=[did],
            exclude_ids=exclude_ids or None,
            limit=n + 5,
            new_ratio=settings.QUESTION_NEW_RATIO,
        )
        picked = random.sample(qs, min(n, len(qs))) if qs else []
        all_qs.extend(picked)
    random.shuffle(all_qs)
    return all_qs


def _run_answer_loop(questions: list[dict], session_id: int) -> dict:
    total = len(questions)
    correct_count = 0
    per_domain: dict[int, dict] = {}

    for idx, q in enumerate(questions, 1):
        q = shuffle_question(q)
        print_question(q, idx, total)
        q_start = time.time()
        try:
            answer = get_user_answer()
        except KeyboardInterrupt:
            console.print("\n  [dim]诊断已中断[/dim]")
            break
        elapsed = int(time.time() - q_start)

        correct = q.get("correct", "")
        is_correct = answer == correct
        if is_correct:
            correct_count += 1

        print_result(q, answer, is_correct, show_explanation=False)

        did = q.get("domain_id", 0)
        if did not in per_domain:
            per_domain[did] = {"total": 0, "correct": 0}
        per_domain[did]["total"] += 1
        per_domain[did]["correct"] += int(is_correct)

        record_answer(
            session_id=session_id,
            question_id=q["id"],
            domain_id=did,
            subdomain=q.get("subdomain", ""),
            difficulty=q.get("difficulty", 2),
            user_answer=answer,
            correct_answer=correct,
            is_correct=is_correct,
            time_spent=elapsed,
        )

    return {"total": total, "correct": correct_count, "per_domain": per_domain}


def _generate_recommendations(weaknesses: list[dict]) -> list[dict]:
    result = []
    for w in weaknesses:
        d = DOMAINS.get(w.get("domain_id", 0), {})
        urgency = (100 - w.get("weakness_score", 0)) * d.get("weight", 0)
        result.append({
            "domain_id": w.get("domain_id"),
            "domain_name": d.get("name", ""),
            "subdomain": w.get("subdomain", ""),
            "weakness_score": w.get("weakness_score", 0),
            "weight": d.get("weight", 0),
            "urgency": urgency,
        })
    return sorted(result, key=lambda x: -x["urgency"])[:3]


def _show_results(results: dict, weaknesses: list[dict], recs: list[dict]) -> None:
    total = results["total"]
    correct = results["correct"]
    acc = correct / total * 100 if total else 0
    color = "green" if acc >= 70 else "yellow" if acc >= 50 else "red"

    # 本次诊断摘要
    console.print(
        Panel(
            f"  答题总数：[cyan]{total}[/cyan]\n"
            f"  正确数量：[green]{correct}[/green]\n"
            f"  本次正确率：[{color}]{acc:.1f}%[/{color}]",
            title="📋 本次诊断结果",
            border_style=color,
            box=box.ROUNDED,
        )
    )

    # 各域细分
    per_domain = results.get("per_domain", {})
    if per_domain:
        table = Table(box=box.SIMPLE_HEAVY, show_header=True, padding=(0, 1))
        table.add_column("域", style="cyan", width=4)
        table.add_column("名称", min_width=14)
        table.add_column("答题", justify="right", width=6)
        table.add_column("正确率", justify="right", min_width=8)
        for did, stat in sorted(per_domain.items()):
            d = DOMAINS.get(did, {})
            t = stat["total"]
            c = stat["correct"]
            pct = c / t * 100 if t else 0
            pct_style = "green" if pct >= 70 else "yellow" if pct >= 50 else "red"
            table.add_row(
                str(did), d.get("name", ""),
                str(t),
                f"[{pct_style}]{pct:.0f}%[/{pct_style}]",
            )
        console.print(table)

    # 薄弱点
    console.print()
    print_weakness_table(weaknesses)

    # 学习推荐
    if recs:
        console.print("\n  [bold yellow]📚 建议优先学习：[/bold yellow]")
        for i, r in enumerate(recs, 1):
            score = r["weakness_score"]
            weight_pct = r["weight"] * 100
            console.print(
                f"  [bold]{i}.[/bold] 域{r['domain_id']} [cyan]{r['domain_name']}[/cyan]"
                f" — {r['subdomain']}\n"
                f"     掌握分 [red]{score:.0f}[/red]/100  "
                f"考试占比 [yellow]{weight_pct:.0f}%[/yellow]"
            )
    else:
        console.print("\n  [green]暂无明显薄弱点，继续保持！[/green]")
