"""第 36 章 · 毕业项目与排障手册：发布/重建/回滚 + 八类故障的真实报错与诊断命令。"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(36)

HERE = Path(__file__).parent
COMPOSE_FILE = str(HERE / "compose.yaml")
PROJECT = "ch36-capstone"
APP = f"{PROJECT}-app-1"
PORT = 18096


def compose(*args: str, env: str = ".env.v1", **kwargs):
    return c.run("compose", "-f", COMPOSE_FILE, "-p", PROJECT,
                 "--env-file", str(HERE / env), *args, **kwargs)


def version() -> str:
    return json.loads(c.wait_http(PORT, "/version", timeout=60))["version"]


def build(tag: str):
    return c.run("build", "--build-arg", f"APP_VERSION={tag}", "-t", f"ch36-app:{tag}",
                 str(HERE), timeout=600)


c.ok("构建 v1 镜像", build("v1").returncode == 0, "")
c.ok("构建 v2 镜像", build("v2").returncode == 0, "")

up = compose("up", "-d", timeout=300)
c.ok("首次发布成功", up.returncode == 0, (up.stderr or up.stdout).strip()[-50:])
c.equal("线上版本是 v1", version(), "v1")
first_id = c.out("inspect", "-f", "{{.Id}}", APP)

release = compose("up", "-d", timeout=300, env=".env.v2")
c.ok("发布 v2（up -d 自动重建变更的服务）", release.returncode == 0, "")
time.sleep(2)
c.equal("线上版本切到 v2", version(), "v2")
c.ok("容器被替换（ID 变化）", c.out("inspect", "-f", "{{.Id}}", APP) != first_id, "")
c.equal("旧容器没有残留（不是叠加部署）", len(compose("ps", "-q").stdout.split()), 1)

rollback = compose("up", "-d", timeout=300, env=".env.v1")
c.ok("回滚到 v1", rollback.returncode == 0, "")
time.sleep(2)
c.equal("回滚后版本为 v1", version(), "v1")

crash = c.run("run", "--rm", f"ch36-app:v1", "python", "-c", "raise SystemExit(3)")
c.equal("① 容器异常退出时保留退出码", crash.returncode, 3)

c.run("run", "-d", "--name", c.name("bad"), "--entrypoint", "sh", "ch36-app:v1",
      "-c", "echo 'fatal: missing config' 1>&2; exit 7")
time.sleep(1)
bad_logs = c.run("logs", c.name("bad"))
c.contains("② docker logs 能看到崩溃原因", bad_logs.stderr + bad_logs.stdout, "fatal: missing config")
c.equal("② 退出码可在 inspect 中确认",
        c.out("inspect", "-f", "{{.State.ExitCode}}", c.name("bad")), "7")

conflict = c.run("run", "-d", "--name", c.name("port"), "-p", f"127.0.0.1:{PORT}:8000",
                 "ch36-app:v1")
c.ok("③ 端口冲突报错明确", conflict.returncode != 0,
     (conflict.stderr or conflict.stdout).strip().splitlines()[-1][:80])

duplicate = c.run("run", "-d", "--name", APP, "ch36-app:v1")
c.contains("④ 容器名冲突报错明确", duplicate.stderr + duplicate.stdout,
           f'container name "/{APP}" is already in use')

c.run("run", "-d", "--name", c.name("unhealthy"), "--entrypoint", "sh", "ch36-app:v1",
      "-c", "sleep 60")
time.sleep(2)
c.ok("⑤ 镜像级 HEALTHCHECK 对派生容器同样生效",
     c.run("inspect", "-f", "{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}",
           c.name("unhealthy")).stdout.strip() in ("starting", "healthy", "unhealthy"),
     "镜像里写了 HEALTHCHECK")

health_log = c.out("inspect", "-f", "{{json .State.Health.Log}}", APP)
c.ok("⑤ 健康检查历史可读（定位不健康原因）",
     health_log.startswith("[") and "ExitCode" in health_log, health_log[:60])

c.run("run", "-d", "--name", c.name("term"), "ch36-app:v1", "python", "app.py")
time.sleep(2)
c.run("stop", c.name("term"), timeout=120)
c.equal("⑥ PID 1 是 python 时忽略 SIGTERM，被 SIGKILL（137）",
        c.out("inspect", "-f", "{{.State.ExitCode}}", c.name("term")), "137")

c.run("run", "-d", "--name", c.name("term-init"), "--init", "ch36-app:v1", "python", "app.py")
time.sleep(2)
c.run("stop", c.name("term-init"), timeout=120)
c.equal("⑥ 加 --init（tini 作为 PID 1）后能收到 SIGTERM（143）",
        c.out("inspect", "-f", "{{.State.ExitCode}}", c.name("term-init")), "143")

c.run("run", "-d", "--name", c.name("diff"), "ch36-app:v1", "python", "app.py")
time.sleep(2)
c.run("exec", c.name("diff"), "sh", "-c", "echo drift > /home/appuser/drift.txt")
c.contains("⑦ docker diff 能发现容器内文件漂移",
           c.out("diff", c.name("diff")), "A /home/appuser/drift.txt")

df = c.out("system", "df")
c.ok("⑧ docker system df 可查磁盘占用",
     "Images" in df and "Containers" in df, df.splitlines()[0][:50])

exit_codes = c.out("inspect", "-f", "{{.State.ExitCode}}", c.name("bad"))
c.ok("⑨ 137 与 143 的语义不同（KILL vs TERM）",
     exit_codes == "7" and c.out("inspect", "-f", "{{.State.ExitCode}}", APP) in ("0", ""),
     f"bad={exit_codes}")

compose("down", "-v", timeout=300)

raise SystemExit(c.finish())
