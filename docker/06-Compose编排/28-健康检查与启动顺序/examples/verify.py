"""第 28 章 · 健康检查与启动顺序：starting/healthy/unhealthy 三态、depends_on 条件、restart 策略。"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(28)

HERE = Path(__file__).parent
COMPOSE_FILE = str(HERE / "compose.yaml")
WAIT_FILE = str(HERE / "compose.wait.yaml")
PROJECT = "ch28-hc"
WAIT_PROJECT = "ch28-wait"


def compose(*args: str, **kwargs):
    return c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT, *args, **kwargs)


def health(name: str) -> str:
    proc = c.run("inspect", "-f", "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}", name)
    return proc.stdout.strip() if proc.returncode == 0 else "missing"


def wait_health(name: str, expect: str, timeout: float = 90.0) -> str:
    status = "missing"
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = health(name)
        if status == expect:
            return status
        time.sleep(0.5)
    return status


def logs_of(service: str) -> str:
    return compose("logs", "--no-color", service).stdout


up = compose("up", "-d", timeout=600)
c.ok("up -d 成功（含 service_healthy 依赖），按依赖顺序启动", up.returncode == 0,
     (up.stderr or up.stdout).strip()[-80:])

c.equal("没有 healthcheck 的服务 Health 为空（steady）",
        health(f"{PROJECT}-steady-1") if c.container_running(f"{PROJECT}-steady-1") else "none",
        "none")
c.equal("start_period 内状态是 starting", health(f"{PROJECT}-probe-1"), "starting")

c.run("exec", f"{PROJECT}-probe-1", "touch", "/tmp/ready")
c.equal("标记文件出现后转为 healthy", wait_health(f"{PROJECT}-probe-1", "healthy"), "healthy")

c.equal("持续失败的服务最终 unhealthy", wait_health(f"{PROJECT}-sick-1", "unhealthy", 60), "unhealthy")
streak = c.out("inspect", "-f", "{{.State.Health.FailingStreak}}", f"{PROJECT}-sick-1")
c.ok("失败计数 FailingStreak 达阈值", streak.isdigit() and int(streak) >= 2, f"FailingStreak={streak}")

c.equal("镜像没定义健康检查，可在 compose 里补（web）",
        wait_health(f"{PROJECT}-web-1", "healthy"), "healthy")

started_logs = logs_of("consumer_started")
c.contains("service_started：消费者先启动，此时依赖还没监听", started_logs, "NOT_READY")
c.contains("service_healthy：等到依赖真正可连接才启动", logs_of("consumer_healthy"), "CONNECTED")

c.equal("slowdb 最终 healthy", wait_health(f"{PROJECT}-slowdb-1", "healthy"), "healthy")

deadline = time.time() + 60
restarts = "0"
while time.time() < deadline:
    proc = c.run("inspect", "-f", "{{.RestartCount}}", f"{PROJECT}-crasher-1")
    restarts = proc.stdout.strip()
    status = c.container_status(f"{PROJECT}-crasher-1")
    if restarts == "3" and status == "exited":
        break
    time.sleep(0.5)
c.equal("on-failure:3 重启 3 次后放弃", restarts, "3")
c.equal("放弃后状态为 exited", c.container_status(f"{PROJECT}-crasher-1"), "exited")
c.equal("退出码保留为 1",
        c.out("inspect", "-f", "{{.State.ExitCode}}", f"{PROJECT}-crasher-1"), "1")
c.equal("restart: no 的容器不重启", c.out("inspect", "-f", "{{.RestartCount}}", f"{PROJECT}-steady-1"), "0")

start = time.time()
wait_up = c.run("compose", "-f", WAIT_FILE, "-p", WAIT_PROJECT, "up", "-d", "--wait", timeout=300)
elapsed = time.time() - start
c.ok("up -d --wait 等全部 healthy 才返回", wait_up.returncode == 0,
     (wait_up.stderr or wait_up.stdout).strip()[-60:])
c.equal("--wait 返回时确实已 healthy", health(f"{WAIT_PROJECT}-ready-1"), "healthy")
c.ok("--wait 真的阻塞到就绪（服务需 4 秒才建标记文件）", elapsed > 3.0, f"耗时 {elapsed:.1f}s")

compose("down", timeout=300)
c.run("compose", "-f", WAIT_FILE, "-p", WAIT_PROJECT, "down", "-v", timeout=300)

raise SystemExit(c.finish())
