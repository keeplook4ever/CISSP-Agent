"""Claude 动态题目生成"""
from __future__ import annotations

import json
import random
import time

from ai.client import chat
from ai.prompts import QUESTION_GENERATION
from config.domains import DOMAINS
from config.settings import settings
from database.models import insert_question, count_questions_by_subdomain


def generate_questions(
    domain_id: int,
    subdomain: str = None,
    difficulty: int = None,
    count: int = 5,
) -> list[dict]:
    """调用 Claude 生成题目，成功则存入数据库返回题目列表。
    若该子域已有题目达到 MIN_QUESTIONS_PER_SUBDOMAIN，则跳过生成。"""
    domain = DOMAINS.get(domain_id, {})
    domain_name = domain.get("name", f"域{domain_id}")
    sub = subdomain or random.choice(domain.get("subdomains", [domain_name]))
    diff = difficulty or random.randint(1, 3)
    diff_map = {1: "基础", 2: "中级", 3: "高级"}

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

    raw = chat(QUESTION_GENERATION, user_msg, max_tokens=4096)
    if not raw:
        return []

    try:
        # 提取JSON（Claude有时会包裹在```json```中）
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        questions = data.get("questions", [])
    except (json.JSONDecodeError, IndexError):
        return []

    saved = []
    for q in questions:
        q["domain_id"] = domain_id
        q["source"] = "claude"
        if not q.get("id"):
            q["id"] = f"AI-D{domain_id}-{int(time.time()) % 10000:04d}"
        try:
            insert_question(q)
            saved.append(q)
        except Exception:
            pass
    return saved
