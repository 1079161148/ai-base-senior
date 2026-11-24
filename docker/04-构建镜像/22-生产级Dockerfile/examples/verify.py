"""第 22 章 · 生产级 Dockerfile：非 root、健康检查、信号、只读根。"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(22)
context = Path(__file__).parent
tag = f"{c.name('prod')}:1.0.0"


def wait_healthy(name: str, timeout: float = 90.0) -> str:
    deadline = time.time() + timeout
    last = "unknown"
    while time.time() < deadline:
        last = c.out("inspect", "-f",
                     "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", name)
        if last == "healthy":
            return last
        if last == "unhealthy":
            return last
        time.sleep(2)
    return last


build = c.run("build", "-t", tag, "-f", str(context / "Dockerfile"), str(context), timeout=300)
c.ok("生产级镜像构建成功", build.returncode == 0,
     (build.stdout + build.stderr).strip().splitlines()[-1][:60] if (build.stdout + build.stderr).strip() else "")

config = c.json("image", "inspect", tag)[0]["Config"]
c.equal("声明运行用户为非 root", config["User"], "appuser")
c.ok("声明了 HEALTHCHECK", config.get("Healthcheck") is not None,
     str(config.get("Healthcheck", {}).get("Test"))[:50])
c.equal("显式设置停止信号", config.get("StopSignal"), "SIGTERM")
c.ok("OCI 标签齐全", (config.get("Labels") or {}).get("org.opencontainers.image.version") == "1.0.0",
     str(list((config.get("Labels") or {}).keys()))[:70])

dockerfile_text = (context / "Dockerfile").read_text(encoding="utf-8")
c.ok("基础镜像未使用 latest", ":latest" not in dockerfile_text and "FROM python:3.12-slim" in dockerfile_text)

web = c.name("web")
c.run("run", "-d", "--name", web, "-p", "18120:8000", tag, timeout=120)
c.ok("服务可访问", "ok" in c.wait_http(18120), c.http_get(18120).strip()[:30])

uid = c.out("exec", web, "id", "-u")
c.equal("容器内实际以非 root 运行", uid, "10001")

c.equal("健康检查判定为 healthy", wait_healthy(web), "healthy")

ro = c.name("ro")
c.run("run", "-d", "--name", ro, "--read-only", "--tmpfs", "/tmp", "-p", "18121:8000", tag, timeout=120)
c.ok("只读根文件系统下服务仍可运行", "ok" in c.wait_http(18121), c.http_get(18121).strip()[:30])
write_attempt = c.run("exec", ro, "sh", "-c", "echo x > /app/should-fail")
c.ok("只读根文件系统拒绝写入", write_attempt.returncode != 0,
     (write_attempt.stdout + write_attempt.stderr).strip()[:60])

stop = c.run("stop", web, timeout=60)
c.ok("收到 SIGTERM 能优雅退出", "graceful shutdown" in c.container_logs(web),
     c.container_logs(web).strip().replace("\n", " ")[-60:])

raise SystemExit(c.finish())
