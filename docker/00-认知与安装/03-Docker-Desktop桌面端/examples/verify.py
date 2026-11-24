"""第 03 章 · Docker Desktop 桌面端：形态、资源与配置。"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(3)

os_name = c.out("info", "--format", "{{.OperatingSystem}}")
c.ok("运行形态可识别", bool(os_name), os_name)

contexts = c.out("context", "ls")
c.ok("存在 desktop-linux context", "desktop-linux" in contexts, contexts.replace("\n", " ")[:110])

ncpu = int(c.out("info", "--format", "{{.NCPU}}"))
mem = int(c.out("info", "--format", "{{.MemTotal}}"))
c.ok("桌面端 VM 已分配 CPU", ncpu > 0, f"{ncpu} 核")
c.ok("桌面端 VM 已分配内存", mem > 0, f"{mem / 1024 ** 3:.1f} GB")

root_dir = c.out("info", "--format", "{{.DockerRootDir}}")
c.ok("数据目录可读", bool(root_dir), root_dir)

c.ok("磁盘用量视图可用", c.run("system", "df").returncode == 0)

desktop = c.run("desktop", "version")
c.ok("docker desktop 子命令可用", desktop.returncode == 0,
     (desktop.stdout or desktop.stderr).strip().splitlines()[0] if (desktop.stdout or desktop.stderr).strip() else "")

settings_path = Path(os.environ.get("APPDATA", "")) / "Docker" / "settings-store.json"
c.ok("桌面端配置文件存在", settings_path.exists(), str(settings_path))

if settings_path.exists():
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    c.ok("配置项可读", isinstance(settings, dict) and len(settings) > 0, f"{len(settings)} 个配置项")
    c.ok("可查开源自启开关", "AutoStart" in settings, str([k for k in settings if "art" in k][:3]))
    c.ok("可查 Docker AI 开关", "EnableDockerAI" in settings, str([k for k in settings if "AI" in k][:3]))
    c.ok("可查 containerd 快照器开关", "UseContainerdSnapshotter" in settings,
         str([k for k in settings if "Snapshot" in k][:3]))

c.ok("daemon 可用", c.run("ps").returncode == 0)

raise SystemExit(c.finish())
