"""第 06 章 · 镜像命名规则与拉取。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(6)

c.run("pull", "nginx:1.27-alpine", timeout=300)
c.ok("短名拉取成功", c.image_exists("nginx:1.27-alpine"))

c.ok("完整名等价于短名", c.image_exists("docker.io/library/nginx:1.27-alpine"))

digest = c.out("image", "inspect", "nginx:1.27-alpine", "-f", "{{index .RepoDigests 0}}")
c.ok("RepoDigests 是 sha256 内容寻址", "@sha256:" in digest, digest[:56])

c.run("pull", "alpine", timeout=300)
c.ok("不带标签默认 latest", c.image_exists("alpine:latest"))

digest_320 = c.out("image", "inspect", "alpine:3.20", "-f", "{{index .RepoDigests 0}}")
digest_latest = c.out("image", "inspect", "alpine:latest", "-f", "{{index .RepoDigests 0}}")
c.ok("不同标签对应不同 digest", digest_320 != digest_latest,
     f"3.20={digest_320[-16:]} latest={digest_latest[-16:]}")

alias = c.name("alias") + ":v1"
c.run("tag", "alpine:3.20", alias)
c.ok("tag 创建别名", c.image_exists(alias))
id_src = c.out("images", "-q", "--no-trunc", "alpine:3.20")
id_alias = c.out("images", "-q", "--no-trunc", alias)
c.equal("别名与原镜像共享同一 ID", id_src, id_alias)

c.ok("images 列表可读", "alpine" in c.out("images"))

c.run("pull", "python:3.12-alpine", timeout=300)
size_alpine = int(c.out("image", "inspect", "python:3.12-alpine", "-f", "{{.Size}}"))
size_slim = int(c.out("image", "inspect", "python:3.12-slim", "-f", "{{.Size}}"))
c.ok("同一镜像的不同变体体积不同", size_alpine != size_slim,
     f"alpine={size_alpine // 1048576}MB slim={size_slim // 1048576}MB")

arch = c.out("image", "inspect", "alpine:3.20", "-f", "{{.Architecture}}")
c.equal("镜像架构可查", arch, "amd64")

raise SystemExit(c.finish())
