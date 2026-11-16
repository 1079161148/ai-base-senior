"""第 18 章示例：with 与 contextlib.contextmanager。"""

import contextlib

@contextlib.contextmanager
def tool_session(name):
    """进入/退出时打印，清理逻辑放 finally [R3]。"""
    print("进入:", name)
    try:
        yield {"tool": name}
    finally:
        print("退出:", name)

with tool_session("search") as session:
    print("会话:", session)
