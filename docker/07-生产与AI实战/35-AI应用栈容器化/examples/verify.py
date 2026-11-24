"""第 35 章 · AI 应用栈容器化：pgvector 检索、Redis 会话、工具网关、Agent 编排、DevContainer。"""

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(35)

HERE = Path(__file__).parent
COMPOSE_FILE = str(HERE / "compose.yaml")
ENV_FILE = str(HERE / ".env")
PROJECT = "ch35-ai"
NET = "ch35-net"


def compose(*args: str, **kwargs):
    return c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT, "--env-file", ENV_FILE,
                 *args, **kwargs)


def psql(sql: str):
    return compose("exec", "-T", "db", "psql", "-U", "app", "-d", "ai", "-tAc", sql)


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read())


valid = compose("config", "-q")
c.ok("compose 配置校验通过", valid.returncode == 0, valid.stderr.strip()[:70])
c.equal("四个服务齐备", sorted(compose("config", "--services").stdout.split()),
        ["agent", "cache", "db", "tools"])

up = compose("up", "-d", timeout=900)
c.ok("up -d 拉起 AI 应用栈", up.returncode == 0, (up.stderr or up.stdout).strip()[-70:])

deadline = time.time() + 180
healthy = False
while time.time() < deadline:
    status = c.run("inspect", "-f", "{{if .State.Health}}{{.State.Health.Status}}{{end}}",
                   f"{PROJECT}-db-1").stdout.strip()
    if status == "healthy":
        healthy = True
        break
    time.sleep(1)
c.ok("db 健康检查通过", healthy, "pg_isready")

c.equal("pgvector 扩展已安装",
        psql("select count(*) from pg_extension where extname='vector'").stdout.strip(), "1")
c.equal("向量列类型为 vector(3)",
        psql("select atttypid::regtype from pg_attribute "
             "where attrelid='docs'::regclass and attname='embedding'").stdout.strip(), "vector")
c.contains("HNSW 索引已创建",
           psql("select indexdef from pg_indexes where indexname='docs_embedding_idx'").stdout,
           "hnsw")

nearest = psql("select content from docs order by embedding <-> '[1,0,0]' limit 1").stdout.strip()
c.equal("余弦距离检索返回最相近条目", nearest, "docker 容器编排")

c.equal("初始化数据为 4 行", psql("select count(*) from docs").stdout.strip(), "4")

c.ok("写入会话缓存",
     compose("exec", "-T", "cache", "redis-cli", "SETEX", "answer:docker", "600",
             "容器编排答案").stdout.strip() == "OK", "")
c.equal("缓存可读回",
        compose("exec", "-T", "cache", "redis-cli", "GET", "answer:docker").stdout.strip(),
        "容器编排答案")
c.equal("AOF 已开启（重启不丢会话）",
        compose("exec", "-T", "cache", "redis-cli", "CONFIG", "GET", "appendonly").stdout.split()[-1],
        "yes")

agent_health = json.loads(c.wait_http(18095, "/healthz", timeout=90))
c.ok("agent 能连通 db 与 redis", agent_health["db"] == "up" and agent_health["redis"] == "up",
     json.dumps(agent_health))

tools_direct = compose("exec", "-T", "agent", "python", "-c",
                       "import urllib.request;print(urllib.request.urlopen('http://tools:8001/tools').read().decode())")
tool_names = [tool["name"] for tool in json.loads(tools_direct.stdout)["tools"]]
c.equal("agent 通过服务名调用工具网关", tool_names,
        ["kb.search", "kb.upsert", "web.fetch"])

reply = post_json("http://127.0.0.1:18095/chat", {"question": "docker"})
c.ok("agent 返回结构化回答", reply["answer"].startswith("[stub]") and len(reply["tools"]) == 3,
     json.dumps(reply, ensure_ascii=False)[:80])
c.ok("提示词从只读挂载读取", reply["prompt_chars"] > 0, f"prompt_chars={reply['prompt_chars']}")

c.equal("四个容器都在 ch35-net",
        c.out("network", "inspect", "-f", "{{len .Containers}}", NET), "4")
c.equal("db 端口没有发布到宿主（生产默认）",
        c.out("inspect", "-f", "{{json .HostConfig.PortBindings}}", f"{PROJECT}-db-1"), "{}")

devcontainer = json.loads((HERE / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8"))
c.ok("devcontainer.json 可解析且指向 compose 服务",
     devcontainer["service"] == "agent" and devcontainer["dockerComposeFile"] == "../compose.yaml",
     json.dumps(devcontainer)[:60])

compose("down", timeout=300)
c.ok("down 后数据卷保留", c.volume_exists(f"{PROJECT}_pgdata"), "")
compose("up", "-d", timeout=900)
deadline = time.time() + 180
while time.time() < deadline:
    if c.run("inspect", "-f", "{{if .State.Health}}{{.State.Health.Status}}{{end}}",
             f"{PROJECT}-db-1").stdout.strip() == "healthy":
        break
    time.sleep(1)
c.equal("重启后向量数据仍在（initdb 未重跑）",
        psql("select count(*) from docs").stdout.strip(), "4")

compose("down", "-v", timeout=300)
c.equal("down -v 清理数据卷", c.volume_exists(f"{PROJECT}_pgdata"), False)

raise SystemExit(c.finish())
