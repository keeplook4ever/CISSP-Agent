"""统计表格组件"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from config.domains import DOMAINS

console = Console()


def print_domain_stats_table(stats: list[dict]) -> None:
    """打印各域正确率统计表"""
    table = Table(title="📊 各域学习统计", box=box.ROUNDED, border_style="blue")
    table.add_column("域", style="cyan", width=4)
    table.add_column("名称", min_width=14)
    table.add_column("答题数", justify="right")
    table.add_column("正确数", justify="right")
    table.add_column("正确率", justify="right", min_width=10)
    table.add_column("状态", justify="center")

    stats_map = {s["domain_id"]: s for s in stats}
    for domain_id, domain in DOMAINS.items():
        s = stats_map.get(domain_id, {})
        total = s.get("total_attempts", 0)
        correct = s.get("correct_count", 0)
        acc = s.get("accuracy_rate", 0)

        if total == 0:
            acc_str = Text("—", style="dim")
            status = "⬜ 未练习"
        else:
            pct = acc * 100
            if pct >= 80:
                acc_str = Text(f"{pct:.1f}%", style="bold green")
                status = "✅ 良好"
            elif pct >= 70:
                acc_str = Text(f"{pct:.1f}%", style="yellow")
                status = "⚠️  需加强"
            else:
                acc_str = Text(f"{pct:.1f}%", style="bold red")
                status = "❌ 薄弱"

        table.add_row(
            str(domain_id),
            domain["name"],
            str(total),
            str(correct),
            acc_str,
            status,
        )
    console.print(table)


def print_session_summary(
    total: int,
    correct: int,
    duration_sec: int,
    session_type: str = "练习",
) -> None:
    """打印会话结束摘要"""
    acc = (correct / total * 100) if total else 0
    mins = duration_sec // 60
    secs = duration_sec % 60

    table = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 2))
    table.add_column("项目", style="dim")
    table.add_column("数值", style="bold")

    table.add_row("总题数", str(total))
    table.add_row("正确数", f"[green]{correct}[/green]")
    table.add_row("错误数", f"[red]{total - correct}[/red]")
    table.add_row("正确率", f"{'[green]' if acc >= 70 else '[red]'}{acc:.1f}%[/]")
    table.add_row("用时", f"{mins}分{secs:02d}秒")

    console.print(f"\n{'='*40}")
    console.print(f"  📋 {session_type}结束")
    console.print(table)
    console.print(f"{'='*40}\n")


def print_study_progress_table(stats: list[dict]) -> None:
    """打印学习模式知识点学习进度表"""
    table = Table(title="📖 知识点学习进度", box=box.ROUNDED, border_style="cyan")
    table.add_column("域", style="cyan", width=4)
    table.add_column("名称", min_width=14)
    table.add_column("已学/总计", justify="center", min_width=10)
    table.add_column("完成度", justify="right", min_width=10)
    table.add_column("最近学习", justify="center", min_width=12)

    stats_map = {s["domain_id"]: s for s in stats}
    for domain_id, domain in DOMAINS.items():
        s = stats_map.get(domain_id, {})
        total_subs = len(domain.get("subdomains", [])) + 1  # +1 = 整体概述
        studied = s.get("topics_studied", 0)
        last_at = (s.get("last_studied_at") or "")[:10] or "—"

        if studied == 0:
            ratio_str = Text(f"0 / {total_subs}", style="dim")
            pct_str = Text("—", style="dim")
        else:
            pct = studied / total_subs * 100
            ratio_str = f"{studied} / {total_subs}"
            if pct >= 80:
                pct_str = Text(f"{pct:.0f}%", style="bold green")
            elif pct >= 50:
                pct_str = Text(f"{pct:.0f}%", style="yellow")
            else:
                pct_str = Text(f"{pct:.0f}%", style="red")

        table.add_row(str(domain_id), domain["name"], ratio_str, pct_str, last_at)
    console.print(table)


def print_weakness_table(weaknesses: list[dict]) -> None:
    """打印薄弱点列表"""
    if not weaknesses:
        console.print("  [green]✅ 暂无明显薄弱点，继续保持！[/green]")
        return

    table = Table(title="⚠️  薄弱点清单", box=box.ROUNDED, border_style="red")
    table.add_column("域", style="cyan", width=4)
    table.add_column("子域", min_width=16)
    table.add_column("掌握分", justify="right")
    table.add_column("答题数", justify="right")
    table.add_column("错题数", justify="right")

    for w in weaknesses:
        d = DOMAINS.get(w.get("domain_id", 0), {})
        score = w.get("weakness_score", 0)
        score_str = Text(f"{score:.0f}", style="bold red" if score < 50 else "red")
        table.add_row(
            str(w.get("domain_id", "")),
            w.get("subdomain") or d.get("name", ""),
            score_str,
            str(w.get("question_count", 0)),
            str(w.get("error_count", 0)),
        )
    console.print(table)


def print_wrong_review(wrong_questions: list[dict]) -> None:
    """答题结束后展示本次所有错题及解析"""
    if not wrong_questions:
        return

    console.print(f"\n{'─'*50}")
    console.print(
        Panel(
            f"  本次共答错 [bold red]{len(wrong_questions)}[/bold red] 题，以下是错题详情与解析",
            title="📝 本次错题回顾",
            border_style="red",
            box=box.ROUNDED,
        )
    )

    for i, q in enumerate(wrong_questions, 1):
        opts = {
            "A": q.get("option_a", ""),
            "B": q.get("option_b", ""),
            "C": q.get("option_c", ""),
            "D": q.get("option_d", ""),
        }
        domain_id = q.get("domain_id", "")
        subdomain = q.get("subdomain", "")
        user_ans = q.get("user_answer", "?")
        correct_ans = q.get("ar_correct") or q.get("correct", "?")
        source_tag = " [dim][AI][/dim]" if q.get("source") == "claude" else ""

        header = (
            f"[bold red]错题 {i}[/bold red]  "
            f"域{domain_id} · {subdomain}{source_tag}"
        )
        body = Text()
        body.append(f"\n{q.get('question', '')}\n\n", style="bold white")
        for label in ["A", "B", "C", "D"]:
            if label == correct_ans:
                body.append(f"  {label}. {opts[label]}\n", style="bold green")
            elif label == user_ans:
                body.append(f"  {label}. {opts[label]}\n", style="bold red")
            else:
                body.append(f"  {label}. {opts[label]}\n")

        body.append(f"\n你选了 ", style="dim")
        body.append(f"{user_ans}", style="bold red")
        body.append(f"  ·  正确答案 ", style="dim")
        body.append(f"{correct_ans}. {opts.get(correct_ans, '')}", style="bold green")

        console.print(Panel(body, title=header, border_style="red", box=box.ROUNDED))

        if q.get("explanation"):
            console.print(
                Panel(
                    q["explanation"],
                    title="💡 解析",
                    border_style="yellow",
                    padding=(0, 1),
                )
            )
