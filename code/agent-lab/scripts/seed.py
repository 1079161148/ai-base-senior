"""演示数据播种：让项目"打开就有东西可看"。

**为什么需要它**：
一个空库的项目演示起来非常尴尬 —— 会话页是空的、文档页是空的、
指标页只有一根柱子和 0 次请求，观众会怀疑"这东西真的跑过吗"。
这个脚本把三类数据一次准备好：账号、业务数据、指标样本。

用法：

    uv run python scripts/seed.py                 # 全部：账号 + 待办 + 文档 + 指标
    uv run python scripts/seed.py --no-metrics    # 不造指标（想看真实数据时）
    uv run python scripts/seed.py --warmup 8      # 额外发 8 条真实对话（会花钱）
    uv run python scripts/seed.py --reset         # 先清空演示账号的业务数据

**关于 --metrics 的诚实说明**：
它直接往 `trace_metrics` 表写样本，不是真实请求。这样做的原因是
演示看板需要 7 天的分布和几条失败记录，用真实请求凑的话
既慢（每次几秒）又贵（每次几分钱），而且很难精确造出"P95 抖一下"的效果。
真实请求请用 `--warmup`，它走完整的 HTTP + Agent 链路。
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 允许 `python scripts/seed.py` 直接跑（不用先 install）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import aiosqlite  # noqa: E402

from agent_lab.app.core.config import settings  # noqa: E402
from agent_lab.app.core.db import DB_PATH, init_db  # noqa: E402
from agent_lab.app.services import users as user_svc  # noqa: E402

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed"

TODOS = [
    ("整理 RAG 检索的评测基线", 0),
    ("把上下文预算的阈值调成 70%", 1),
    ("补一份工具调用的失败重试测试", 0),
    ("给计划执行加上人工审批节点", 1),
    ("写 trace 回放的使用说明", 0),
    ("把限流从内存换成 Redis", 0),
]

QUESTIONS = [
    "帮我列出所有待办",
    "接口超时怎么处理？",
    "什么是 RRF 混合检索？",
    "把「写 trace 回放的使用说明」标记为完成",
    "上下文超预算了会怎么办",
    "这个项目怎么部署到服务器",
    "解释一下幂等键的作用",
    "待办一共有几条",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def seed_todos(db: aiosqlite.Connection, user_id: str) -> int:
    existing = await db.execute_fetchall(
        "SELECT COUNT(1) AS n FROM todos WHERE user_id = ?", (user_id,)
    )
    if existing and existing[0]["n"] > 0:
        print(f"  · 待办已存在 {existing[0]['n']} 条，跳过")
        return 0

    created = _now()
    for title, done in TODOS:
        await db.execute(
            "INSERT INTO todos (user_id, title, done, created_at) VALUES (?, ?, ?, ?)",
            (user_id, title, done, created.isoformat(timespec="seconds")),
        )
    await db.commit()
    return len(TODOS)


_pg_ready = False


async def _ensure_pg() -> bool:
    """把连接池准备好（幂等）。

    服务和脚本是两条独立的执行路径：服务启动时 lifespan 会 create_pool()，
    脚本里没人替我们建池。而且 create_pool 只设置内部 `_pool`，
    ingest / get_pg_fastapi 读的是 `_pool_for_fastapi` —— 两个都得设。
    """
    global _pg_ready
    if _pg_ready:
        return True

    from agent_lab.app.core import pg

    try:
        pool = await pg.create_pool()
        pg.set_pool(pool)
        await pg.init_pg()
        _pg_ready = True
        return True
    except Exception as exc:  # noqa: BLE001 - 这里就是要吞掉并给出人话提示
        print(f"  ! Postgres 不可用（{exc}），跳过与文档相关的步骤")
        print("    提示：先 docker compose up -d pg，并确认 .env 里的 PG_DSN")
        return False


async def claim_legacy_pg_documents(user_id: str) -> int:
    """把 S9 之前索引、没有归属的文档划给演示账号。

    不做的后果：升级后文档列表只剩新传的那几份，老文档虽然还在库里，
    但因为 `user_id = ''` 谁都查不到 —— 表现为"我的文档凭空消失了"。
    """
    if not await _ensure_pg():
        return 0

    from agent_lab.app.core import pg

    pool = pg.get_pool()
    if pool is None:
        return 0
    async with pool.acquire() as conn:
        status = await conn.execute(
            "UPDATE documents SET user_id = $1 WHERE user_id = ''", user_id
        )
    # asyncpg 返回 "UPDATE 3" 这样的字符串
    return int(status.split()[-1]) if status else 0


async def seed_documents(user_id: str) -> int:
    """上传 data/seed 下的示例文档。需要 Postgres 在跑。"""
    if not SEED_DIR.exists():
        print("  · 没有 data/seed 目录，跳过文档")
        return 0
    if not await _ensure_pg():
        return 0

    from agent_lab.app.core import pg
    from agent_lab.app.services.rag import ingest

    count = 0
    try:
        for path in sorted(SEED_DIR.glob("*.md")):
            meta = await ingest.ingest_file(path, user_id=user_id)
            print(f"  · 已索引 {path.name}：{meta['chunk_count']} 块")
            count += 1
    finally:
        # 脚本退出前必须关池：不关的话事件循环关闭时会报
        # "Task was destroyed but it is pending"，看起来像有 bug
        await pg.close_pool()
    return count


async def seed_metrics(db: aiosqlite.Connection, user_id: str, days: int = 7) -> int:
    """造一份"看起来像真的"指标样本。

    刻意包含：
    - 不同日期的量差（近两天多、远端少）
    - 少量失败（status != completed）—— 全绿的成功率反而是减分项
    - 延迟抖动（让 P95 明显高于 P50，曲线才有看头）
    """
    # 不做"已存在就跳过"：trace_id 由固定种子算出，重复执行是幂等的
    # （INSERT OR REPLACE 会覆盖同样那几行），所以直接补齐即可。
    # 之前的跳过逻辑会让"先跑过真实请求"的环境永远补不上 7 天分布。
    rng = random.Random(20261112)  # 固定种子：每次生成同样数据，方便截图对照
    fingerprints = ["2c47c1aee78d", "8f31b0d42a19"]
    statuses_pool = ["completed"] * 18 + ["tool_timeout", "max_steps"]

    total = 0
    for day_offset in range(days):
        day = _now() - timedelta(days=day_offset)
        # 越接近今天请求越多：远端 4 条，今天 8 条
        per_day = 4 + (days - day_offset) // 2
        for i in range(per_day):
            status = rng.choice(statuses_pool)
            # 失败样本通常更慢（超时/多轮重试），这个规律要造出来
            base = rng.randint(1800, 5200) if status == "completed" else rng.randint(12000, 24000)
            duration = base + rng.randint(-400, 900)
            prompt_tokens = rng.randint(900, 2600)
            completion_tokens = rng.randint(120, 700)
            started = day.replace(hour=rng.randint(9, 21), minute=rng.randint(0, 59))
            tid = hashlib.sha256(f"{user_id}-{day_offset}-{i}".encode()).hexdigest()[:16]

            await db.execute(
                "INSERT OR REPLACE INTO trace_metrics "
                "(trace_id, user_id, session_id, model, config_fingerprint, prompt_version, "
                " tool_version, question, started_at, duration_ms, prompt_tokens, "
                " completion_tokens, total_tokens, cost_cny, steps, tool_calls, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tid,
                    user_id,
                    None,
                    settings.LLM_MODEL,
                    rng.choice(fingerprints),
                    "p3",
                    "t2",
                    rng.choice(QUESTIONS),
                    started.isoformat(timespec="seconds"),
                    duration,
                    prompt_tokens,
                    completion_tokens,
                    prompt_tokens + completion_tokens,
                    round((prompt_tokens * 1e-6 + completion_tokens * 2e-6) * 7.2, 6),
                    rng.randint(1, 4),
                    rng.randint(0, 3),
                    status,
                ),
            )
            total += 1

    await db.commit()
    return total


def claim_legacy_traces(user_id: str) -> int:
    """把 S9 之前生成的 trace 文件归属到演示账号。

    **为什么需要**：trace 是 JSON 文件而不是表，SQLite 的认领 SQL 覆盖不到它们。
    S9 之前写的文件里没有 user_id 字段，而查询接口会按 `user_id == 当前用户`
    过滤 —— 不处理的话，Trace 页面在升级后会是空的，看起来像"数据丢了"。
    """
    from agent_lab.app.services import trace as trace_service

    trace_dir = trace_service.TRACE_DIR
    if not trace_dir.is_dir():
        return 0

    claimed = 0
    for path in trace_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # 单个文件坏了不该让整个播种失败
            continue
        if not isinstance(data, dict):
            continue
        if data.get("user_id"):
            continue
        data["user_id"] = user_id
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        claimed += 1
    return claimed


async def reset_user_data(db: aiosqlite.Connection, user_id: str) -> None:
    """只清演示账号自己的数据，不碰别人的。

    顺序有讲究：先删子表再删父表，否则会留下孤儿行。
    """
    await db.execute("DELETE FROM session_messages WHERE session_id IN "
                     "(SELECT id FROM sessions WHERE user_id = ?)", (user_id,))
    for table in ("sessions", "task_plans", "todos", "trace_metrics"):
        await db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
    await db.commit()


async def main() -> int:
    parser = argparse.ArgumentParser(description="播种演示数据")
    parser.add_argument("--reset", action="store_true", help="先清空演示账号的数据")
    parser.add_argument("--no-metrics", action="store_true", help="不造指标样本")
    parser.add_argument("--no-docs", action="store_true", help="不上传示例文档")
    parser.add_argument("--warmup", type=int, default=0, help="额外发 N 条真实对话（花钱）")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001", help="warmup 用的服务地址")
    args = parser.parse_args()

    await init_db()

    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        user_id = await user_svc.ensure_demo_user(db)
        print(f"演示账号：{settings.DEMO_USERNAME} / {settings.DEMO_PASSWORD}  (id={user_id})")

        if args.reset:
            await reset_user_data(db, user_id)
            print("  · 已清空演示账号的历史数据")

        # 老数据认领：S9 之前的数据没有 user_id
        claimed = await user_svc.claim_legacy_rows(db, user_id)
        if claimed:
            print(f"  · 已认领 {claimed} 条历史数据（SQLite）")

        # trace 是文件，得单独认领
        claimed_files = claim_legacy_traces(user_id)
        if claimed_files:
            print(f"  · 已认领 {claimed_files} 个历史 trace 文件")

        claimed_docs = await claim_legacy_pg_documents(user_id)
        if claimed_docs:
            print(f"  · 已认领 {claimed_docs} 份历史文档")

        n = await seed_todos(db, user_id)
        if n:
            print(f"  · 已创建 {n} 条待办")

        if not args.no_docs:
            await seed_documents(user_id)

        if not args.no_metrics:
            n = await seed_metrics(db, user_id)
            if n:
                print(f"  · 已生成 {n} 条指标样本")
    finally:
        await db.close()

    if args.warmup > 0:
        await warmup(args.base_url, args.warmup)

    print("完成。启动方式见 README 的「快速开始」。")
    return 0


async def warmup(base_url: str, count: int) -> None:
    """发真实对话，产生真实的 trace / 指标 / 会话。

    用 SSE 流式接口，读到 done 就算完成。
    会花真钱（每条约 0.002 元），所以默认关闭。
    """
    import httpx

    print(f"开始预热 {count} 条真实对话（会产生 token 费用）…")
    async with httpx.AsyncClient(base_url=base_url, timeout=120) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": settings.DEMO_USERNAME, "password": settings.DEMO_PASSWORD},
        )
        if login.status_code != 200:
            print(f"  ! 登录失败：{login.status_code} {login.text[:120]}")
            return
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(count):
            question = QUESTIONS[i % len(QUESTIONS)]
            try:
                async with client.stream(
                    "POST",
                    "/api/v1/chat/stream/v2",
                    json={"content": question},
                    headers=headers,
                ) as resp:
                    if resp.status_code != 200:
                        print(f"  ! 第 {i + 1} 条失败：HTTP {resp.status_code}")
                        continue
                    async for _ in resp.aiter_lines():
                        pass
                print(f"  · {i + 1}/{count} {question}")
            except Exception as exc:  # noqa: BLE001
                print(f"  ! 第 {i + 1} 条异常：{exc}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))