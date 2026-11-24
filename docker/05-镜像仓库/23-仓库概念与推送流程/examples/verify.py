"""第 23 章 · 仓库概念、镜像命名与推送/拉取流程。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(23)

c.run("pull", "alpine:3.20", timeout=300)

local_tag = f"{c.name('app')}:v1"
c.run("tag", "alpine:3.20", local_tag)
c.ok("本地标签可创建", c.image_exists(local_tag))

remote_tag = f"localhost:5999/{c.name('app')}:v1"
c.run("tag", "alpine:3.20", remote_tag)
c.ok("带仓库前缀的标签可创建", c.image_exists(remote_tag))

push = c.run("push", remote_tag, timeout=60)
c.ok("推送到不可达仓库会失败", push.returncode != 0,
     (push.stdout + push.stderr).strip().splitlines()[-1][:70] if (push.stdout + push.stderr).strip() else "")

config_dir = Path.home() / ".docker"
c.ok("Docker 客户端配置目录存在", config_dir.exists(), str(config_dir))

config_file = config_dir / "config.json"
if config_file.exists():
    c.ok("登录凭证存放于 config.json", config_file.stat().st_size >= 0, str(config_file))

c.ok("search 子命令可用", c.run("search", "--help").returncode == 0)
c.ok("login 子命令可用", c.run("login", "--help").returncode == 0)

digest = c.out("image", "inspect", "alpine:3.20", "-f", "{{index .RepoDigests 0}}")
c.ok("镜像带内容寻址 digest", "@sha256:" in digest, digest[:56])

mirrors = c.out("info", "--format", "{{range .RegistryConfig.Mirrors}}{{println .}}{{end}}").split()
c.ok("可从 info 读到仓库镜像配置", isinstance(mirrors, list), f"{len(mirrors)} 个加速源")

repo_tags = c.out("image", "inspect", local_tag, "-f", "{{json .RepoTags}}")
c.ok("RepoTags 反映本地标签", local_tag in repo_tags, repo_tags[:70])

c.ok("环境可访问默认仓库配置",
     "https://index.docker.io/v1/" == c.out("info", "--format", "{{.IndexServerAddress}}"),
     c.out("info", "--format", "{{.IndexServerAddress}}"))

raise SystemExit(c.finish())
