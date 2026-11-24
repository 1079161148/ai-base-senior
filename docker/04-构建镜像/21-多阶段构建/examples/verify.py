"""第 21 章 · 多阶段构建：构建环境与运行环境分离。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(21)
context = Path(__file__).parent

single_tag = f"{c.name('single')}:1.0"
multi_tag = f"{c.name('multi')}:1.0"

c.run("build", "-t", single_tag, "-f", str(context / "Dockerfile.single"), str(context), timeout=300)
c.run("build", "-t", multi_tag, "-f", str(context / "Dockerfile.multistage"), str(context), timeout=300)
c.ok("单阶段镜像构建成功", c.image_exists(single_tag))
c.ok("多阶段镜像构建成功", c.image_exists(multi_tag))

single_out = c.run("run", "--rm", single_tag).stdout.strip()
multi_out = c.run("run", "--rm", multi_tag).stdout.strip()
c.equal("单阶段产物正确", single_out, "built at build stage")
c.equal("多阶段产物与单阶段一致", multi_out, single_out)

single_size = int(c.out("image", "inspect", "-f", "{{.Size}}", single_tag))
multi_size = int(c.out("image", "inspect", "-f", "{{.Size}}", multi_tag))
c.ok("多阶段镜像体积大幅下降", multi_size * 3 < single_size,
     f"多阶段={multi_size // 1024 // 1024}MB 单阶段={single_size // 1024 // 1024}MB")

alpine_release = c.run("run", "--rm", multi_tag, "cat", "/etc/alpine-release").stdout.strip()
c.ok("最终镜像基于 alpine", alpine_release.startswith("3."), alpine_release)

python_probe = c.run("run", "--rm", multi_tag, "which", "python3")
c.ok("最终镜像不含构建环境的 python", python_probe.returncode != 0,
     (python_probe.stdout + python_probe.stderr).strip()[:50])

artifact = c.out("run", "--rm", multi_tag, "cat", "/app/artifact.txt")
c.ok("COPY --from 成功搬运产物", artifact.strip() == "built at build stage", artifact.strip()[:40])

layers = c.out("history", multi_tag, "--format", "{{.CreatedBy}}").splitlines()
c.ok("多阶段最终镜像层数很少", len(layers) <= 5, f"{len(layers)} 层")

single_layers = c.out("history", single_tag, "--format", "{{.CreatedBy}}").splitlines()
c.ok("单阶段镜像层数更多", len(single_layers) >= len(layers),
     f"单阶段={len(single_layers)} 多阶段={len(layers)}")

raise SystemExit(c.finish())
