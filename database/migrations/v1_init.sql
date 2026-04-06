-- CISSP Agent 数据库初始化脚本 v1

-- 题库表（本地 JSON 导入 + Claude 动态生成）
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    qid         TEXT UNIQUE NOT NULL,              -- 如 "D1-001"
    domain_id   INTEGER NOT NULL,
    subdomain   TEXT,
    difficulty  INTEGER DEFAULT 2,                 -- 1=易 2=中 3=难
    source      TEXT DEFAULT 'local',              -- 'local' | 'claude'
    question    TEXT NOT NULL,
    option_a    TEXT NOT NULL,
    option_b    TEXT NOT NULL,
    option_c    TEXT NOT NULL,
    option_d    TEXT NOT NULL,
    correct     TEXT NOT NULL,                     -- 'A'|'B'|'C'|'D'
    explanation TEXT,
    tags        TEXT DEFAULT '[]',                 -- JSON 数组
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active   INTEGER DEFAULT 1
);

-- 学习/考试会话表
CREATE TABLE IF NOT EXISTS study_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_type    TEXT NOT NULL,                 -- 'practice'|'exam'|'review'|'study'
    domain_filter   TEXT DEFAULT '[]',             -- JSON 数组，选择的域
    started_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at        DATETIME,
    duration_seconds INTEGER DEFAULT 0,
    total_questions INTEGER DEFAULT 0,
    correct_count   INTEGER DEFAULT 0,
    is_completed    INTEGER DEFAULT 0,
    exam_score      REAL                           -- 模拟考试换算分（0-1000）
);

-- 答题记录表（核心）
CREATE TABLE IF NOT EXISTS answer_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    question_id     INTEGER NOT NULL,
    domain_id       INTEGER NOT NULL,
    subdomain       TEXT,
    difficulty      INTEGER,
    user_answer     TEXT NOT NULL,
    correct_answer  TEXT NOT NULL,
    is_correct      INTEGER NOT NULL,              -- 0|1
    time_spent_sec  INTEGER DEFAULT 0,
    answered_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES study_sessions(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);

-- 各域统计汇总（聚合缓存，每次答题后更新）
CREATE TABLE IF NOT EXISTS domain_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id       INTEGER NOT NULL UNIQUE,
    total_attempts  INTEGER DEFAULT 0,
    correct_count   INTEGER DEFAULT 0,
    accuracy_rate   REAL DEFAULT 0.0,
    avg_time_sec    REAL DEFAULT 0.0,
    last_practiced  DATETIME,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 每日学习进度
CREATE TABLE IF NOT EXISTS daily_progress (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    study_date      DATE NOT NULL UNIQUE,
    day_number      INTEGER,
    minutes_studied INTEGER DEFAULT 0,
    questions_done  INTEGER DEFAULT 0,
    correct_count   INTEGER DEFAULT 0,
    sessions_count  INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 薄弱点记录
CREATE TABLE IF NOT EXISTS weakness_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id       INTEGER NOT NULL,
    subdomain       TEXT,
    weakness_score  REAL NOT NULL,                 -- 0-100，越低越弱
    question_count  INTEGER DEFAULT 0,
    error_count     INTEGER DEFAULT 0,
    identified_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    resolved_at     DATETIME,
    ai_suggestion   TEXT,
    UNIQUE(domain_id, subdomain)
);

-- 50天学习计划
CREATE TABLE IF NOT EXISTS study_plan (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    day_number      INTEGER NOT NULL UNIQUE,
    target_date     DATE,
    domain_id       INTEGER NOT NULL,
    subdomain_focus TEXT,
    objectives      TEXT DEFAULT '[]',             -- JSON 数组
    practice_count  INTEGER DEFAULT 30,
    is_exam_day     INTEGER DEFAULT 0,
    day_type        TEXT DEFAULT 'study',          -- 'study'|'review'|'exam'
    is_completed    INTEGER DEFAULT 0,
    completed_at    DATETIME
);

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_answer_domain ON answer_records(domain_id);
CREATE INDEX IF NOT EXISTS idx_answer_session ON answer_records(session_id);
CREATE INDEX IF NOT EXISTS idx_answer_date ON answer_records(answered_at);
CREATE INDEX IF NOT EXISTS idx_questions_domain ON questions(domain_id, difficulty);
CREATE INDEX IF NOT EXISTS idx_plan_day ON study_plan(day_number);

-- 初始化8个域的统计行
INSERT OR IGNORE INTO domain_stats (domain_id, total_attempts, correct_count, accuracy_rate)
VALUES (1,0,0,0.0),(2,0,0,0.0),(3,0,0,0.0),(4,0,0,0.0),
       (5,0,0,0.0),(6,0,0,0.0),(7,0,0,0.0),(8,0,0,0.0);
