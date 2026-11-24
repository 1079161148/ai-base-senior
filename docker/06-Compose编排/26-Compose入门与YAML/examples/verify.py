"""第 26 章 · Compose 入门：YAML 结构、变量插值、项目命名、up/ps/logs/exec/down。"""

import sys
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(26)

HERE = Path(__file__).parent
COMPOSE_FILE = str(HERE / "compose.yaml")
BROKEN_FILE = str(HERE / "compose.broken.yaml")
ENV_FILE = str(HERE / ".env")
PROJECT = "ch26-compose"


def compose(*args: str, **kwargs):
    """统一带上 -f / -p / --env-file，等价于在项目目录里直接敲 docker compose。"""
    return c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT,
                 "--env-file", ENV_FILE, *args, **kwargs)


version = c.out("compose", "version", "--short")
c.ok("Compose 为 v2 及以上（不再是独立的 docker-compose）",
     version.split(".")[0].isdigit() and int(version.split(".")[0]) >= 2, version)

valid = compose("config", "-q")
c.ok("config 校验通过", valid.returncode == 0, valid.stderr.strip()[:60])

c.equal("config --services 列出两个服务",
        sorted(compose("config", "--services").stdout.split()), ["web", "worker"])

rendered = compose("config").stdout
c.ok("命令行 -p 覆盖文件里的 name", "name: ch26-compose" in rendered and "ch26-file" not in rendered,
     [line for line in rendered.splitlines() if line.startswith("name:")])
c.contains("变量插值读取 .env 的值", rendered, "GREETING: hello-bob")
c.contains("变量缺失时使用 :- 默认值", rendered, "FALLBACK: guest")
c.contains("卷被自动加上项目名前缀", rendered, "name: ch26-compose_data")

broken = c.run("compose", "-f", BROKEN_FILE, "--env-file", ENV_FILE, "config", "-q")
c.ok("非法 YAML 在启动前就被拦下", broken.returncode != 0, broken.stderr.strip().splitlines()[-1][:80])

up = compose("up", "-d", timeout=300)
c.ok("up -d 启动整个项目", up.returncode == 0, (up.stderr or up.stdout).strip()[-80:])

c.ok("容器名 = 项目名-服务名-序号", c.container_running(f"{PROJECT}-web-1"),
     f"{PROJECT}-web-1")
c.equal("项目标签 com.docker.compose.project",
        c.out("inspect", "-f", '{{index .Config.Labels "com.docker.compose.project"}}',
              f"{PROJECT}-web-1"), PROJECT)
c.equal("服务标签 com.docker.compose.service",
        c.out("inspect", "-f", '{{index .Config.Labels "com.docker.compose.service"}}',
              f"{PROJECT}-web-1"), "web")

c.equal("ps --services 只显示运行中的服务",
        sorted(compose("ps", "--services").stdout.split()), ["web", "worker"])

page = c.wait_http(18080)
c.contains("端口映射生效，能访问 nginx", page, "Welcome to nginx")

mode = compose("exec", "-T", "worker", "printenv", "MODE")
c.equal("exec 在服务内执行命令", mode.stdout.strip(), "demo")

try:
    # 故意请求不存在的路径：只为在 access log 里留下记录，404 本身是预期结果
    c.http_get(18080, "/probe-from-verify-26")
except urllib.error.HTTPError:
    pass
logs = compose("logs", "--no-color", "web").stdout
c.contains("logs 汇总服务日志", logs, "/probe-from-verify-26")

c.ok("显式命名的网络已创建", c.network_exists("ch26-net"), "ch26-net")
c.equal("两个容器都接入同一网络",
        c.out("network", "inspect", "-f", "{{len .Containers}}", "ch26-net"), "2")
c.ok("命名卷已创建", c.volume_exists(f"{PROJECT}_data"), f"{PROJECT}_data")

down = compose("down", "-v", timeout=300)
c.ok("down 成功", down.returncode == 0, (down.stderr or down.stdout).strip()[-60:])
c.equal("容器被删除", c.container_exists(f"{PROJECT}-web-1"), False)
c.equal("网络被删除", c.network_exists("ch26-net"), False)
c.equal("卷被删除（-v）", c.volume_exists(f"{PROJECT}_data"), False)

raise SystemExit(c.finish())
