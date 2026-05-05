"""针对各域各生成10道题，按错误率从高到低排序"""
import sys
import os
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.domains import DOMAINS
from ai.question_generator import generate_questions

# 按错误率从高到低排序：D2(13%) D1(8.1%) D7(7%) D3(6.9%) D4(5.9%) D6(5.1%) D8(4.5%) D5(3.5%)
DOMAIN_ORDER = [2, 1, 7, 3, 4, 6, 8, 5]
TARGET_PER_DOMAIN = 10
BATCH_SIZE = 5


def generate_for_domain(domain_id: int, target: int) -> int:
    domain = DOMAINS[domain_id]
    domain_name = domain.get("name", f"域{domain_id}")
    subdomains = domain.get("subdomains", [])
    if not subdomains:
        return 0

    generated = 0
    # 随机选子域，每批5题
    batches = (target + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(batches):
        if generated >= target:
            break
        sub = random.choice(subdomains)
        batch_need = min(BATCH_SIZE, target - generated)
        diff = random.choice([2, 2, 3])  # 偏向中高难度

        print(f"  [D{domain_id} {domain_name}] 批次{i+1} | 子域:《{sub}》| 难度:{diff} | 请求{batch_need}题...", flush=True)

        saved = []
        for attempt in range(2):
            saved = generate_questions(
                domain_id=domain_id,
                subdomain=sub,
                difficulty=diff,
                count=batch_need,
                force=True,
            )
            if saved:
                break
            if attempt == 0:
                print(f"    重试中...", flush=True)
                time.sleep(5)

        n = len(saved)
        generated += n
        print(f"    ✓ 生成 {n} 题（域累计: {generated}/{target}）", flush=True)

        if n == 0:
            print(f"    ! API无返回，跳过", flush=True)
            break

        time.sleep(2)

    return generated


def main():
    print("=" * 60)
    print("CISSP错题补充生成 - 每域10道，按错误率排序")
    print("域顺序: D2 > D1 > D7 > D3 > D4 > D6 > D8 > D5")
    print("=" * 60)

    total = 0
    for domain_id in DOMAIN_ORDER:
        domain_name = DOMAINS[domain_id].get("name", "")
        print(f"\n[域{domain_id}] {domain_name}")
        n = generate_for_domain(domain_id, TARGET_PER_DOMAIN)
        total += n
        print(f"  域{domain_id} 完成: {n} 题")

    print(f"\n{'=' * 60}")
    print(f"全部完成！共生成 {total} 道新题")


if __name__ == "__main__":
    main()
