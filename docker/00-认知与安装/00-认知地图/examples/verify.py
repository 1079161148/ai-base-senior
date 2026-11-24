"""第 00 章 · 认知地图：确认 Docker 环境与三大核心概念。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(0)

client = c.run("version", "--format", "{{.Client.Version}}")
c.ok("docker CLI 可用", client.returncode == 0, client.stdout.strip() or client.stderr.strip()[:80])

server = c.run("version", "--format", "{{.Server.Version}}")
c.ok("dockerd 服务端可用", server.returncode == 0, server.stdout.strip() or server.stderr.strip()[:80])

info = c.out("info")
c.ok("info 显示 Server Version", "Server Version" in info)
c.ok("info 显示 Storage Driver", "Storage Driver" in info)
c.ok("info 显示 Docker Root Dir", "Docker Root Dir" in info)

hello = c.run("run", "--rm", "hello-world", timeout=300)
c.ok("hello-world 容器可运行", hello.returncode == 0,
     next((line for line in hello.stdout.splitlines() if "Hello" in line), ""))

lifecycle = c.name("lifecycle")
c.run("run", "--name", lifecycle, "hello-world", timeout=300)
c.equal("容器随主进程结束", c.container_status(lifecycle), "exited")

c.ok("镜像概念可验证", c.image_exists("hello-world:latest"))
c.ok("容器概念可验证", c.container_exists(lifecycle))

c.run("rm", "-f", lifecycle)
c.ok("容器可删除", not c.container_exists(lifecycle))

raise SystemExit(c.finish())
