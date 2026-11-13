"""检查 LLM 配置是否可用。

用法：
    cd E:\\ai-agent-study\\code\\agent-lab
    uv run python scripts/check_llm.py

只发一次最短的请求（max_tokens=16），用来确认
「地址 + Key + 模型名」三者是否对得上。

比在前端点一下按钮、再对着红色错误条猜要快得多 ——
这里能直接看到上游返回的原始报错。

**注意**：它读的是 .env 的当前内容，不需要启动后端。
改完配置直接跑，能看到结果再重启服务。
"""

import asyncio
import sys

import httpx

from agent_lab.app.core.config import settings


def mask(key: str) -> str:
    """只显示末尾 4 位。终端日志经常被截图分享，Key 不该出现在里面。"""
    if not key:
        return "（未填）"
    if len(key) <= 8:
        return "***"
    return f"…{key[-4:]}（共 {len(key)} 字符）"


def diagnose(status: int, body: str) -> None:
    print("\n可能的原因：")

    if status in (401, 403):
        print("  1. Key 复制错了（漏字符、混进空格或换行）")
        print("  2. Key 与 LLM_BASE_URL 不是同一家平台")
        print("     ← 中转站的 Key 配官方地址，必然 401，这是最常见的一种")
        print("  3. 额度用尽 / 账号被限制")
    elif status == 404:
        print("  请求路径不对：多数平台要求 base_url 末尾带 /v1")
        print(f"  当前实际打的是 {settings.LLM_BASE_URL.rstrip('/')}/chat/completions")
        print("  若少了 /v1，把 LLM_BASE_URL 改成 https://你的域名/v1")
    elif status == 400:
        print("  参数或模型名不对：确认 LLM_MODEL 是该平台支持的名称")
        print("  有些中转站把 deepseek-chat 叫 deepseek-v3，以平台文档为准")
    elif status == 402:
        # 402 和 401 是两回事：401 是「不认这张卡」，402 是「卡没问题但没钱」
        print("  账号欠费 / 没有可用套餐 —— 去平台控制台充值或订购后重试")
        print("  注意：能返回 402 说明 Key 已通过认证，配置是通的，只差额度")
    elif status == 429:
        print("  限流或额度不足，等一会儿再试")
    elif status >= 500:
        print("  上游服务故障，不是你的配置问题")
    else:
        print(f"  看原始响应：{body[:200]}")


async def main() -> int:
    print("=" * 60)
    print("当前配置（来自 .env）")
    print("=" * 60)
    print(f"  LLM_BASE_URL : {settings.LLM_BASE_URL}")
    print(f"  LLM_MODEL    : {settings.LLM_MODEL}")
    print(f"  LLM_API_KEY  : {mask(settings.LLM_API_KEY)}")

    if not settings.llm_configured:
        print("\n[×] 配置不完整：LLM_API_KEY 为空，先在 .env 里填上。")
        return 1

    url = f"{settings.LLM_BASE_URL.rstrip('/')}/chat/completions"
    print("\n" + "=" * 60)
    print("实际请求")
    print("=" * 60)
    print(f"  POST {url}")

    payload: dict[str, object] = {
        "model": settings.LLM_MODEL,
        "messages": [{"role": "user", "content": "只回复两个字：收到"}],
        "max_tokens": 16,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        print(f"\n[×] 连不上：{type(exc).__name__}: {exc}")
        print("\n可能的原因：")
        print("  1. 网络 / 代理问题")
        print("  2. 域名拼错")
        print("  3. 该地址需要 HTTPS 但你写了 HTTP（或反过来）")
        return 1

    print(f"\nHTTP {resp.status_code}")

    if resp.status_code == 200:
        data = resp.json()
        content = ""
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            pass

        usage = data.get("usage") or {}
        print(f"  ✓ 模型回复：{content!r}")
        print(f"  ✓ token 用量：{usage}")
        print("\n[√] 配置可用，重启后端即可在页面上对话。")
        return 0

    print(f"\n原始响应：\n{resp.text[:600]}")
    diagnose(resp.status_code, resp.text)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
