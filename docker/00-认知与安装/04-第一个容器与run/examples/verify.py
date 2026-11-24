"""第 04 章 · 第一个容器与 docker run 核心选项。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(4)

foreground = c.run("run", "--rm", "alpine:3.20", "echo", "hi")
c.equal("前台运行并输出", foreground.stdout.strip(), "hi")

env_run = c.run("run", "--rm", "-e", "NAME=docker", "alpine:3.20", "sh", "-c", "echo $NAME")
c.equal("-e 传递环境变量", env_run.stdout.strip(), "docker")

override = c.run("run", "--rm", "alpine:3.20", "cat", "/etc/alpine-release")
c.ok("镜像名后命令覆盖默认 CMD", override.returncode == 0 and override.stdout.strip().startswith("3."),
     override.stdout.strip())

autorm = c.name("autorm")
c.run("run", "--rm", "--name", autorm, "alpine:3.20", "true")
c.ok("--rm 退出后自动删除", not c.container_exists(autorm))

exit_code = c.run("run", "--rm", "alpine:3.20", "sh", "-c", "exit 3")
c.equal("退出码传递到宿主", exit_code.returncode, 3)

web = c.name("web")
c.run("run", "-d", "--name", web, "-p", "127.0.0.1:18080:80", "nginx:1.27-alpine", timeout=300)
body = c.wait_http(18080)
c.ok("后台运行 + 端口映射可访问", "Welcome to nginx" in body, body.strip()[:40])

ports = c.out("port", web)
c.ok("端口只绑定回环地址", "127.0.0.1:18080" in ports and "0.0.0.0" not in ports, ports)

c.run("stop", web)
c.ok("停止后不再运行", not c.container_running(web))

raise SystemExit(c.finish())
