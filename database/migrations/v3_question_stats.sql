-- 题目状态追踪表（每道题一条记录，记录是否做过、上次结果、上次做题时间）
CREATE TABLE IF NOT EXISTS question_stats (
    question_id      INTEGER PRIMARY KEY,
    is_attempted     INTEGER NOT NULL DEFAULT 0,   -- 0=未做过, 1=已做过
    last_result      INTEGER,                       -- NULL=未做, 0=上次答错, 1=上次答对
    last_answered_at DATETIME,
    attempt_count    INTEGER NOT NULL DEFAULT 0,
    correct_count    INTEGER NOT NULL DEFAULT 0,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id)
);

CREATE INDEX IF NOT EXISTS idx_qstats_attempted ON question_stats(is_attempted);
CREATE INDEX IF NOT EXISTS idx_qstats_last_result ON question_stats(last_result);

-- 从历史 answer_records 回填（幂等：INSERT OR IGNORE 保证安全，多次执行无副作用）
INSERT OR IGNORE INTO question_stats
    (question_id, is_attempted, last_result, last_answered_at, attempt_count, correct_count)
SELECT
    ar_latest.question_id,
    1,
    ar_latest.is_correct,
    ar_latest.answered_at,
    ar_counts.attempt_count,
    ar_counts.correct_count
FROM (
    -- 每道题最近一次作答记录
    SELECT question_id, is_correct, answered_at
    FROM answer_records ar1
    WHERE answered_at = (
        SELECT MAX(answered_at)
        FROM answer_records ar2
        WHERE ar2.question_id = ar1.question_id
    )
    GROUP BY question_id
) AS ar_latest
JOIN (
    -- 每道题累计统计
    SELECT
        question_id,
        COUNT(*)        AS attempt_count,
        SUM(is_correct) AS correct_count
    FROM answer_records
    GROUP BY question_id
) AS ar_counts ON ar_latest.question_id = ar_counts.question_id;
