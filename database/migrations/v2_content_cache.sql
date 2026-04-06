-- v2: 知识点内容本地缓存表
CREATE TABLE IF NOT EXISTS study_content_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key   TEXT UNIQUE NOT NULL,       -- "{domain_id}|{topic}"
    domain_id   INTEGER NOT NULL,
    topic       TEXT NOT NULL,
    content     TEXT NOT NULL,
    char_count  INTEGER NOT NULL DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cache_domain ON study_content_cache(domain_id);
