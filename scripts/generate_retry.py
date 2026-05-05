"""补充生成失败域的题目，带延时重试"""
import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.domains import DOMAINS
from ai.question_generator import generate_questions

# 需要补充的域及目标数量
RETRY_TARGETS = {
    7: 5,   # 上轮只生成了5题，补5题
    8: 5,   # 上轮只生成了5题，补5题
}
BATCH_SIZE = 5


def generate_for_domain(domain_id: int, target: int) -> int:
    domain = DOMAINS[domain_id]
    domain_name = domain.get("name", f"域{domain_id}")
    subdomains = domain.get("subdomains", [])
    if not subdomains:
        return 0

    generated = 0
    batches = (target + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(batches):
        if generated >= target:
            break
        sub = random.choice(subdomains)
        batch_need = min(BATCH_SIZE, target - generated)
        diff = random.choice([2, 2, 3])

        print(f"  [D{domain_id} {domain_name}] 批次{i+1} | 子域:《{sub}》| 难度:{diff} | 请求{batch_need}题...", flush=True)

        saved = []
        for attempt in range(3):  # 最多重试3次
            saved = generate_questions(
                domain_id=domain_id,
                subdomain=sub,
                difficulty=diff,
                count=batch_need,
                force=True,
            )
            if saved:
                break
            wait = 10 * (attempt + 1)
            print(f"    重试{attempt+1}，等待{wait}秒...", flush=True)
            time.sleep(wait)

        n = len(saved)
        generated += n
        print(f"    ✓ 生成 {n} 题（域累计: {generated}/{target}）", flush=True)

        if n == 0:
            print(f"    ! 跳过此批次", flush=True)

        time.sleep(3)

    return generated


def main():
    print("=" * 60)
    print("CISSP题库补充生成 - 修复失败域")
    print("=" * 60)

    total = 0
    for domain_id, target in RETRY_TARGETS.items():
        domain_name = DOMAINS[domain_id].get("name", "")
        print(f"\n[域{domain_id}] {domain_name}，目标补充: {target} 题")
        n = generate_for_domain(domain_id, target)
        total += n
        print(f"  域{domain_id} 完成: {n}/{target} 题")
        time.sleep(5)  # 域间间隔

    print(f"\n{'=' * 60}")
    print(f"补充完成！本轮新增 {total} 道题")


if __name__ == "__main__":
    main()
