"""数据库连接与初始化。

**为什么用 aiosqlite 而不是标准库 sqlite3**：
sqlite3 是同步阻塞的，在 `async def` 里直接调用会卡住整个事件循环
—— 这正是 S0 反复强调的「异步陷阱」：单请求看着没问题，一上并发全排队。

**为什么路径用 Path(__file__) 而不是相对路径**：
`"./data/app.db"` 是相对「启动目录」解析的，从别的目录启动就会连到另一个空库，
而且**不报错**。用 __file__ 锚定，从哪启动都一样。
"""

from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite

# db.py 位于 src/agent_lab/app/core/，向上 4 层即 agent-lab/ 项目根
#   parents[0]=core  [1]=app  [2]=agent_lab  [3]=src  [4]=agent-lab
DB_PATH = Path(__file__).resolve().parents[4] / "data" / "app.db"

SCHEMA = """
-- ---- S9：用户 ----
-- 密码只存哈希（pbkdf2$迭代次数$salt$hash），永远不存明文。
-- 即使库被拖走，攻击者也拿不到能直接登录的凭据。
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS todos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 多租户：每行都属于某个用户。空串表示 S9 之前的遗留数据，
    -- 由迁移逻辑统一归属到演示账号。
    user_id    TEXT    NOT NULL DEFAULT '',
    title      TEXT    NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);

-- 注意：涉及 user_id 的索引**不能**写在这里。
-- 老库的 sessions/todos 表已存在时，CREATE TABLE IF NOT EXISTS 不会补列，
-- 紧接着的 CREATE INDEX 就会因为"列不存在"让整个启动失败。
-- 这些索引统一放到 _migrate() 之后建（见 POST_MIGRATION_INDEXES）。

-- ---- S4：会话与记忆 ----
-- 会话即一次对话的容器。前端可以用它实现"多轮对话→新建→回顾旧对话"。
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,       -- uuid4，全局唯一
    user_id     TEXT NOT NULL DEFAULT '',  -- 归属用户，隔离他人会话
    title       TEXT NOT NULL,          -- 对话标题（由模型摘要或用户手动取）
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- 每条消息 -- user 提问、assistant 回答、工具结果 -- 一视同仁地存。
-- 这与 agent.py 里只存 user/assistant 不同：这里还包括 tool 角色，
-- 目的是服务重启后完整重建 history，而不是只记住"聊过什么话题"。
CREATE TABLE IF NOT EXISTS session_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,  -- system / user / assistant / tool
    content     TEXT,           -- assistant 可能在调工具时不发正文
    tool_call_id TEXT,          -- 仅 tool 消息用
    tool_calls  TEXT,           -- JSON，仅 assistant 消息用
    created_at  TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_msg_session ON session_messages(session_id, id);

-- 摘要记忆：把旧消息压缩成一段自然语言摘要。
-- 内容可以是多段消息的浓缩版，也可以是一条事实。
CREATE TABLE IF NOT EXISTS session_memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    -- 覆盖的消息区间（左闭右开：[msg_start, msg_end)）
    msg_start   INTEGER NOT NULL,
    msg_end     INTEGER NOT NULL,
    content     TEXT NOT NULL,          -- 摘要正文
    token_count INTEGER NOT NULL,       -- 摘要的 token 数（用于预算计算）
    created_at  TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_mem_session ON session_memories(session_id, msg_start);

-- ---- S6：任务计划（计划是数据，不是对话）----
-- 存下来才能"暂停 → 改参数 → 恢复"，也才能在重启后接着跑。
CREATE TABLE IF NOT EXISTS task_plans (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL DEFAULT '',
    session_id  TEXT,                    -- 关联会话，可为空（独立计划）
    goal        TEXT NOT NULL,            -- 用户原始目标
    status      TEXT NOT NULL DEFAULT 'pending',
                -- pending / running / awaiting_approval / done / failed / cancelled
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plan_steps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id       TEXT NOT NULL,
    idx           INTEGER NOT NULL,       -- 执行顺序，0 基
    action        TEXT NOT NULL,          -- 工具名
    params        TEXT NOT NULL DEFAULT '{}',   -- JSON，可被人工编辑
    description   TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'pending',
                  -- pending / running / done / failed / skipped
    requires_human INTEGER NOT NULL DEFAULT 0,  -- 执行前必须人工确认
    approved      INTEGER NOT NULL DEFAULT 0,   -- 人工是否已确认
    result        TEXT,                   -- JSON 结果
    error         TEXT,
    attempts      INTEGER NOT NULL DEFAULT 0,
    duration_ms   REAL,
    finished_at   TEXT,
    FOREIGN KEY (plan_id) REFERENCES task_plans(id)
);

CREATE INDEX IF NOT EXISTS idx_step_plan ON plan_steps(plan_id, idx);

-- 幂等记录：重放时先查这里，命中就不再执行，避免"重跑一次多发一条评论/多建一条待办"
CREATE TABLE IF NOT EXISTS idempotency_records (
    key         TEXT PRIMARY KEY,   -- sha256(plan_id|idx|action|规范化参数)
    plan_id     TEXT NOT NULL,
    step_idx    INTEGER NOT NULL,
    action      TEXT NOT NULL,
    result      TEXT,               -- 首次执行的返回值，重放时原样返回
    created_at  TEXT NOT NULL
);

-- ---- S7：指标落库 ----
-- trace JSON 文件适合"回放单次对话"，不适合"按天聚合算 P95"。
-- 这里只存聚合需要的标量，一行一次对话，查询走索引，别去扫 JSON。
CREATE TABLE IF NOT EXISTS trace_metrics (
    trace_id           TEXT PRIMARY KEY,
    user_id            TEXT NOT NULL DEFAULT '',
    session_id         TEXT,
    model              TEXT NOT NULL,
    -- 配置指纹：模型+温度+max_tokens+提示词版本+工具版本 的哈希
    config_fingerprint TEXT NOT NULL,
    prompt_version     TEXT NOT NULL,
    tool_version       TEXT NOT NULL,
    question           TEXT,
    started_at         TEXT NOT NULL,   -- ISO 时间，聚合按天用 substr(started_at,1,10)
    duration_ms        REAL NOT NULL,
    prompt_tokens      INTEGER NOT NULL DEFAULT 0,
    completion_tokens  INTEGER NOT NULL DEFAULT 0,
    total_tokens       INTEGER NOT NULL DEFAULT 0,
    cost_cny           REAL NOT NULL DEFAULT 0,
    steps              INTEGER NOT NULL DEFAULT 0,
    tool_calls         INTEGER NOT NULL DEFAULT 0,
    -- completed / max_steps / cost_limit / disconnected / failed / rate_limited
    status             TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_metrics_started ON trace_metrics(started_at);
CREATE INDEX IF NOT EXISTS idx_metrics_fp ON trace_metrics(config_fingerprint, started_at);
"""


# 老库升级清单：(表, 列, 列定义)。
#
# **为什么必须有这一步**：`CREATE TABLE IF NOT EXISTS` 对已存在的表是空操作，
# 不会补新列。S8 时期建的 data/app.db 直接跑 S9 的代码，
# 查询 `WHERE user_id = ?` 会报 "no such column"，而报错发生在业务查询里，
# 看起来完全不像"缺迁移"。显式检查 + ALTER 是唯一可靠的做法。
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("todos", "user_id", "TEXT NOT NULL DEFAULT ''"),
    ("sessions", "user_id", "TEXT NOT NULL DEFAULT ''"),
    ("task_plans", "user_id", "TEXT NOT NULL DEFAULT ''"),
    ("trace_metrics", "user_id", "TEXT NOT NULL DEFAULT ''"),
]


async def _migrate(db: aiosqlite.Connection) -> None:
    for table, column, decl in _MIGRATIONS:
        rows = await db.execute_fetchall(f"PRAGMA table_info({table})")
        if column not in {r["name"] for r in rows}:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    # 索引必须等列补齐之后再建，否则启动直接炸（这条踩过一次，见 SCHEMA 里的注释）
    for ddl in POST_MIGRATION_INDEXES:
        await db.execute(ddl)


POST_MIGRATION_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_todos_user ON todos(user_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, updated_at)",
    "CREATE INDEX IF NOT EXISTS idx_plans_user ON task_plans(user_id, updated_at)",
]


async def init_db() -> None:
    """建库建表。在 lifespan 启动阶段调用，保证表一定存在。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        # row_factory 让 PRAGMA 的返回能按列名取值（迁移逻辑依赖它）
        db.row_factory = aiosqlite.Row
        await db.executescript(SCHEMA)
        await _migrate(db)
        await db.commit()


async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """FastAPI 依赖：每个请求一个连接，响应结束后自动 close。

    `yield` 之前的代码在请求前执行，`finally` 在响应后执行 ——
    这就是 Depends 的「携带清理逻辑」能力，等价于中间件但没有全局副作用。

    ⚠️ 教学简化：每请求建一次连接，生产环境应换成连接池（会在请求间复用）。
    """
    db = await aiosqlite.connect(DB_PATH)
    # 让查询结果支持 row["title"]，而不是只能按索引 row[0]
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
