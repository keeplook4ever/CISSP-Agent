"""Claude 动态题目生成"""
from __future__ import annotations

import json
import random
import time
import uuid
from typing import Optional

from ai.client import chat, FAST_MODEL
from ai.prompts import QUESTION_GENERATION
from config.domains import DOMAINS
from config.settings import settings
from database.models import insert_question, count_questions_by_subdomain, count_questions_by_domain


def generate_questions(
    domain_id: int,
    subdomain: str = None,
    difficulty: int = None,
    count: int = 5,
    min_difficulty: int = 1,
    force: bool = False,
) -> list[dict]:
    """调用 Claude 生成题目，成功则存入数据库返回题目列表。
    若该子域已有题目达到 MIN_QUESTIONS_PER_SUBDOMAIN，则跳过生成。
    min_difficulty: 生成题目的最低难度（1=易,2=中,3=难），联网补充时建议传2。
    force: 为 True 时跳过阈值检查，强制生成 count 道题（考试模式使用）。"""
    domain = DOMAINS.get(domain_id, {})
    domain_name = domain.get("name", f"域{domain_id}")
    sub = subdomain or random.choice(domain.get("subdomains", [domain_name]))
    diff = difficulty or random.randint(max(min_difficulty, 1), 3)
    diff_map = {1: "基础", 2: "中级", 3: "高级"}

    if force:
        actual_count = count
    else:
        # 检查本地已有题数，计算实际需要生成的数量
        existing = count_questions_by_subdomain(domain_id, sub)
        needed = max(0, settings.MIN_QUESTIONS_PER_SUBDOMAIN - existing)
        actual_count = min(count, needed)
        if actual_count <= 0:
            return []  # 本地已满足阈值，无需消耗 token

    user_msg = (
        f"请为CISSP域{domain_id}【{domain_name}】中的子域【{sub}】"
        f"生成{actual_count}道{diff_map[diff]}难度（difficulty={diff}）的选择题。"
        f"题目ID格式：AI-D{domain_id}-{{三位数字}}。"
    )

    try:
        # fill-bank 批量生成用 Haiku（速度快 5-10 倍）
        # max_tokens 按题数估算：每题约 800 token（含解析），留 20% 余量
        estimated_tokens = max(1500, actual_count * 900)
        raw = chat(QUESTION_GENERATION, user_msg, max_tokens=estimated_tokens, model=FAST_MODEL)
    except Exception:
        return []

    if not raw:
        return []

    try:
        # 提取JSON（Claude有时会包裹在```json```中）
        text = raw
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        questions = data.get("questions", [])
    except (json.JSONDecodeError, IndexError, ValueError):
        return []

    saved = []
    for q in questions:
        q["domain_id"] = domain_id
        q["source"] = "claude"
        # 始终用 UUID 生成唯一 ID，避免 AI 返回重复 ID 导致 INSERT OR IGNORE 跳过
        q["id"] = f"AI-D{domain_id}-{uuid.uuid4().hex[:8]}"
        # 入库前随机化选项顺序，correct 和解析同步绑定，避免运行时标签空间混乱
        q = _randomize_options(q)
        try:
            row_id = insert_question(q)
            if row_id:  # INSERT OR IGNORE 跳过时 lastrowid=0，不计入 saved
                saved.append(q)
        except Exception:
            pass
    return saved


def _randomize_options(q: dict) -> dict:
    """入库前随机化选项顺序，同步更新 correct 和解析中的字母引用。"""
    import re
    labels = ["A", "B", "C", "D"]
    order = labels[:]
    random.shuffle(order)
    # order[i] = 旧标签，labels[i] = 新标签
    old_to_new = {old: new for new, old in zip(labels, order)}
    opts = q["options"]
    new_opts = {labels[i]: opts[order[i]] for i in range(4)}
    new_correct = old_to_new[q["correct"]]

    explanation = q.get("explanation", "")
    if explanation:
        ph = {old: f"\x00{new}\x00" for old, new in old_to_new.items()}
        # 1. "A项" / "A选项" / "A错误" / "A正确"
        explanation = re.sub(
            r'([ABCD])(?=[项选错正])',
            lambda m: ph.get(m.group(1), m.group(1)),
            explanation,
        )
        # 2. "选项A"
        explanation = re.sub(
            r'(?<=选项)([ABCD])',
            lambda m: ph.get(m.group(1), m.group(1)),
            explanation,
        )
        # 3. "答案A" / "答案(A)" / "答案（A）"
        explanation = re.sub(
            r'(?<=答案)([（(]?)([ABCD])',
            lambda m: m.group(1) + ph.get(m.group(2), m.group(2)),
            explanation,
        )
        explanation = explanation.replace("\x00", "")

    result = dict(q)
    result["options"] = new_opts
    result["correct"] = new_correct
    result["explanation"] = explanation
    return result


def fill_question_bank(
    domain_ids: Optional[list[int]] = None,
    target_per_domain: int = 30,
    batch_size: int = 3,
    on_progress=None,
) -> dict[int, int]:
    """为指定域批量生成题目，直至每域达到 target_per_domain 道题。

    Args:
        domain_ids: 要补充的域列表，默认为 [5, 6, 7, 8]
        target_per_domain: 每域目标题数
        batch_size: 每次 API 调用生成的题数
        on_progress: 可选回调 fn(domain_id, subdomain, generated_count)

    Returns:
        {domain_id: 新增题数} 的字典
    """
    target_domain_ids = domain_ids or [5, 6, 7, 8]
    results: dict[int, int] = {}

    for domain_id in target_domain_ids:
        domain = DOMAINS.get(domain_id, {})
        subdomains = domain.get("subdomains", [])
        if not subdomains:
            results[domain_id] = 0
            continue

        domain_generated = 0
        # 每个子域的目标：均匀分配，至少 3 题
        target_per_sub = max(3, (target_per_domain + len(subdomains) - 1) // len(subdomains))

        for sub in subdomains:
            # 先检查域总量是否已达标
            if count_questions_by_domain().get(domain_id, 0) >= target_per_domain:
                break

            # 对同一子域最多循环生成 10 批，防止无限消耗
            for _ in range(10):
                if count_questions_by_domain().get(domain_id, 0) >= target_per_domain:
                    break
                if count_questions_by_subdomain(domain_id, sub) >= target_per_sub:
                    break
                # 调用前通知（n=None 表示"正在请求 API，请稍候"）
                if on_progress:
                    on_progress(domain_id, sub, None)
                # 最多重试 2 次，应对瞬时网络抖动
                saved = []
                for attempt in range(2):
                    saved = generate_questions(domain_id, sub, count=batch_size,
                                               min_difficulty=settings.AI_GEN_MIN_DIFFICULTY)
                    if saved:
                        break
                    if attempt == 0:
                        time.sleep(3)
                n = len(saved)
                domain_generated += n
                # 调用后通知实际结果
                if on_progress:
                    on_progress(domain_id, sub, n)
                if n == 0:
                    break  # 两次均无返回则跳过此子域

        results[domain_id] = domain_generated

    return results
