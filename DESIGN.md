# CISSP 中文学习+考试模拟 Agent 设计文档

## Context

用户需要在 50 天内（每天 3 小时）通过 CISSP 考试。需要一个中文版的 CLI 学习系统，能够：
- 按 8 个域进行知识点学习和题目练习
- 模拟 CISSP CAT 自适应考试（125题/3小时）
- 每轮测试后分析薄弱点，针对性强化训练
- 生成 50 天个性化学习计划

---

## 技术选型

- **Python 3.11+** + `rich`（终端 UI）+ `click`（CLI 框架）
- **Claude API**（claude-sonnet-4-6）：动态出题 + 答案解析 + 薄弱点分析
- **SQLite**（sqlite3 内置）：进度追踪
- **离线优先**：本地 JSON 题库可独立运行，在线模式启用 Claude 增强

---

## 项目结构

```
cissp-agent/
├── main.py                      # CLI 入口 + 交互式主菜单
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py              # 从环境变量读取配置（ANTHROPIC_API_KEY）
│   └── domains.py               # 8 个域的元数据（名称/权重/子域列表）
├── database/
│   ├── connection.py            # SQLite 连接管理
│   ├── models.py                # 建表 + CRUD 操作
│   └── migrations/v1_init.sql   # 初始化 SQL
├── questions/
│   ├── loader.py                # 加载本地 JSON 题库
│   └── bank/
│       ├── domain1.json         # 每域 30 道题，共 240 题
│       ├── domain2.json
│       ├── ...
│       └── domain8.json
├── ai/
│   ├── client.py                # Anthropic SDK 封装
│   ├── prompts.py               # 所有 System Prompt（中文）
│   ├── question_generator.py    # 动态题目生成
│   ├── answer_analyzer.py       # 答案深度解析
│   └── weakness_analyzer.py     # 薄弱点分析报告
├── modes/
│   ├── study_mode.py            # 学习模式：知识点讲解
│   ├── practice_mode.py         # 练习模式：选题答题
│   ├── exam_mode.py             # 模拟考试（CAT 自适应）
│   └── review_mode.py           # 错题复习
├── analysis/
│   ├── weakness_detector.py     # 多维度薄弱点计算
│   ├── progress_tracker.py      # 进度追踪
│   └── report_generator.py      # 报告生成
├── plan/
│   └── study_plan.py            # 50 天计划生成器
└── ui/
    └── cli/
        ├── menus.py             # rich 菜单组件
        ├── display.py           # 题目/统计展示
        └── tables.py            # 统计表格
```

---

## 数据库 Schema（7 张核心表）

| 表名 | 说明 |
|------|------|
| `questions` | 题库（本地+Claude生成） |
| `study_sessions` | 学习/考试会话 |
| `answer_records` | 逐题答题记录（最核心） |
| `domain_stats` | 各域正确率汇总 |
| `daily_progress` | 每日完成情况 |
| `weakness_records` | 薄弱点识别记录 |
| `study_plan` | 50 天计划 |

---

## 核心功能模块

### 1. CLI 主菜单（`main.py`）

```
╔══════════════════════════════════════╗
║    CISSP 中文学习系统 | 第12天/50天    ║
╚══════════════════════════════════════╝
[1] 学习模式 - 知识点讲解
[2] 练习模式 - 选题练习（可选域）
[3] 模拟考试 - 125题/3小时
[4] 错题复习 - 薄弱点强化
[5] 学习报告 - 进度统计
[6] 50天计划 - 查看/重生成
[0] 退出
```

### 2. 练习模式（`modes/practice_mode.py`）

- 可选域/子域/难度
- 即时反馈（练习模式显示答对/错 + 解析）
- 每题记录答题时间
- 结束时展示薄弱点分析

### 3. 模拟考试 CAT 引擎（`modes/exam_mode.py`）

- 简化版 IRT：维护能力估计值（-3 到 +3）
- 按答对/答错动态调整难度
- 8 个域按权重分配题目

**域权重 → 题目分配（125题）：**

| 域 | 名称 | 权重 | 题数 |
|----|------|------|------|
| D1 | 安全与风险管理 | 16% | 20 |
| D2 | 资产安全 | 10% | 13 |
| D3 | 安全架构与工程 | 13% | 16 |
| D4 | 通信与网络安全 | 13% | 16 |
| D5 | 身份与访问管理 | 13% | 16 |
| D6 | 安全评估与测试 | 12% | 15 |
| D7 | 安全运营 | 13% | 16 |
| D8 | 软件开发安全 | 10% | 13 |

### 4. 薄弱点分析（`analysis/weakness_detector.py`）

多维度加权评分（0-100，越低越弱）：
- 正确率（60% 权重）
- 答题用时（20% 权重，超时扣分）
- 进步趋势（20% 权重，持续错误加重）

低于 70% 触发薄弱点标记 → Claude 生成针对性复习建议

### 5. AI 模块（`ai/` 目录）

4 个核心 System Prompt：
- `QUESTION_GENERATION`：按域/子域/难度动态出题
- `ANSWER_EXPLANATION`：深度解析（为什么对/为什么其他选项错/记忆技巧）
- `WEAKNESS_ANALYSIS`：分析答题数据，生成个性化改进报告
- `STUDY_GUIDE`：知识点讲解（CISSP 管理者思维视角）

### 6. 50 天学习计划（`plan/study_plan.py`）

| 天数 | 域 | 说明 |
|------|-----|------|
| 第 1-8 天 | D1 | 安全与风险管理（权重最高） |
| 第 9-14 天 | D3 | 安全架构与工程 |
| 第 15-20 天 | D4 | 通信与网络安全 |
| 第 21-26 天 | D5 | 身份与访问管理 |
| 第 27-31 天 | D6 | 安全评估与测试 |
| 第 32-37 天 | D7 | 安全运营 |
| 第 38-41 天 | D2 | 资产安全 |
| 第 42-45 天 | D8 | 软件开发安全 |
| 第 46-50 天 | 综合 | 模拟考试+薄弱点强化 |

每 7 天安排一次阶段性全域模拟测验。

---

## 题库 JSON 格式

```json
{
  "domain_id": 1,
  "domain_name": "安全与风险管理",
  "version": "2024.1",
  "questions": [
    {
      "id": "D1-001",
      "subdomain": "风险管理概念",
      "difficulty": 2,
      "question": "SLE（单一损失期望）的计算公式是？",
      "options": {
        "A": "资产价值 × 暴露因子",
        "B": "年度损失期望 ÷ 发生频率",
        "C": "资产价值 + 恢复成本",
        "D": "暴露因子 × 年度发生频率"
      },
      "correct": "A",
      "explanation": "SLE = AV × EF（资产价值 × 暴露因子）。ALE = SLE × ARO。",
      "tags": ["SLE", "定量风险", "ALE"]
    }
  ]
}
```

---

## 验证方式

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 初始化（建库 + 生成计划）
python main.py init

# 3. 验证题库加载
python main.py practice --domain 1 --count 5

# 4. 测试考试模式
python main.py exam

# 5. 查看薄弱点报告
python main.py report --type overall

# 6. 在线模式（需设置 API key）
export ANTHROPIC_API_KEY=your_key
python main.py study --domain 1
```

---

## 运行环境

- Python 3.11+
- 工作目录：`/Users/keeplook4ever/Desktop/CISSP-Agent/`
- 数据库：`data/cissp.db`（自动创建）
- API Key：环境变量 `ANTHROPIC_API_KEY`（可选，不设则离线模式）
