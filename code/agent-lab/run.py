"""本地开发启动入口（IDE 里可以直接点运行）。

为什么需要这个文件：

    src/agent_lab/app/main.py 内部使用了相对导入（from .core.config import ...），
    所以直接运行它会报：
        ImportError: attempted relative import with no known parent package

    本文件位于「包外」，把 "agent_lab.app.main:app" 这个字符串交给 uvicorn，
    由 uvicorn 自己按包路径导入 —— 既能在 IDE 里一键启动，也不会触发相对导入问题。

用法：

    uv run python run.py

    或在 IDE 里直接右键运行本文件。

注意：
    uvicorn 必须收到「字符串」而不是 app 对象，reload 才能生效。
    传对象的话 reload 会失效并告警。
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "agent_lab.app.main:app",
        host="127.0.0.1",
        port=8001,  # 8000 被其他程序长期占用，开发统一用 8001
        reload=True,
    )
