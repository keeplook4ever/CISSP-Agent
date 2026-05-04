"""批量生成300道CISSP题目，按考试权重平衡各知识域"""
import sys
import os
import time
import random

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.domains import DOMAINS
from database.models import count_questions_by_domain
from ai.question_generator import generate_questions

# 按CISSP考试权重分配300道题
DOMAIN_TARGETS = {
    1: 48,  # 16%
    2: 30,  # 10%
    3: 39,  # 13%
    4: 39,  # 13%
    5: 39,  # 13%
    6: 36,  # 12%
    7: 39,  # 13%
    8: 30,  # 10%
}

BATCH_SIZE = 5  # 每次API调用生成5道题


def generate_for_domain(domain_id: int, target: int) -> int:
    """为指定域生成target道新题，返回实际生成数量"""
    domain = DOMAINS[domain_id]
    subdomains = domain.get("subdomains", [])
    if not subdomains:
        return 0

    generated = 0
    # 按子域均匀分配，每子域目标题数
    per_sub = max(3, (target + len(subdomains) - 1) // len(subdomains))

    # 随机打乱子域顺序，让题目更多样
    sub_list = subdomains[:]
    random.shuffle(sub_list)

    for sub in sub_list:
        if generated >= target:
            break
        remaining = target - generated
        # 当前子域需要生成的数量（不超过per_sub，也不超过remaining）
        sub_target = min(per_sub, remaining)

        batches_done = 0
        sub_generated = 0
        while sub_generated < sub_target and batches_done < 6:
            batch_need = min(BATCH_SIZE, sub_target - sub_generated)
            diff = random.choice([1, 2, 2, 3])  # 偏向中等难度

            print(f"  [域{domain_id}] {sub} | 批次{batches_done+1} | 请求{batch_need}题...", flush=True)

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
            sub_generated += n
            generated += n
            batches_done += 1
            print(f"    ✓ 生成 {n} 题（子域累计: {sub_generated}，域累计: {generated}/{target}）", flush=True)

            if n == 0:
                print(f"    ! API无返回，跳过此子域", flush=True)
                break

            # API限速保护
            time.sleep(2)

    return generated


def main():
    print("=" * 60)
    print("CISSP题库批量生成 - 目标：300道新题")
    print("=" * 60)

    # 显示当前题库状态
    current = count_questions_by_domain()
    total_current = sum(current.values())
    print(f"\n当前题库: {total_current} 道题")
    for did, cnt in sorted(current.items()):
        target = DOMAIN_TARGETS.get(did, 0)
        print(f"  域{did} {DOMAINS[did]['name']}: {cnt} 题  → 新增目标: {target} 题")

    print(f"\n开始生成，预计需要约 {300 // BATCH_SIZE * 3} 次API调用...\n")

    total_generated = 0
    domain_results = {}

    for domain_id in sorted(DOMAIN_TARGETS.keys()):
        target = DOMAIN_TARGETS[domain_id]
        name = DOMAINS[domain_id]["name"]
        print(f"\n{'='*50}")
        print(f"域{domain_id}: {name}  目标: {target} 题")
        print(f"{'='*50}")

        n = generate_for_domain(domain_id, target)
        domain_results[domain_id] = n
        total_generated += n
        print(f"  域{domain_id} 完成: 新增 {n} 题")

        # 域间延迟
        if domain_id < 8:
            time.sleep(3)

    # 汇总报告
    print("\n" + "=" * 60)
    print("生成完成！汇总报告：")
    print("=" * 60)
    final = count_questions_by_domain()
    for did in sorted(DOMAIN_TARGETS.keys()):
        name = DOMAINS[did]["name"]
        new = domain_results.get(did, 0)
        total = final.get(did, 0)
        print(f"  域{did} {name}: +{new} 题（库存: {total} 题）")

    total_final = sum(final.values())
    print(f"\n题库总量: {total_current} → {total_final} 道题")
    print(f"本次新增: {total_generated} 道题")


if __name__ == "__main__":
    main()
