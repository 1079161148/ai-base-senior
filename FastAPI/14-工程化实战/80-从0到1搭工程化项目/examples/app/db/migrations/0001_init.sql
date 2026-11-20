-- 0001 初始表：只有最必要的字段
CREATE TABLE IF NOT EXISTS notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL,
    body       TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notes_title ON notes (title);