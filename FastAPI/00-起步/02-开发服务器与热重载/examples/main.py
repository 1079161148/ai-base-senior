"""第 02 章 · 开发服务器与热重载。

本章示例的重点不是接口本身，而是**让你看见进程**：
  - /whoami  返回 pid / ppid / 启动时间，用来观察 reload 与 workers 的差异
  - /config  返回运行时关键信息，用来确认 host/port/环境变量是否生效

启动方式（在本目录执行）：
  python main.py                                  # 代码启动，无 reload
  uvicorn main:app --reload                       # 开发
  uvicorn main:app --workers 2                    # 多进程（生产形态）
  uvicorn main:app --reload --workers 2           # 实测：只打 WARNING，workers 被忽略
"""

from __future__ import annotations

import os
import sys
import time

from fastapi import FastAPI

# 【作用】记录进程启动时刻与 PID，用来判断「服务是否真的重启过」
# 【注意】这两个值是**模块级常量**，在进程启动时求值一次。
#        如果 reload 真的重启了进程，重新 import 模块时它们会重新求值（PID 变、uptime 归零）；
#        如果只是打印了 Reloading 但进程没换，那么 PID 和 uptime 都不会变。
#        这正是本章用来验证 reload 是否生效的探针。
STARTED_AT = time.time()
PID = os.getpid()
PPID = os.getppid()

app = FastAPI(
    title="第 02 章 · 开发服务器",
    description="用于观察 uvicorn 的进程与重载行为",
    version="0.1.0",
)


@app.get("/whoami", tags=["观测"])
def whoami() -> dict[str, object]:
    """返回当前处理请求的进程身份。

    【作用】多进程（`--workers N`）下反复请求这里，会看到 N 个不同的 pid，
           证明请求被分发到了不同进程——它们之间**不共享内存**。
    【注意】`ppid` 在 workers 模式下是父进程（管理进程）；在 reload 模式下
           是 reloader 进程。所以 ppid 不能用来判断「是不是主进程」。
    """
    return {
        "pid": PID,
        "ppid": PPID,
        # 【注意】uptime 只增不减；若某次请求发现它变小了，说明进程重启过
        "uptime_seconds": round(time.time() - STARTED_AT, 3),
        "python": sys.version.split()[0],
    }


@app.get("/config", tags=["观测"])
def config() -> dict[str, object]:
    """暴露运行时配置，用于确认环境变量与启动参数。

    【注意】真实项目不要暴露这种接口——它泄露环境信息。
           这里仅作为教学观测点，生产应通过日志或配置中心查看。
    """
    return {
        "cwd": os.getcwd(),
        "argv": sys.argv[:6],
        # 【作用】环境变量可在启动前设置：$env:APP_ENV="dev"（PowerShell）
        "app_env": os.getenv("APP_ENV", "dev"),
        "reload_flag_present": "--reload" in sys.argv,
        "workers_flag_present": "--workers" in sys.argv,
    }


if __name__ == "__main__":
    # 【作用】`python main.py` 直接启动，方便快速验证
    # 【注意】传 app 对象时无法开启 reload（reload 需要 import 字符串来重新加载模块）
    # 【注意】port=0 会让操作系统分配一个空闲端口，适合本地临时验证
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
