"""第 29 章 · Compose 生产实践：profiles、secrets、override、extends/include、scale、资源限制。"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(29)

HERE = Path(__file__).parent
COMPOSE_FILE = str(HERE / "compose.yaml")
PROD_FILE = str(HERE / "compose.prod.yaml")
PROJECT = "ch29-prod"
SECRET = (HERE / "secrets" / "db_password.txt").read_text(encoding="utf-8").strip()


def compose(*args: str, **kwargs):
    return c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT, *args, **kwargs)


def wait_health(name: str, timeout: float = 60.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if c.container_status(name) == "running":
            return "running"
        time.sleep(0.5)
    return c.container_status(name)


valid = compose("config", "-q")
c.ok("config 校验通过", valid.returncode == 0, valid.stderr.strip()[:80])

services = compose("config", "--services").stdout.split()
c.ok("include 引入的服务被合并进来", "metrics" in services, str(sorted(services)))
c.ok("profile 服务默认不出现", "shell" not in services and "migrate" not in services,
     str(sorted(services)))
c.equal("config --profiles 列出可用 profile",
        sorted(compose("config", "--profiles").stdout.split()), ["tools"])

# 只有"默认发现"（不给 -f）时才会自动加载 compose.override.yaml
discovered = c.run("compose", "--project-directory", str(HERE), "-p", PROJECT, "config").stdout
c.contains("默认发现时 compose.override.yaml 自动合并", discovered, "OVERRIDE_MARK: from-override")

rendered = compose("config").stdout
c.ok("显式 -f compose.yaml 时 override 不自动合并",
     "OVERRIDE_MARK" not in rendered, "需手动 -f compose.override.yaml")
c.contains("env_file 后者覆盖前者", rendered, "APP_MODE: local")
c.contains("env_file 前者未丢失", rendered, "DB_HOST: db")
c.ok("extends 继承父服务且保留自身配置",
     "BASE_KEY: base-value" in rendered and "CHILD_KEY: child-value" in rendered, "")

prod = c.run("compose", "-f", COMPOSE_FILE, "-f", PROD_FILE, "-p", PROJECT, "config").stdout
c.contains("多 -f 显式叠加覆盖环境变量", prod, "DEPLOY_ENV: prod")
c.contains("多 -f 覆盖资源限制", prod, 'memory: "134217728"')

scaled_json = json.loads(c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT,
                               "config", "--format", "json").stdout)
c.ok("config --format json 可被程序解析",
     scaled_json["name"] == PROJECT and "api" in scaled_json["services"],
     str(sorted(scaled_json["services"])))

up = compose("up", "-d", timeout=300)
c.ok("up -d 启动默认服务集", up.returncode == 0, (up.stderr or up.stdout).strip()[-70:])

c.equal("include 的服务真的跑起来了", wait_health(f"{PROJECT}-metrics-1"), "running")
c.equal("profile 服务没有启动", c.container_exists(f"{PROJECT}-shell-1"), False)

secret_value = compose("exec", "-T", "api", "cat", "/run/secrets/db_password").stdout.strip()
c.equal("secret 以只读文件形式进容器", secret_value, SECRET)
env_json = c.out("inspect", "-f", "{{json .Config.Env}}", f"{PROJECT}-api-1")
c.ok("密钥没有出现在环境变量里", SECRET not in env_json, "")
mounts_json = c.out("inspect", "-f", "{{json .Mounts}}", f"{PROJECT}-api-1")
c.ok("secret 挂载为只读",
     "/run/secrets/db_password" in mounts_json and '"RW":false' in mounts_json,
     mounts_json[:80])

c.equal("deploy.resources.limits.memory 生效",
        c.out("inspect", "-f", "{{.HostConfig.Memory}}", f"{PROJECT}-api-1"), "67108864")
c.equal("deploy.resources.limits.cpus 生效",
        c.out("inspect", "-f", "{{.HostConfig.NanoCpus}}", f"{PROJECT}-api-1"), "500000000")

scale = compose("up", "-d", "--scale", "web=3", timeout=300)
c.ok("--scale web=3 生效", scale.returncode == 0, (scale.stderr or scale.stdout).strip()[-70:])
web_ids = compose("ps", "-q", "web").stdout.split()
c.equal("web 起了 3 个副本", len(web_ids), 3)
ips = {c.out("inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", i)
       for i in web_ids}
c.equal("每个副本独立 IP", len(ips), 3)

tools = c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT, "--profile", "tools",
              "up", "-d", "migrate", timeout=300)
c.ok("--profile tools 才拉起一次性任务", tools.returncode == 0,
     (tools.stderr or tools.stdout).strip()[-70:])
c.contains("一次性任务按预期执行完",
           compose("logs", "--no-color", "migrate").stdout, "migrated")

c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT, "--profile", "tools",
      "down", "-v", "--remove-orphans", timeout=300)
c.equal("带上 profile 才能把一次性任务一起清掉", len(compose("ps", "-aq").stdout.split()), 0)

raise SystemExit(c.finish())
