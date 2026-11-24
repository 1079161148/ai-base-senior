-- 向量检索的最小可用结构（pgvector）
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS docs (
    id        serial PRIMARY KEY,
    content   text NOT NULL,
    embedding vector(3) NOT NULL
);

-- HNSW 索引：近似最近邻，查询快、构建慢、占内存
CREATE INDEX IF NOT EXISTS docs_embedding_idx
    ON docs USING hnsw (embedding vector_cosine_ops);

INSERT INTO docs (content, embedding) VALUES
    ('docker 容器编排',   '[0.9, 0.1, 0.0]'),
    ('kubernetes 集群',   '[0.8, 0.2, 0.1]'),
    ('意大利面做法',      '[0.0, 0.9, 0.1]'),
    ('咖啡烘焙曲线',      '[0.1, 0.8, 0.2]')
ON CONFLICT DO NOTHING;
