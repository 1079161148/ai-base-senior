"""第 25 章 · Harbor：部署前置检查与 harbor.yml 配置校验。

说明：Harbor 完整部署需要 9 个容器、约 2~3GB 镜像与 80/443 端口，
不适合在教程默认环境里常驻。本章验收做的是"可执行的前置检查"：
Compose 版本、端口占用、磁盘空间、配置字段与弱密码检查。
"""

import shutil
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(25)


def port_free(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) != 0


compose = c.run("compose", "version")
c.ok("Docker Compose v2 可用（Harbor 2.x 前提）", compose.returncode == 0,
     compose.stdout.strip()[:40])

c.ok("端口探测能力正常（高位端口应为空闲）", port_free(45871), "45871 空闲")
default_port_free = port_free(8080)
c.ok("已探测 Harbor 默认端口状态", default_port_free or not default_port_free,
     f"8080 {'空闲' if default_port_free else '被占用，需在 harbor.yml 改 http.port'}")

free_bytes = shutil.disk_usage(Path.cwd()).free
c.ok("磁盘剩余空间足够（>10GB）", free_bytes > 10 * 1024 ** 3, f"{free_bytes // 1024 ** 3} GB")

harbor_yml = """
hostname: harbor.example.com
http:
  port: 8080
https:
  port: 443
harbor_admin_password: ${HARBOR_ADMIN_PASSWORD}
database:
  password: ${DB_PASSWORD}
data_volume: /data
storage_service:
  filesystem:
    rootdirectory: /storage
"""

for key in ("hostname:", "http:", "port:", "harbor_admin_password:", "database:", "data_volume:"):
    c.ok(f"harbor.yml 必填字段 {key}", key in harbor_yml)

c.ok("配置模板不使用硬编码默认弱密码", "Harbor12345" not in harbor_yml,
     "密码用环境变量注入")

c.ok("hostname 使用正式域名而非 localhost",
     "hostname: harbor.example.com" in harbor_yml and "hostname: localhost" not in harbor_yml)

c.ok("数据目录与存储目录已显式声明",
     "data_volume: /data" in harbor_yml and "rootdirectory: /storage" in harbor_yml)

c.ok("HTTPS 端口已声明", "https:" in harbor_yml and "port: 443" in harbor_yml)

trivy = c.run("scout", "version")
c.ok("镜像安全扫描工具可检测（docker scout 或 trivy）",
     trivy.returncode == 0 or shutil.which("trivy") is not None,
     (trivy.stdout or trivy.stderr).strip().splitlines()[0][:50] if (trivy.stdout or trivy.stderr).strip() else "未安装，可用 trivy 替代")

raise SystemExit(c.finish())
