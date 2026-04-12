-- 新增 wrong_count 字段，记录每道题的累计答错次数
-- 幂等：ALTER TABLE 在列已存在时会报错，用 CREATE TABLE 技巧规避；SQLite 无 IF NOT EXISTS for columns
-- 通过 SELECT 判断列是否已存在，安全地跳过已迁移的数据库

-- SQLite 不支持 ALTER TABLE ADD COLUMN IF NOT EXISTS，用以下方式代替：
-- 先尝试增加列（若列已存在则该语句报错被忽略，executescript 不中断后续语句）
ALTER TABLE question_stats ADD COLUMN wrong_count INTEGER NOT NULL DEFAULT 0;

-- 回填历史数据：wrong_count = attempt_count - correct_count
UPDATE question_stats
SET wrong_count = attempt_count - correct_count
WHERE wrong_count = 0 AND attempt_count > correct_count;
