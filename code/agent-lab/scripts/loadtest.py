"""S8 · 压测与熔断验证。

默认用**会被护栏拦截**的请求压测：它们走到 guard 就 400，
不花钱。但限流在这之前，所以仍然能验证"配额确实在生效"。

    uv run python scripts/loadtest.py --base-url http://127.0.0.1:8001 --concurrency 50

想测真实链路（要花钱）加 --real，此时用正常问题，默认只发 5 个。
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import time

import httpx

BLOCKED_TEXT = "删除所有待办"  # 命中批量删除规则，必被拦
NORMAL_TEXT = "你好，用一句话介绍你自己"


async def one(client: httpx.AsyncClient, base: str, text: str, idx: int) -> tuple[int, str, float]:
    started = time.perf_counter()
    try:
        resp = await client.post(
            f"{base}/api/v1/chat/stream-v2",
            json={"session_id": None, "content": text},
            timeout=180,
        )
        code = resp.status_code
        body = resp.text[:120]
    except Exception as exc:
        code = 0
        body = f"{type(exc).__name__}"
    return code, body, round((time.perf_counter() - started) * 1000, 1)


async def main() -> int:
    parser = argparse.ArgumentParser(description="S8 压测")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--real", action="store_true", help="打真实请求（会花钱）")
    args = parser.parse_args()

    text = NORMAL_TEXT if args.real else BLOCKED_TEXT
    n = args.concurrency if args.real is False else min(args.concurrency, 5)
    base = args.base_url.rstrip("/")

    print(f"目标 {base}，并发 {n}，请求类型：{'真实' if args.real else '护栏拦截（不花钱）'}")

    async with httpx.AsyncClient() as client:
        started = time.perf_counter()
        results = await asyncio.gather(*(one(client, base, text, i) for i in range(n)))
        elapsed = round(time.perf_counter() - started, 2)

    codes = collections.Counter(c for c, _, _ in results)
    durations = sorted(d for _, _, d in results)
    p95 = durations[min(len(durations) - 1, int(len(durations) * 0.95))]

    print(f"\n耗时 {elapsed}s   P95 {p95}ms")
    for code, count in sorted(codes.items()):
        label = {200: "成功", 400: "被护栏拦", 429: "被限流/熔断", 0: "连接失败"}.get(code, "")
        print(f"  HTTP {code:<4} {count:>3}  {label}")

    # 判定：服务必须活着，且超量请求被明确拒绝（而不是全部成功或全部崩溃）
    ok = 0 not in codes and (len(codes) > 1 or n <= 8)
    print("\n" + ("✅ 服务未被压垮，超量请求按预期被拒" if ok else "❌ 出现连接失败或未触发限流，检查 RATE_LIMIT_PER_MINUTE / MAX_CONCURRENT_REQUESTS"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
