"""第 11 章 · 磁盘清理：system df 与各类 prune。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(11)

df = c.out("system", "df")
c.ok("system df 可读", "Images" in df or "images" in df, df.splitlines()[0][:70] if df else "")
c.ok("system df 含可回收空间", "RECLAIMABLE" in df.upper())

stopped = c.name("stopped")
c.run("run", "--name", stopped, "--label", "chapter=11", "alpine:3.20", "true")
c.ok("已停止容器存在", c.container_exists(stopped) and not c.container_running(stopped))
c.run("container", "prune", "-f", "--filter", "label=chapter=11")
c.ok("container prune 清掉已停止容器", not c.container_exists(stopped))

volume = c.name("vol")
c.run("volume", "create", "--label", "chapter=11", volume)
c.ok("卷已创建", c.volume_exists(volume))
c.ok("volume prune 命令可用", c.run("volume", "prune", "--help").returncode == 0)
c.run("volume", "rm", volume)
c.ok("未使用卷可精确删除", not c.volume_exists(volume))

network = c.name("net")
c.run("network", "create", "--label", "chapter=11", network)
c.ok("网络已创建", c.network_exists(network))
c.run("network", "prune", "-f", "--filter", "label=chapter=11")
c.ok("network prune 清掉未使用网络", not c.network_exists(network))

dangling = f"{c.name('dg')}:v1"
build = c.run("build", "-t", dangling, "-", input_text="FROM alpine:3.20\nRUN echo x > /x\n", timeout=300)
c.ok("构建一个临时镜像", build.returncode == 0, (build.stdout or build.stderr).strip().splitlines()[-1][:60] if (build.stdout or build.stderr).strip() else "")
c.run("rmi", dangling)

prune = c.run("image", "prune", "-f")
c.ok("image prune 可执行", prune.returncode == 0, (prune.stdout or prune.stderr).strip()[:60])

c.ok("builder prune 可执行", c.run("builder", "prune", "-f").returncode == 0)

system_prune = c.run("system", "prune", "-f", "--filter", "label=chapter=11")
c.ok("system prune 可按 label 精确清理", system_prune.returncode == 0,
     (system_prune.stdout or system_prune.stderr).strip().splitlines()[-1][:60] if (system_prune.stdout or system_prune.stderr).strip() else "")

after = c.out("system", "df")
c.ok("清理后仍可统计", "Images" in after)

raise SystemExit(c.finish())
