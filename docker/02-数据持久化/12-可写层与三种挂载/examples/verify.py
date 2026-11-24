"""第 12 章 · 可写层与三种挂载：volume / bind / tmpfs。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(12)

writable = c.name("writable")
c.run("run", "--name", writable, "alpine:3.20", "sh", "-c", "echo data > /data.txt")
diff = c.out("diff", writable)
c.ok("可写层产生文件变更", "/data.txt" in diff, diff)

c.run("rm", "-f", writable)
fresh = c.run("run", "--rm", "alpine:3.20", "sh", "-c", "cat /data.txt 2>/dev/null || echo MISSING")
c.equal("删除容器后可写层数据丢失", fresh.stdout.strip(), "MISSING")

volume = c.name("vol")
c.run("volume", "create", volume)
c.ok("命名卷创建成功", c.volume_exists(volume))

first = c.name("v1")
written = c.run("run", "--name", first, "-v", f"{volume}:/data", "alpine:3.20",
                "sh", "-c", "echo persisted > /data/file; cat /data/file")
c.equal("写入命名卷", written.stdout.strip(), "persisted")

c.run("rm", "-f", first)
second = c.name("v2")
c.run("run", "-d", "--name", second, "-v", f"{volume}:/data", "alpine:3.20", "sleep", "60")
c.equal("换容器后卷数据仍在", c.out("exec", second, "cat", "/data/file").strip(), "persisted")

c.ok("volume ls 可见该卷", volume in c.out("volume", "ls", "--format", "{{.Name}}"))
mountpoint = c.out("volume", "inspect", "-f", "{{.Mountpoint}}", volume)
c.ok("volume inspect 显示挂载点", bool(mountpoint), mountpoint)

host_dir = Path(tempfile.gettempdir()) / f"{c.prefix}-bind"
host_dir.mkdir(exist_ok=True)
(host_dir / "index.txt").write_text("from-host", encoding="utf-8")
host_path = str(host_dir).replace("\\", "/")

bind = c.name("bind")
c.run("run", "-d", "--name", bind, "-v", f"{host_path}:/data", "alpine:3.20", "sleep", "60")
c.equal("绑定挂载读到宿主文件", c.out("exec", bind, "cat", "/data/index.txt").strip(), "from-host")

(host_dir / "index.txt").write_text("updated", encoding="utf-8")
c.equal("宿主修改在容器内立即可见", c.out("exec", bind, "cat", "/data/index.txt").strip(), "updated")

tmpfs = c.name("tmpfs")
c.run("run", "-d", "--name", tmpfs, "--tmpfs", "/tmp", "alpine:3.20", "sleep", "60")
tmpfs_cfg = c.json("inspect", "-f", "{{json .HostConfig.Tmpfs}}", tmpfs)
c.ok("tmpfs 记录在 HostConfig.Tmpfs", "/tmp" in tmpfs_cfg, str(tmpfs_cfg))

types = c.json("inspect", "-f", "{{json .Mounts}}", second)
c.equal("命名卷挂载类型为 volume", [m["Type"] for m in types], ["volume"])

raise SystemExit(c.finish())
