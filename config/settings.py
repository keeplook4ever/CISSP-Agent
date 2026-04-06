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
    WEAKNESS_THRESHOLD: float = 0.70

    # 知识点缓存：内容字符数低于此值视为不完整，触发在线补充
    MIN_CONTENT_CHARS: int = 500

    # 题目缓存：每个子域最少保有题目数，不足时在线补充
    MIN_QUESTIONS_PER_SUBDOMAIN: int = 30

    # 每日诊断：题目总数
    DAILY_DIAGNOSTIC_COUNT: int = 30

    # 每日诊断：各域达标所需最少答题次数（不足则不纳入"全部达标"判断）
    DOMAIN_PASS_MIN_ATTEMPTS: int = 100


settings = Settings()
