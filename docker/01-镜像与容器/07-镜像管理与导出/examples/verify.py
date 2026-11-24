"""第 07 章 · 镜像管理：查看、打标签、导出导入、看层。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(7)

src = "alpine:3.20"
c.run("pull", src, timeout=300)
c.ok("源镜像存在", c.image_exists(src))

alias = f"{c.name('copy')}:v1"
c.run("tag", src, alias)
c.ok("tag 创建别名", c.image_exists(alias))

history = c.out("history", src, "--format", "{{.CreatedBy}}", "--no-trunc")
c.ok("history 可看构建层", len(history.splitlines()) >= 1, f"{len(history.splitlines())} 层")

size = int(c.out("image", "inspect", src, "-f", "{{.Size}}"))
c.ok("inspect 可读镜像大小", size > 0, f"{size // 1024} KB")

tar_path = Path(tempfile.gettempdir()) / f"{c.prefix}-alpine.tar"
save = c.run("save", "-o", str(tar_path), src, timeout=300)
c.ok("save 导出为 tar", save.returncode == 0 and tar_path.exists() and tar_path.stat().st_size > 0,
     f"{tar_path.stat().st_size // 1024} KB" if tar_path.exists() else "文件不存在")

load = c.run("load", "-i", str(tar_path), timeout=300)
c.ok("load 从 tar 导入", load.returncode == 0 and "Loaded image" in (load.stdout + load.stderr),
     (load.stdout + load.stderr).strip().splitlines()[-1][:60])
tar_path.unlink(missing_ok=True)

base_c = c.name("base")
owned = f"{c.name('owned')}:v1"
c.run("run", "--name", base_c, src, "sh", "-c", "echo mark > /mark")
c.run("commit", base_c, owned)
c.run("rm", "-f", base_c)
c.ok("commit 生成单 tag 镜像", c.image_exists(owned))

runner = c.name("runner")
c.run("run", "-d", "--name", runner, owned, "sleep", "60")
in_use = c.run("rmi", owned)
c.ok("镜像被运行中容器占用时不能删", in_use.returncode != 0,
     (in_use.stderr or in_use.stdout).strip()[:70])

c.run("rm", "-f", runner)
after_rm = c.run("rmi", owned)
c.ok("删除容器后镜像可删", after_rm.returncode == 0, (after_rm.stdout or after_rm.stderr).strip()[:60])

c.ok("image prune 可执行", c.run("image", "prune", "-f").returncode == 0)

formatted = c.out("images", "--format", "{{.Repository}}:{{.Tag}}")
c.ok("格式化输出可用", "alpine:3.20" in formatted, formatted.replace("\n", " ")[:60])

layers = c.out("history", src, "--format", "{{.Size}}", "--no-trunc").splitlines()
c.ok("层大小可读", len(layers) >= 1, f"{len(layers)} 行")

raise SystemExit(c.finish())
