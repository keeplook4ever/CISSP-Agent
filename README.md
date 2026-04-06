# CISSP 中文学习 + 考试模拟 Agent

基于 Claude AI 的 CISSP 中文 CLI 学习系统，帮助你在 50 天内系统备考 CISSP 认证。

---

## 功能特性

- **学习模式**：按 8 个域逐域讲解知识点（CISSP 管理者思维视角）
- **练习模式**：可选域/子域/难度，即时 AI 解析
- **模拟考试**：125 题 / 3 小时 CAT 自适应考试引擎（简化 IRT 算法）
- **错题复习**：自动识别薄弱点，针对性强化训练
- **学习报告**：多维度进度统计与改进建议
- **50 天计划**：个性化学习路径生成与调整

---

## 技术栈

| 组件 | 说明 |
|------|------|
| Python 3.11+ | 运行环境 |
| [Claude API](https://docs.anthropic.com) (claude-sonnet-4-6) | 动态出题 / 解析 / 薄弱点分析 |
| SQLite | 本地进度追踪（7 张核心表） |
| `rich` | 终端 UI |
| `click` | CLI 框架 |

**离线优先**：本地 JSON 题库（240 题，每域 30 题）可独立运行；设置 API Key 后启用 Claude 增强功能。

---

## 快速开始

### 1. 克隆 & 安装依赖

```bash
git clone <repo-url>
cd CISSP-Agent
pip install -r requirements.txt
```

### 2. 配置 API Key（可选，不设则离线模式）

```bash
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY=your_key
```

> **安全提示**：严禁将 API Key 硬编码或提交到代码库，必须通过环境变量注入。

### 3. 初始化（建库 + 生成学习计划）

```bash
python main.py init
```

### 4. 开始学习

```bash
# 总菜单模式
python main.py

# 练习模式（离线）
python main.py practice --domain 1 --count 5

# 模拟考试
python main.py exam

# 学习模式（需 API Key）
python main.py study --domain 1

# 查看薄弱点报告
python main.py report --type overall
```

---

## 项目结构

```
cissp-agent/
├── main.py                      # CLI 入口 + 交互式主菜单
├── requirements.txt
├── .env.example
├── config/                      # 配置：环境变量读取、8 域元数据
├── database/                    # SQLite 连接 + 建表 + CRUD
├── questions/
│   └── bank/                    # 本地题库 domain1.json ~ domain8.json
├── ai/                          # Anthropic SDK 封装、出题、解析、薄弱点分析
├── modes/                       # 学习 / 练习 / 考试 / 复习 四大模式
├── analysis/                    # 薄弱点计算、进度追踪、报告生成
├── plan/                        # 50 天学习计划生成器
└── ui/cli/                      # rich 菜单 / 题目展示 / 统计表格
```

---

## CISSP 8 域题目分配（模拟考试 125 题）

| 域 | 名称 | 权重 | 题数 |
|----|------|:----:|:----:|
| D1 | 安全与风险管理 | 16% | 20 |
| D2 | 资产安全 | 10% | 13 |
| D3 | 安全架构与工程 | 13% | 16 |
| D4 | 通信与网络安全 | 13% | 16 |
| D5 | 身份与访问管理 | 13% | 16 |
| D6 | 安全评估与测试 | 12% | 15 |
| D7 | 安全运营 | 13% | 16 |
| D8 | 软件开发安全 | 10% | 13 |

---

## 50 天学习路径

| 天数 | 域 | 说明 |
|------|-----|------|
| 第 1–8 天 | D1 | 安全与风险管理（权重最高） |
| 第 9–14 天 | D3 | 安全架构与工程 |
| 第 15–20 天 | D4 | 通信与网络安全 |
| 第 21–26 天 | D5 | 身份与访问管理 |
| 第 27–31 天 | D6 | 安全评估与测试 |
| 第 32–37 天 | D7 | 安全运营 |
| 第 38–41 天 | D2 | 资产安全 |
| 第 42–45 天 | D8 | 软件开发安全 |
| 第 46–50 天 | 综合 | 模拟考试 + 薄弱点强化 |

每 7 天安排一次阶段性全域模拟测验。

---

## 运行环境

- Python 3.11+
- 数据库：`data/cissp.db`（自动创建，无需手动操作）
- API Key：环境变量 `ANTHROPIC_API_KEY`（可选）
