"""第 33 章 · CI/CD 与多架构构建：buildx bake、本地缓存、跨架构、OCI 产物与元数据。"""

import json
import shutil
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(33)

HERE = Path(__file__).parent
BAKE = str(HERE / "docker-bake.hcl")
CACHE = HERE / ".buildcache"
OUT_OCI = HERE / "out-image.tar"
OUT_LOCAL = HERE / "out-local"
META = HERE / "meta.json"


def bake(*args: str, timeout: int = 600):
    return c.run("buildx", "bake", "-f", BAKE, *args, timeout=timeout)


def cached_lines(proc) -> int:
    # BuildKit 的进度输出走 stderr
    return (proc.stdout + proc.stderr).count("CACHED")


buildx = c.run("buildx", "version")
c.ok("buildx 可用", buildx.returncode == 0,
     (buildx.stdout or buildx.stderr).strip().splitlines()[0][:40])

c.contains("至少有一个 running 的 builder", c.out("buildx", "ls"), "running")

platforms = c.out("buildx", "inspect", "--bootstrap")
c.ok("builder 同时支持 amd64 与 arm64",
     "linux/amd64" in platforms and "linux/arm64" in platforms,
     [line.strip() for line in platforms.splitlines() if line.startswith("Platforms")][:1])

plan_raw = bake("--print")
plan = json.loads(plan_raw.stdout)
c.ok("bake --print 输出可解析的构建计划",
     plan_raw.returncode == 0 and {"api", "worker"} <= set(plan["target"]),
     str(sorted(plan["target"])))
c.equal("bake 计划里 target 的 tag 由变量拼出",
        plan["target"]["api"]["tags"], ["ch33-api:dev"])

first = bake("--load")
c.ok("bake --load 一次构建两个镜像", first.returncode == 0, (first.stderr or first.stdout).strip()[-70:])
c.equal("api 镜像内容正确", c.out("run", "--rm", "ch33-api:dev", "cat", "/app/role"), "api")
c.equal("worker 镜像内容正确", c.out("run", "--rm", "ch33-worker:dev", "cat", "/app/role"), "worker")

c.equal("ARG 写入 OCI 标签",
        c.out("inspect", "-f", '{{index .Config.Labels "org.opencontainers.image.version"}}',
              "ch33-api:dev"), "dev")

second = bake("--load")
c.ok("第二次构建命中本地缓存（CACHED 行数 > 0）", cached_lines(second) > 0,
     f"CACHED={cached_lines(second)}")

override = bake("api", "--load", "--set", "api.tags=ch33-api:v2",
                "--set", "api.args.APP_VERSION=1.2.3")
c.ok("命令行 --set 可覆盖 tag 与构建参数", override.returncode == 0,
     (override.stderr or override.stdout).strip()[-60:])
c.equal("覆盖后的构建参数生效",
        c.out("inspect", "-f", '{{index .Config.Labels "org.opencontainers.image.version"}}',
              "ch33-api:v2"), "1.2.3")

arm = c.run("buildx", "build", "--platform", "linux/arm64", "--load",
            "-t", f"{c.prefix}-arm64:v1", "--target", "api", str(HERE), timeout=600)
c.ok("单平台跨架构构建（arm64）成功", arm.returncode == 0, (arm.stderr or arm.stdout).strip()[-60:])
c.equal("产出的镜像架构是 arm64",
        c.out("inspect", "-f", "{{.Architecture}}", f"{c.prefix}-arm64:v1"), "arm64")

multi_oci = c.run("buildx", "build", "--platform", "linux/amd64,linux/arm64",
                  "--output", f"type=oci,dest={OUT_OCI}",
                  "--metadata-file", str(META),
                  "-t", f"{c.prefix}-multi:v1", "--target", "api", str(HERE), timeout=600)
c.ok("多平台产物可用 OCI 格式导出", multi_oci.returncode == 0 and OUT_OCI.exists(),
     f"{OUT_OCI.stat().st_size // 1024}KB" if OUT_OCI.exists() else "missing")
metadata = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
c.ok("--metadata-file 记录构建产物 digest",
     any("digest" in key for key in metadata), str(list(metadata))[:70])

archs: set[str | None] = set()
if OUT_OCI.exists():
    with tarfile.open(OUT_OCI) as tar:
        index = json.loads(tar.extractfile("index.json").read())
        for manifest in index["manifests"]:
            if "index" in manifest.get("mediaType", ""):
                # buildx 导出的 OCI 布局是 index → manifest list → 各平台 manifest
                blob = "blobs/sha256/" + manifest["digest"].split(":")[1]
                inner = json.loads(tar.extractfile(blob).read())
                archs |= {item.get("platform", {}).get("architecture")
                          for item in inner["manifests"]}
            elif "platform" in manifest:
                archs.add(manifest["platform"].get("architecture"))
# index 里除了两个平台的镜像，还会有 provenance/SBOM 的 attestation（platform 为 unknown/unknown）
c.ok("多平台产物索引里同时含 amd64 与 arm64", {"amd64", "arm64"} <= archs, str(sorted(map(str, archs))))

local_out = c.run("buildx", "build", "--target", "base",
                  "--output", f"type=local,dest={OUT_LOCAL}",
                  "-t", f"{c.prefix}-export:v1", str(HERE), timeout=600)
exported = OUT_LOCAL / "out" / "hello.txt"
c.ok("type=local 把构建产物导出到指定目录",
     local_out.returncode == 0 and exported.exists(),
     exported.read_text(encoding="utf-8").strip() if exported.exists() else "missing")

for asset in ("ch33-api:dev", "ch33-worker:dev", "ch33-api:v2",
              f"{c.prefix}-arm64:v1", f"{c.prefix}-export:v1"):
    c.run("rmi", "-f", asset)

for path in (CACHE, OUT_LOCAL, OUT_OCI, META):
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink()

raise SystemExit(c.finish())
