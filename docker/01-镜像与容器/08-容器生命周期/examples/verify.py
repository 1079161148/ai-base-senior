"""第 08 章 · 容器生命周期：create/start/stop/restart/kill/rm/pause。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(8)

life = c.name("life")
c.run("create", "--name", life, "alpine:3.20", "sleep", "300")
c.equal("create 后状态为 created", c.container_status(life), "created")
c.ok("create 不启动容器", not c.container_running(life))

c.run("start", life)
c.ok("start 后进入运行", c.container_running(life))

c.run("pause", life)
c.equal("pause 后状态为 paused", c.container_status(life), "paused")
c.run("unpause", life)
c.ok("unpause 后恢复运行", c.container_running(life))

c.run("restart", life, timeout=60)
c.ok("restart 后仍在运行", c.container_running(life))

c.run("kill", life)
c.equal("kill 后状态为 exited", c.container_status(life), "exited")
c.equal("kill 退出码为 137", c.out("inspect", "-f", "{{.State.ExitCode}}", life), "137")

c.run("rm", life)
c.ok("rm 删除已停止容器", not c.container_exists(life))

force = c.name("force")
c.run("run", "-d", "--name", force, "alpine:3.20", "sleep", "300")
c.run("rm", "-f", force)
c.ok("rm -f 强制删除运行中容器", not c.container_exists(force))

graceful = c.name("graceful")
c.run("run", "-d", "--name", graceful, "alpine:3.20", "sh", "-c",
      "trap 'exit 0' TERM; while true; do sleep 1; done")
c.run("stop", graceful, timeout=60)
c.equal("stop 发送 SIGTERM 得到正常退出码 0",
        c.out("inspect", "-f", "{{.State.ExitCode}}", graceful), "0")

stubborn = c.name("stubborn")
c.run("run", "-d", "--name", stubborn, "alpine:3.20", "sh", "-c",
      "trap '' TERM; while true; do sleep 1; done")
c.run("stop", "-t", "2", stubborn, timeout=60)
c.equal("拒绝 TERM 时超时后被 SIGKILL（137）",
        c.out("inspect", "-f", "{{.State.ExitCode}}", stubborn), "137")

keep = c.name("keep")
c.run("run", "-d", "--name", keep, "alpine:3.20", "sh", "-c", "echo data > /tmp/keep; sleep 300")
c.run("stop", keep, timeout=60)
c.ok("停止后容器仍存在", c.container_exists(keep))
c.ok("停止后状态为 exited", c.container_status(keep) == "exited")
c.run("start", keep)
c.equal("停止再启动后容器内数据仍在", c.out("exec", keep, "cat", "/tmp/keep").strip(), "data")

raise SystemExit(c.finish())
