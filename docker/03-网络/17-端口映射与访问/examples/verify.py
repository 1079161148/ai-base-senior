"""第 17 章 · 端口映射：-p / -P、回环绑定、冲突与宿主访问。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(17)

web = c.name("web")
c.run("run", "-d", "--name", web, "-p", "18100:80", "nginx:1.27-alpine", timeout=300)
body = c.wait_http(18100)
c.ok("端口映射后外部可访问", "Welcome to nginx" in body, body.strip()[:40])

port_info = c.out("port", web)
c.ok("docker port 显示映射关系", "18100" in port_info and "80/tcp" in port_info, port_info)

local = c.name("local")
c.run("run", "-d", "--name", local, "-p", "127.0.0.1:18101:80", "nginx:1.27-alpine", timeout=300)
c.wait_http(18101)
local_port = c.out("port", local)
c.ok("绑定 127.0.0.1 时不暴露到 0.0.0.0",
     "127.0.0.1:18101" in local_port and "0.0.0.0" not in local_port, local_port)

conflict = c.run("run", "-d", "--name", c.name("conflict"), "-p", "18100:80", "nginx:1.27-alpine")
c.ok("宿主端口冲突时报错", conflict.returncode != 0,
     (conflict.stderr or conflict.stdout).strip()[:80])

random_port = c.name("random")
c.run("run", "-d", "--name", random_port, "-P", "nginx:1.27-alpine", timeout=300)
allocated = c.out("port", random_port)
c.ok("-P 自动分配宿主端口", "80/tcp" in allocated and len(allocated.strip()) > 0, allocated)

multi = c.name("multi")
c.run("run", "-d", "--name", multi, "-p", "18102:80", "-p", "18103:443",
      "nginx:1.27-alpine", timeout=300)
all_ports = c.out("port", multi)
c.ok("多端口可同时映射", "18102" in all_ports and "18103" in all_ports,
     all_ports.replace("\n", " ")[:60])

dns = c.run("exec", web, "nslookup", "host.docker.internal")
c.ok("容器内可解析 host.docker.internal",
     dns.returncode == 0 and "Address" in dns.stdout, dns.stdout.strip().replace("\n", " ")[:70])

c.ok("映射信息在 inspect 中可查",
     "18100" in c.out("inspect", "-f", "{{json .NetworkSettings.Ports}}", web),
     c.out("inspect", "-f", "{{json .NetworkSettings.Ports}}", web)[:80])

raise SystemExit(c.finish())
