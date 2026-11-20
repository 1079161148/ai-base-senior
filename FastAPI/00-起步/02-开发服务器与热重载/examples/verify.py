"""第 02 章 · 自动验收（不需要启动 uvicorn）。

验证内容：
  1. 应用能被 TestClient 加载（说明 main:app 这个导入路径成立）
  2. /whoami 结构正确，且同一次进程内 pid 稳定、uptime 单调递增
  3. /config 可访问，且能读到 APP_ENV 默认值

注意：本章真正的主角是**进程行为**（reload / workers），
那部分必须起真实服务才能观察，见 verify_proc.py。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_whoami_shape() -> str:
    """pid/ppid 必须是整数，uptime 必须是非负数。"""
    data = client.get("/whoami").json()
    assert isinstance(data["pid"], int), data
    assert isinstance(data["ppid"], int), data
    assert data["uptime_seconds"] >= 0, data
    # 【为什么】TestClient 在**当前进程**内调用 app，所以 pid 必须等于本进程
    assert data["pid"] == os.getpid(), (data["pid"], os.getpid())
    return f"pid={data['pid']} uptime={data['uptime_seconds']}"


def check_pid_stable() -> str:
    """同一进程内多次请求，pid 必须完全一致。"""
    pids = {client.get("/whoami").json()["pid"] for _ in range(5)}
    assert pids == {os.getpid()}, pids
    return f"5 次请求 pid 集合={pids}"


def check_uptime_monotonic() -> str:
    """uptime 只增不减，可作为「进程是否重启」的探针。"""
    a = client.get("/whoami").json()["uptime_seconds"]
    time.sleep(0.05)
    b = client.get("/whoami").json()["uptime_seconds"]
    assert b >= a, (a, b)
    return f"{a} -> {b}"


def check_config() -> str:
    """/config 能读环境变量，默认值必须是 dev。"""
    data = client.get("/config").json()
    assert data["app_env"] == os.getenv("APP_ENV", "dev"), data
    assert isinstance(data["argv"], list), data
    return f"app_env={data['app_env']} cwd={Path(data['cwd']).name}"


def check_openapi() -> str:
    """两个接口都要出现在文档里，且都带 tags。"""
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/whoami", "/config"}, sorted(schema["paths"])
    for path, item in schema["paths"].items():
        for op in item.values():
            assert op.get("tags") == ["观测"], (path, op.get("tags"))
    return f"paths={sorted(schema['paths'])}"


CHECKS = [
    ("main:app 可导入", lambda: "ok"),
    ("/whoami 结构正确", check_whoami_shape),
    ("同进程 pid 稳定", check_pid_stable),
    ("uptime 单调递增", check_uptime_monotonic),
    ("/config 可读环境", check_config),
    ("OpenAPI 含两接口", check_openapi),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
