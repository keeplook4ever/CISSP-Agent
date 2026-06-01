-- v5: 多人模式支持 — 为核心表添加 player_id

-- 1. 玩家表
CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO players (id, name) VALUES (1, '默认用户');

-- 2. study_sessions 添加 player_id（兼容 ALTER，列已存在时由 migration runner 忽略报错）
ALTER TABLE study_sessions ADD COLUMN player_id INTEGER NOT NULL DEFAULT 1;

-- 3. 重建 question_stats：PRIMARY KEY 改为 (player_id, question_id)
ALTER TABLE question_stats RENAME TO question_stats_v4;

CREATE TABLE question_stats (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id        INTEGER NOT NULL DEFAULT 1,
    question_id      INTEGER NOT NULL,
    is_attempted     INTEGER NOT NULL DEFAULT 0,
    last_result      INTEGER,
    last_answered_at DATETIME,
    attempt_count    INTEGER NOT NULL DEFAULT 0,
    correct_count    INTEGER NOT NULL DEFAULT 0,
    wrong_count      INTEGER NOT NULL DEFAULT 0,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, question_id),
    FOREIGN KEY (player_id)   REFERENCES players(id),
    FOREIGN KEY (question_id) REFERENCES questions(id)
);

INSERT OR IGNORE INTO question_stats
    (player_id, question_id, is_attempted, last_result, last_answered_at,
     attempt_count, correct_count, wrong_count, updated_at)
SELECT 1, question_id, is_attempted, last_result, last_answered_at,
    attempt_count, correct_count, wrong_count, updated_at
FROM question_stats_v4;

DROP TABLE question_stats_v4;

CREATE INDEX IF NOT EXISTS idx_qstats_player       ON question_stats(player_id);
CREATE INDEX IF NOT EXISTS idx_qstats_attempted    ON question_stats(is_attempted);
CREATE INDEX IF NOT EXISTS idx_qstats_last_result  ON question_stats(last_result);

-- 4. 重建 domain_stats：UNIQUE 改为 (player_id, domain_id)
ALTER TABLE domain_stats RENAME TO domain_stats_v4;

CREATE TABLE domain_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL DEFAULT 1,
    domain_id       INTEGER NOT NULL,
    total_attempts  INTEGER DEFAULT 0,
    correct_count   INTEGER DEFAULT 0,
    accuracy_rate   REAL DEFAULT 0.0,
    avg_time_sec    REAL DEFAULT 0.0,
    last_practiced  DATETIME,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, domain_id),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

INSERT OR IGNORE INTO domain_stats
    (player_id, domain_id, total_attempts, correct_count, accuracy_rate,
     avg_time_sec, last_practiced, updated_at)
SELECT 1, domain_id, total_attempts, correct_count, accuracy_rate,
    avg_time_sec, last_practiced, updated_at
FROM domain_stats_v4;

DROP TABLE domain_stats_v4;

CREATE INDEX IF NOT EXISTS idx_domain_stats_player ON domain_stats(player_id, domain_id);

-- 5. 重建 daily_progress：UNIQUE 改为 (player_id, study_date)
ALTER TABLE daily_progress RENAME TO daily_progress_v4;

CREATE TABLE daily_progress (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL DEFAULT 1,
    study_date      DATE NOT NULL,
    day_number      INTEGER,
    minutes_studied INTEGER DEFAULT 0,
    questions_done  INTEGER DEFAULT 0,
    correct_count   INTEGER DEFAULT 0,
    sessions_count  INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, study_date),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

INSERT OR IGNORE INTO daily_progress
    (player_id, study_date, day_number, minutes_studied,
     questions_done, correct_count, sessions_count, created_at)
SELECT 1, study_date, day_number, minutes_studied,
    questions_done, correct_count, sessions_count, created_at
FROM daily_progress_v4;

DROP TABLE daily_progress_v4;

CREATE INDEX IF NOT EXISTS idx_daily_progress_player ON daily_progress(player_id, study_date);
CREATE INDEX IF NOT EXISTS idx_sessions_player        ON study_sessions(player_id);
