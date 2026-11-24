"""第 02 章 · 三平台安装 Docker：环境就绪检测。"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(2)

c.ok("docker CLI 在 PATH 中", shutil.which("docker") is not None, str(shutil.which("docker")))

client = c.out("version", "--format", "{{.Client.Version}}")
server = c.out("version", "--format", "{{.Server.Version}}")
c.ok("客户端版本可读", bool(client), client)
c.ok("服务端可达", bool(server), server)
c.ok("客户端与服务端大版本一致", client.split(".")[0] == server.split(".")[0], f"{client} vs {server}")

context = c.out("context", "show")
c.ok("当前 context 可用", bool(context), context)

compose = c.run("compose", "version")
c.ok("compose 插件已安装", compose.returncode == 0, compose.stdout.strip())

buildx = c.run("buildx", "version")
first_line = (buildx.stdout or buildx.stderr).strip().splitlines()
c.ok("buildx 插件已安装", buildx.returncode == 0, first_line[0] if first_line else "")

os_name = c.out("info", "--format", "{{.OperatingSystem}}")
c.ok("能识别运行形态", bool(os_name), os_name)

run = c.run("run", "--rm", "alpine:3.20", "echo", "ok")
c.equal("daemon 能真实运行容器", run.stdout.strip(), "ok")

pull = c.run("pull", "alpine:3.20")
c.ok("镜像仓库可达", pull.returncode == 0, (pull.stderr or pull.stdout).strip().splitlines()[-1][:70])

raise SystemExit(c.finish())
