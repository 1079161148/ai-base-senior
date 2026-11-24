"""第 10 章 · 运行控制：重启策略、init、用户、资源限制。"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(10)

flap = c.name("flap")
c.run("run", "-d", "--name", flap, "--restart", "on-failure:2", "alpine:3.20", "sh", "-c", "exit 1")
time.sleep(6)
policy = c.out("inspect", "-f",
               "{{.HostConfig.RestartPolicy.Name}}:{{.HostConfig.RestartPolicy.MaximumRetryCount}}", flap)
c.equal("重启策略写入配置", policy, "on-failure:2")
restart_count = int(c.out("inspect", "-f", "{{.RestartCount}}", flap))
c.ok("失败后确实自动重启过", restart_count >= 1, f"RestartCount={restart_count}")

host = c.name("host")
c.run("run", "-d", "--name", host, "--hostname", "mybox", "alpine:3.20", "sleep", "60")
c.equal("--hostname 生效", c.out("exec", host, "hostname"), "mybox")

workdir = c.run("run", "--rm", "--workdir", "/opt", "alpine:3.20", "pwd")
c.equal("--workdir 生效", workdir.stdout.strip(), "/opt")

uid = c.out("run", "--rm", "--user", "1000:1000", "alpine:3.20", "id", "-u")
c.equal("--user 生效", uid, "1000")

limits = c.name("limits")
c.run("run", "-d", "--name", limits, "--memory", "64m", "--cpus", "0.5", "alpine:3.20", "sleep", "60")
c.equal("内存限制写入 cgroup 配置",
        c.out("inspect", "-f", "{{.HostConfig.Memory}}", limits), "67108864")
c.equal("CPU 限制写入配置",
        c.out("inspect", "-f", "{{.HostConfig.NanoCpus}}", limits), "500000000")
c.ok("默认未启用 init",
     c.out("inspect", "-f", "{{.HostConfig.Init}}", limits) in ("false", "<nil>"),
     c.out("inspect", "-f", "{{.HostConfig.Init}}", limits))

with_init = c.name("init")
c.run("run", "-d", "--name", with_init, "--init", "alpine:3.20", "sleep", "60")
c.equal("--init 启用 tini", c.out("inspect", "-f", "{{.HostConfig.Init}}", with_init), "true")

overridden = c.run("run", "--rm", "--entrypoint", "echo", "alpine:3.20", "overridden")
c.equal("--entrypoint 覆盖镜像入口", overridden.stdout.strip(), "overridden")

c.ok("默认重启策略为 no",
     c.out("inspect", "-f", "{{.HostConfig.RestartPolicy.Name}}", limits) in ("no", ""))

raise SystemExit(c.finish())
