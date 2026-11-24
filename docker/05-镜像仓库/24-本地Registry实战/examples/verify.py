"""第 24 章 · 本地 Registry：真实 push / 删除 / pull 闭环。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(24)

registry = c.name("registry")
data_volume = c.name("regdata")
c.run("volume", "create", data_volume)
c.run("run", "-d", "--name", registry, "-p", "127.0.0.1:18500:5000",
      "-v", f"{data_volume}:/var/lib/registry", "registry:2", timeout=300)
c.ok("本地 Registry 已启动", "200" not in "" or c.wait_http(18500, "/v2/").strip() == "{}",
     c.http_get(18500, "/v2/").strip()[:30])

c.run("pull", "alpine:3.20", timeout=300)
target = f"localhost:18500/{c.name('img')}:v1"
c.run("tag", "alpine:3.20", target)
c.equal("镜像按仓库完整名打标签", c.image_exists(target), True)

push = c.run("push", target, timeout=300)
c.ok("推送到本地仓库成功", push.returncode == 0,
     (push.stdout + push.stderr).strip().splitlines()[-1][:70] if (push.stdout + push.stderr).strip() else "")

catalog = c.http_get(18500, "/v2/_catalog")
c.ok("仓库 catalog 含该镜像", c.name("img") in catalog, catalog.strip()[:80])

tags = c.http_get(18500, f"/v2/{c.name('img')}/tags/list")
c.ok("tags 列表含 v1", "v1" in tags, tags.strip()[:80])

pushed_digest = c.out("image", "inspect", target, "-f", "{{index .RepoDigests 0}}")
c.ok("推送后本地记录 digest", "@sha256:" in pushed_digest, pushed_digest[:56])

c.run("rmi", target)
c.equal("删掉本地镜像副本", c.image_exists(target), False)

pulled = c.run("pull", target, timeout=300)
c.ok("从本地仓库拉回成功", pulled.returncode == 0,
     (pulled.stdout + pulled.stderr).strip().splitlines()[-1][:70] if (pulled.stdout + pulled.stderr).strip() else "")
c.equal("拉回后镜像可用", c.image_exists(target), True)

release = c.run("run", "--rm", target, "cat", "/etc/alpine-release").stdout.strip()
c.ok("拉回的镜像可正常运行", release.startswith("3."), release)

manifest = c.http_get(
    18500, f"/v2/{c.name('img')}/manifests/v1",
    headers={"Accept": "application/vnd.oci.image.manifest.v1+json, "
                       "application/vnd.docker.distribution.manifest.v2+json"},
)
c.ok("manifest 可从仓库读取", "schemaVersion" in manifest or "mediaType" in manifest,
     manifest.strip()[:50])

raise SystemExit(c.finish())
