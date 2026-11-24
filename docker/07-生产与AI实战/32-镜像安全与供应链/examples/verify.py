"""第 32 章 · 镜像安全与供应链：digest 固定、构建期密钥泄漏与 secret 挂载修复、扫描工具边界。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(32)

HERE = Path(__file__).parent
SECRET = (HERE / "secrets" / "db_password.txt").read_text(encoding="utf-8").strip()
LEAK_IMG = f"{c.prefix}-leak:v1"
CLEAN_IMG = f"{c.prefix}-clean:v1"


def build(tag: str, dockerfile: str, *extra: str, timeout: int = 300):
    return c.run("build", "-f", str(HERE / dockerfile), "-t", tag, *extra, str(HERE),
                 timeout=timeout)


scout = c.run("scout", "version")
c.ok("镜像扫描工具 docker scout 就绪",
     scout.returncode == 0 and "version" in (scout.stdout + scout.stderr).lower(),
     (scout.stdout + scout.stderr).strip().splitlines()[0][:40] if (scout.stdout + scout.stderr).strip() else "")
unlogged = c.run("scout", "quickview", "alpine:3.20", timeout=120)
c.ok("未登录时 scout 明确要求认证（CI 里需 PAT）",
     "log in" in (unlogged.stdout + unlogged.stderr).lower(),
     ((unlogged.stdout + unlogged.stderr).strip().splitlines() or [""])[-1][:70])

digest_ref = c.out("inspect", "-f", "{{index .RepoDigests 0}}", "alpine:3.20")
c.ok("镜像带不可变 digest", "@sha256:" in digest_ref, digest_ref[:56])

pulled = c.run("pull", digest_ref, timeout=300)
c.ok("可以按 digest 精确拉取（供应链可复现）", pulled.returncode == 0,
     (pulled.stderr or pulled.stdout).strip().splitlines()[-1][:60]
     if (pulled.stderr or pulled.stdout).strip() else "")
c.contains("docker images --digests 能列出 digest",
           c.out("images", "--digests", "alpine:3.20"), "sha256:")

leak = build(LEAK_IMG, "Dockerfile.leak", "--build-arg", f"DB_PASSWORD={SECRET}")
c.ok("反面教材镜像构建成功", leak.returncode == 0, (leak.stderr or leak.stdout).strip()[-60:])
leak_history = c.out("history", "--no-trunc", "--format", "{{.CreatedBy}}", LEAK_IMG)
c.contains("ARG 的值被写进镜像历史（可被任何人读出）", leak_history, SECRET)
c.contains("ENV 的值同样暴露在镜像配置里", leak_history, "token-written-into-image")

leak_env = c.out("inspect", "-f", "{{json .Config.Env}}", LEAK_IMG)
c.contains("ENV 出现在运行配置里", leak_env, "token-written-into-image")
leak_run = c.run("run", "--rm", LEAK_IMG, "cat", "/tmp/build.log")
c.contains("ARG 的值还留在镜像文件系统里", leak_run.stdout, SECRET)

clean = build(CLEAN_IMG, "Dockerfile.clean",
              "--secret", f"id=db_password,src={HERE / 'secrets' / 'db_password.txt'}")
c.ok("用 --secret 挂载密钥后构建成功", clean.returncode == 0, (clean.stderr or clean.stdout).strip()[-60:])
clean_history = c.out("history", "--no-trunc", "--format", "{{.CreatedBy}}", CLEAN_IMG)
c.ok("secret 不进入镜像历史", SECRET not in clean_history, "历史中无明文")
c.ok("secret 不落进镜像层", SECRET not in c.out("run", "--rm", CLEAN_IMG,
                                                 "sh", "-c", "cat /app/alpine-release; ls /run/secrets 2>/dev/null || true"),
     "层内无明文")
clean_env = c.out("inspect", "-f", "{{json .Config.Env}}", CLEAN_IMG)
c.ok("secret 不出现在镜像环境变量里", SECRET not in clean_env, clean_env[:40])

c.equal("镜像记录了目标平台（供应链可追溯）",
        c.out("inspect", "-f", "{{.Os}}/{{.Architecture}}", CLEAN_IMG), "linux/amd64")

buildx = c.run("buildx", "version")
c.ok("BuildKit / buildx 可用（secret 挂载与 attestation 的前提）", buildx.returncode == 0,
     (buildx.stdout or buildx.stderr).strip().splitlines()[0][:50])

ctx_img = f"{c.prefix}-ctx:v1"
ctx_build = build(ctx_img, "Dockerfile.ctx")
c.ok("上下文镜像构建成功", ctx_build.returncode == 0, (ctx_build.stderr or ctx_build.stdout).strip()[-50:])
c.ok(".dockerignore 把 secrets/ 挡在构建上下文之外",
     SECRET not in c.run("run", "--rm", ctx_img, "sh", "-c",
                         "cat /ctx/secrets/db_password.txt 2>/dev/null || echo BLOCKED").stdout,
     "密钥未进入镜像")
c.ok("其余构建文件仍正常进入上下文",
     c.run("run", "--rm", ctx_img, "test", "-f", "/ctx/Dockerfile.ctx").returncode == 0, "")

raise SystemExit(c.finish())
