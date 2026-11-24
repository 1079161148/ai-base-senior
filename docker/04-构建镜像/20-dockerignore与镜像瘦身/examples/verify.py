"""第 20 章 · .dockerignore 与镜像瘦身。"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(20)
ctx = Path(tempfile.gettempdir()) / f"{c.prefix}-ctx"
if ctx.exists():
    shutil.rmtree(ctx)
ctx.mkdir(parents=True)

(ctx / "Dockerfile").write_text("FROM alpine:3.20\nCOPY . /app/\nCMD [\"ls\", \"/app\"]\n",
                                encoding="utf-8")
(ctx / "app.txt").write_text("hello", encoding="utf-8")
(ctx / "blob.bin").write_bytes(os.urandom(5 * 1024 * 1024))


def build(tag: str) -> None:
    c.run("build", "-t", tag, "-f", str(ctx / "Dockerfile"), str(ctx), timeout=300)


def size_of(tag: str) -> int:
    return int(c.out("image", "inspect", "-f", "{{.Size}}", tag))


try:
    fat_tag = f"{c.name('fat')}:1.0"
    build(fat_tag)
    fat_size = size_of(fat_tag)
    fat_list = c.run("run", "--rm", fat_tag).stdout
    c.ok("未配置 ignore 时大文件进入镜像", "blob.bin" in fat_list, fat_list.strip().replace("\n", " ")[:60])
    c.ok("此时镜像体积较大", fat_size > 5 * 1024 * 1024, f"{fat_size // 1024 // 1024} MB")

    (ctx / ".dockerignore").write_text("blob.bin\n", encoding="utf-8")
    slim_tag = f"{c.name('slim')}:1.0"
    build(slim_tag)
    slim_size = size_of(slim_tag)
    slim_list = c.run("run", "--rm", slim_tag).stdout
    c.ok("配置 ignore 后镜像显著变小", slim_size < fat_size, f"{slim_size // 1024 // 1024}MB < {fat_size // 1024 // 1024}MB")
    c.ok("被忽略的文件不在镜像内", "blob.bin" not in slim_list, slim_list.strip().replace("\n", " ")[:60])
    c.ok("忽略后体积缩减超过 5MB", fat_size - slim_size > 5 * 1024 * 1024,
         f"缩减 {(fat_size - slim_size) // 1024 // 1024} MB")

    one_layer = ctx / "Dockerfile.onelayer"
    one_layer.write_text(
        "FROM alpine:3.20\n"
        "RUN dd if=/dev/urandom of=/tmp/big bs=1M count=10 && rm -f /tmp/big\n"
        "CMD [\"true\"]\n",
        encoding="utf-8",
    )
    one_tag = f"{c.name('onelayer')}:1.0"
    c.run("build", "-t", one_tag, "-f", str(one_layer), str(ctx), timeout=300)

    two_layer = ctx / "Dockerfile.twolayer"
    two_layer.write_text(
        "FROM alpine:3.20\n"
        "RUN dd if=/dev/urandom of=/tmp/big bs=1M count=10\n"
        "RUN rm -f /tmp/big\n"
        "CMD [\"true\"]\n",
        encoding="utf-8",
    )
    two_tag = f"{c.name('twolayer')}:1.0"
    c.run("build", "-t", two_tag, "-f", str(two_layer), str(ctx), timeout=300)

    one_size = size_of(one_tag)
    two_size = size_of(two_tag)
    c.ok("同一 RUN 内创建并删除不残留", one_size < two_size,
         f"同层={one_size // 1024 // 1024}MB 跨层={two_size // 1024 // 1024}MB")
    c.ok("跨层删除会留下幽灵数据", two_size - one_size > 8 * 1024 * 1024,
         f"相差 {(two_size - one_size) // 1024 // 1024} MB")
finally:
    shutil.rmtree(ctx, ignore_errors=True)

raise SystemExit(c.finish())
