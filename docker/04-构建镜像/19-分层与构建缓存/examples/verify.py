"""第 19 章 · 分层与构建缓存。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(19)
context = Path(__file__).parent
tag = f"{c.name('cache')}:1.0"
step2 = context / "step2.txt"
original = step2.read_text(encoding="utf-8")


def build(*extra: str):
    return c.run("build", *extra, "-t", tag, "-f", str(context / "Dockerfile"), str(context), timeout=300)


def cached(proc) -> int:
    # BuildKit 的进度输出走 stderr，必须合并统计
    return (proc.stdout + proc.stderr).count("CACHED")


def layer_digests() -> list[str]:
    # 用 RootFS.Layers 判断层是否复用；镜像 ID 会因每次新生成 attestation manifest 而变化
    return c.json("image", "inspect", "-f", "{{json .RootFS.Layers}}", tag)


try:
    first = build()
    c.ok("首次构建成功", first.returncode == 0,
         (first.stdout + first.stderr).strip().splitlines()[-1][:60] if (first.stdout + first.stderr).strip() else "")
    layers_first = layer_digests()

    second = build()
    c.ok("无改动时多层命中缓存", cached(second) >= 4, f"{cached(second)} 个 CACHED")
    c.equal("无改动时层列表完全复用", layer_digests(), layers_first)

    step2.write_text("beta-changed\n", encoding="utf-8")
    third = build()
    c.ok("改动文件后末层变化", layer_digests()[-1] != layers_first[-1],
         f"{layer_digests()[-1][:19]} != {layers_first[-1][:19]}")
    c.ok("改动之前的层仍命中缓存", cached(third) >= 2, f"{cached(third)} 个 CACHED")

    nocache = build("--no-cache")
    c.ok("--no-cache 强制重建不用缓存", cached(nocache) <= 1, f"{cached(nocache)} 个 CACHED")
finally:
    step2.write_text(original, encoding="utf-8")

c.run("build", "-t", tag, "-f", str(context / "Dockerfile"), str(context), timeout=300)

layers = c.out("history", tag, "--format", "{{.CreatedBy}}").splitlines()
c.ok("构建历史可见多层", len(layers) >= 5, f"{len(layers)} 层")

output = c.run("run", "--rm", tag)
c.ok("RUN 的产物固化进镜像",
     "layer-2 built" in output.stdout and "layer-4 built" in output.stdout,
     output.stdout.strip().replace("\n", " | ")[:70])

raise SystemExit(c.finish())
