"""第 27 章 · Compose 编排实战：Web + PostgreSQL + Redis 的真实联通与持久化。"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(27)

HERE = Path(__file__).parent
COMPOSE_FILE = str(HERE / "compose.yaml")
ENV_FILE = str(HERE / ".env")
EMPTY_ENV = str(HERE / "env.empty")
PROJECT = "ch27-app"
NET = "ch27-net"


def compose(*args: str, **kwargs):
    return c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT,
                 "--env-file", ENV_FILE, *args, **kwargs)


def wait_health(name: str, timeout: float = 120.0) -> str:
    status = "missing"
    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = c.run("inspect", "-f", "{{if .State.Health}}{{.State.Health.Status}}{{end}}", name)
        status = proc.stdout.strip() if proc.returncode == 0 else "missing"
        if status == "healthy":
            return status
        time.sleep(1)
    return status


def psql(sql: str):
    return compose("exec", "-T", "db", "psql", "-U", "app", "-d", "appdb", "-tAc", sql)


valid = compose("config", "-q")
c.ok("config 校验通过", valid.returncode == 0, valid.stderr.strip()[:80])
c.equal("三个服务齐备",
        sorted(compose("config", "--services").stdout.split()), ["api", "db", "redis"])

missing = c.run("compose", "-f", COMPOSE_FILE, "--env-file", EMPTY_ENV, "config", "-q")
c.ok("DB_PASSWORD 未设置时立即失败（:? 语法）",
     missing.returncode != 0 and "DB_PASSWORD" in missing.stderr,
     missing.stderr.strip().splitlines()[-1][:90])

up = compose("up", "-d", timeout=600)
c.ok("up -d 拉起整套应用", up.returncode == 0, (up.stderr or up.stdout).strip()[-80:])

c.equal("db 健康检查为 healthy", wait_health(f"{PROJECT}-db-1"), "healthy")
c.equal("redis 健康检查为 healthy", wait_health(f"{PROJECT}-redis-1"), "healthy")
c.ok("api 容器运行中", c.container_running(f"{PROJECT}-api-1"), f"{PROJECT}-api-1")

c.equal("初始化 SQL 只在首次启动执行一次", psql("select count(*) from articles").stdout.strip(), "2")
c.equal("表结构按脚本创建",
         psql("select count(*) from information_schema.columns "
              "where table_name='articles' and column_name in "
              "('id','title','created_at')").stdout.strip(), "3")

first = json.loads(c.wait_http(18081, "/"))
c.equal("api 返回 200 且 JSON 可解析", first["redis"], "up")
second = json.loads(c.http_get(18081, "/"))
c.ok("每次请求都真实自增 Redis 计数", second["hits"] == first["hits"] + 1,
     f"{first['hits']} -> {second['hits']}")
c.equal("api 能连通 PostgreSQL", second["db"], "up")

dns_ip = compose("exec", "-T", "api", "python", "-c",
                 "import socket;print(socket.gethostbyname('db'))").stdout.strip()
c.equal("服务名 db 被解析成容器 IP", dns_ip, c.container_ip(f"{PROJECT}-db-1", NET))

c.equal("三个容器都接入 ch27-net",
        c.out("network", "inspect", "-f", "{{len .Containers}}", NET), "3")
ips = {c.container_ip(f"{PROJECT}-{svc}-1", NET) for svc in ("api", "db", "redis")}
c.equal("每个容器独立 IP", len(ips), 3)

c.ok("写入一条新数据",
     "INSERT 0 1" in psql("insert into articles(title) values ('编排实战新增行')").stdout,
     "")
c.equal("写入后共 3 行", psql("select count(*) from articles").stdout.strip(), "3")

down = compose("down", timeout=300)
c.ok("down 只删容器与网络", down.returncode == 0, "")
c.equal("容器已删除", c.container_exists(f"{PROJECT}-db-1"), False)
c.ok("数据卷仍然保留", c.volume_exists(f"{PROJECT}_pgdata"), f"{PROJECT}_pgdata")

compose("up", "-d", timeout=600)
c.equal("重启后 db 重新 healthy", wait_health(f"{PROJECT}-db-1"), "healthy")
c.equal("重启后数据仍在（initdb 未重复执行）",
        psql("select count(*) from articles").stdout.strip(), "3")

c.ok("向 Redis 写一个键",
     compose("exec", "-T", "redis", "redis-cli", "SET", "chapter", "ch27").stdout.strip() == "OK", "")
compose("exec", "-T", "redis", "redis-cli", "SAVE")
compose("restart", "redis")
wait_health(f"{PROJECT}-redis-1")
c.equal("Redis 重启后键值仍在（RDB 落盘到卷）",
        compose("exec", "-T", "redis", "redis-cli", "GET", "chapter").stdout.strip(), "ch27")

compose("down", "-v", timeout=300)
c.equal("down -v 才删除数据卷", c.volume_exists(f"{PROJECT}_pgdata"), False)

raise SystemExit(c.finish())
