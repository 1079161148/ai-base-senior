-- 只在 PostgreSQL 数据目录为空的首次启动时执行
CREATE TABLE IF NOT EXISTS articles (
    id         serial PRIMARY KEY,
    title      text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO articles (title) VALUES
    ('Docker Compose 编排实战'),
    ('PostgreSQL 数据持久化');
