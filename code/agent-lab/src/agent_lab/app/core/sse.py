"""SSE 消息编码。

**为什么单独成模块**：`demo` 和 `chat` 两个接口都要发 SSE，
而"`data:` 前缀 + 两个换行"这套规则差一个字符浏览器就不触发事件。
这种东西复制粘贴一次就会犯第二次错，所以只留一份实现。

（解码那半在浏览器侧：`agent-lab-web/src/api/stream.ts`）
"""

import json


def encode(payload: dict[str, object]) -> str:
    """把 dict 编成一条 SSE 消息。

    ensure_ascii=False：否则中文会变成 `\\u4f60\\u597d`。
    浏览器能解，但 curl / DevTools 里完全没法读，
    排查"为什么输出是乱码"时会被浪费掉半小时。
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
