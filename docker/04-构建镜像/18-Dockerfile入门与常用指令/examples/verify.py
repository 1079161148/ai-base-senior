"""第 18 章 · Dockerfile 入门与常用指令。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(18)
context = Path(__file__).parent

tag = f"{c.name('web')}:1.0"
build = c.run("build", "-t", tag, "-f", str(context / "Dockerfile"), str(context), timeout=300)
c.ok("镜像构建成功", build.returncode == 0,
     (build.stdout + build.stderr).strip().splitlines()[-1][:70] if (build.stdout + build.stderr).strip() else "")

config = c.json("image", "inspect", tag)[0]["Config"]
c.ok("ENV 写入镜像配置", "APP_ENV=dev" in config["Env"], str(config["Env"])[:60])
c.equal("WORKDIR 生效", config["WorkingDir"], "/www")
c.ok("EXPOSE 记录端口", "8000/tcp" in (config.get("ExposedPorts") or {}), str(config.get("ExposedPorts")))
c.equal("CMD 为 exec 形式", config["Cmd"], ["python", "app.py"])
c.equal("USER 生效", config["User"], "appuser")
c.equal("LABEL 写入元数据", (config.get("Labels") or {}).get("maintainer"), "study")

web = c.name("webc")
c.run("run", "-d", "--name", web, "-p", "18110:8000", tag, timeout=120)
body = c.wait_http(18110)
c.ok("构建出的镜像可运行并对外服务", "Hello from Dockerfile" in body, body.strip()[:50])

entry_tag = f"{c.name('entry')}:1.0"
c.run("build", "-t", entry_tag, "-f", str(context / "Dockerfile.entrypoint"), str(context), timeout=300)
entry_config = c.json("image", "inspect", entry_tag)[0]["Config"]
c.equal("ENTRYPOINT 生效", entry_config["Entrypoint"], ["python", "app.py"])
c.equal("ENTRYPOINT 模式下 CMD 作为默认参数", entry_config["Cmd"], ["--port", "8000"])

overridden = c.run("run", "-d", "--name", c.name("override"), "-p", "18111:9000",
                   entry_tag, "--port", "9000", timeout=120)
c.ok("命令行参数可覆盖 CMD", overridden.returncode == 0,
     (overridden.stderr or overridden.stdout).strip()[:70])
if overridden.returncode == 0:
    override_body = c.wait_http(18111)
    c.ok("覆盖后的端口生效", "Hello from Dockerfile" in override_body, override_body.strip()[:40])

layers = c.out("history", tag, "--format", "{{.CreatedBy}}").splitlines()
c.ok("构建历史可追溯每条指令", len(layers) >= 5, f"{len(layers)} 层")

raise SystemExit(c.finish())
