"""题库 JSON 文件加载器"""
import json
from pathlib import Path
from config.settings import QUESTIONS_DIR
from database.models import insert_question, count_questions_by_domain


def load_all_banks() -> int:
    """加载所有域题库到数据库，返回导入题目数"""
    total = 0
    for domain_id in range(1, 9):
        path = QUESTIONS_DIR / f"domain{domain_id}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for q in data.get("questions", []):
            q["domain_id"] = domain_id
            insert_question(q)
            total += 1
    return total


def ensure_questions_loaded() -> None:
    """确保题库已加载（首次运行时导入）"""
    counts = count_questions_by_domain()
    if sum(counts.values()) < 10:
        load_all_banks()
