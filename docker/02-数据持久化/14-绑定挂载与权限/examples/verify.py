"""第 14 章 · 绑定挂载与权限：:ro、单文件、覆盖行为。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(14)
temp = Path(tempfile.gettempdir())


def host_path(path: Path) -> str:
    return str(path).replace("\\", "/")


ro_dir = temp / f"{c.prefix}-ro"
ro_dir.mkdir(exist_ok=True)
(ro_dir / "a.txt").write_text("read-only", encoding="utf-8")

ro = c.name("ro")
c.run("run", "-d", "--name", ro, "-v", f"{host_path(ro_dir)}:/data:ro", "alpine:3.20", "sleep", "60")
c.equal("只读挂载可读宿主文件", c.out("exec", ro, "cat", "/data/a.txt").strip(), "read-only")

write_ro = c.run("exec", ro, "sh", "-c", "echo x > /data/a.txt")
c.ok("只读挂载拒绝写入", write_ro.returncode != 0,
     (write_ro.stderr or write_ro.stdout).strip()[:70])

mounts = c.json("inspect", "-f", "{{json .Mounts}}", ro)
c.ok("只读挂载 RW=false", mounts[0]["RW"] is False, str(mounts[0].get("RW")))
c.equal("绑定挂载类型为 bind", mounts[0]["Type"], "bind")

conf = temp / f"{c.prefix}-app.conf"
conf.write_text("host-value", encoding="utf-8")
single = c.name("single")
c.run("run", "-d", "--name", single, "-v", f"{host_path(conf)}:/app.conf:ro", "alpine:3.20", "sleep", "60")
c.equal("单个文件可单独挂载", c.out("exec", single, "cat", "/app.conf").strip(), "host-value")

empty = temp / f"{c.prefix}-empty"
empty.mkdir(exist_ok=True)
overlay = c.name("overlay")
c.run("run", "-d", "--name", overlay, "-v", f"{host_path(empty)}:/usr/share/nginx/html:ro",
      "nginx:1.27-alpine", timeout=300)
listed = c.out("exec", overlay, "ls", "/usr/share/nginx/html")
c.equal("空目录覆盖掉镜像内原有 index.html", listed.strip(), "")

volume = c.name("vol")
c.run("volume", "create", volume)
volume_list = c.out("run", "--rm", "-v", f"{volume}:/usr/share/nginx/html",
                    "nginx:1.27-alpine", "ls", "/usr/share/nginx/html")
c.ok("空命名卷首次挂载会复制镜像内容", "index.html" in volume_list,
     volume_list.replace("\n", " ")[:50])

(ro_dir / "a.txt").write_text("changed-on-host", encoding="utf-8")
c.equal("宿主改文件容器立即可见",
        c.out("exec", ro, "cat", "/data/a.txt").strip(), "changed-on-host")

c.ok("宿主目录被真实挂载", ro_dir.exists() and (ro_dir / "a.txt").read_text(encoding="utf-8") == "changed-on-host")

raise SystemExit(c.finish())
