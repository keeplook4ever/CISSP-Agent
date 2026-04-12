import os
from pathlib import Path

# 尝试加载 .env 文件（开发环境用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
QUESTIONS_DIR = BASE_DIR / "questions" / "bank"


class Settings:
    # Claude API
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MAX_TOKENS: int = 4096

    # 运行模式
    FORCE_OFFLINE: bool = os.environ.get("FORCE_OFFLINE", "").lower() == "true"

    @classmethod
    def is_online(cls) -> bool:
        return bool(cls.ANTHROPIC_API_KEY) and not cls.FORCE_OFFLINE

    # 数据库
    DB_PATH: str = str(DATA_DIR / "cissp.db")

    # 考试参数
    EXAM_TOTAL_QUESTIONS: int = 125
    EXAM_TIME_MINUTES: int = 180
    EXAM_PASS_SCORE: int = 700

    # 练习参数
    DEFAULT_PRACTICE_COUNT: int = 20

    # 学习计划
    TOTAL_DAYS: int = 50
    DAILY_HOURS: float = 3.0

    # 薄弱点阈值（正确率低于此值则标记为薄弱）
    WEAKNESS_THRESHOLD: float = 0.80

    # 知识点缓存：内容字符数低于此值视为不完整，触发在线补充
    MIN_CONTENT_CHARS: int = 500

    # 题目缓存：每个子域最少保有题目数，不足时在线补充
    MIN_QUESTIONS_PER_SUBDOMAIN: int = 30

    # 每日诊断：题目总数
    DAILY_DIAGNOSTIC_COUNT: int = 30

    # 每日诊断：各域达标所需最少答题次数（不足则不纳入"全部达标"判断）
    DOMAIN_PASS_MIN_ATTEMPTS: int = 350

    # 出题策略：新题（未做过）占比 / 历史错题占比
    QUESTION_NEW_RATIO: float = 0.8
    QUESTION_WRONG_RATIO: float = 0.2

    # AI 联网补充题目时的最低难度（1=易, 2=中, 3=难）
    AI_GEN_MIN_DIFFICULTY: int = 2

    # ── 定时自动进入模式 ──────────────────────────────────────────
    # 格式：每项为 dict，包含以下字段：
    #   mode      : 目标模式，可选 "exam" | "practice" | "review" | "study"
    #   weekdays  : 生效星期列表，1=周一 … 7=周日（ISO）；留空 [] 表示每天
    #   start_time: 时间窗口开始，"HH:MM" 格式（24小时制）
    #   end_time  : 时间窗口结束，"HH:MM" 格式（24小时制）
    #   label     : 显示给用户的描述（可选）
    #
    # 示例（已注释）：
    #   每周六日 20:00–23:59 自动进入模拟考试
    #   {"mode": "exam", "weekdays": [6, 7], "start_time": "20:00", "end_time": "23:59", "label": "周末晚间模拟考"}
    #
    # 若要启用，取消注释并修改时间段 / 星期即可；多条规则按顺序匹配，取第一个命中的。
    SCHEDULED_MODES: list = [
        {"mode": "exam",     "weekdays": [6, 7], "start_time": "19:00", "end_time": "23:59", "label": "周末晚间模拟考"},
        # {"mode": "practice", "weekdays": [],     "start_time": "07:00", "end_time": "08:00", "label": "晨间练习"},
        # {"mode": "review",   "weekdays": [],     "start_time": "21:00", "end_time": "22:00", "label": "每日错题复习"},
    ]


settings = Settings()
