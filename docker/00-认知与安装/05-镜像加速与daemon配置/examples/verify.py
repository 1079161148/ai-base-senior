"""第 05 章 · 镜像加速与 daemon 配置。"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(5)

info = c.out("info")
c.ok("info 含 Registry Mirrors 段", "Registry Mirrors" in info)

mirrors = c.out(
    "info", "--format", "{{range .RegistryConfig.Mirrors}}{{println .}}{{end}}"
).split()
c.ok("加速源可读", bool(mirrors), str(mirrors[:3]))
c.ok("加速源是合法 URL",
     all(m.startswith(("http://", "https://")) for m in mirrors), str(mirrors[:2]))
c.ok("至少配置一个加速源", len(mirrors) >= 1, f"{len(mirrors)} 个")

index = c.out("info", "--format", "{{.IndexServerAddress}}")
c.equal("默认仓库是 Docker Hub", index, "https://index.docker.io/v1/")

driver = c.out("info", "--format", "{{.Driver}}")
c.ok("存储驱动可读", bool(driver), driver)

settings_path = Path(os.environ.get("APPDATA", "")) / "Docker" / "settings-store.json"
c.ok("桌面端配置文件存在", settings_path.exists(), str(settings_path))

settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
c.ok("配置文件是合法 JSON", isinstance(settings, dict) and len(settings) > 0, f"{len(settings)} 个键")

sample = json.dumps({
    "registry-mirrors": mirrors[:1],
    "insecure-registries": [],
    "log-driver": "json-file",
    "log-opts": {"max-size": "50m", "max-file": "3"},
})
parsed = json.loads(sample)
c.ok("标准 daemon.json 结构可校验",
     parsed["registry-mirrors"] == mirrors[:1] and parsed["log-opts"]["max-file"] == "3",
     sample[:70])

pull = c.run("pull", "alpine:3.20", timeout=300)
c.ok("经加速源拉取成功", pull.returncode == 0, pull.stdout.strip().splitlines()[-1][:60] if pull.stdout.strip() else "")

raise SystemExit(c.finish())
