"""第 15 章 · 网络模型与默认网络：bridge / host / none。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(15)

networks = c.out("network", "ls", "--format", "{{.Name}}")
for name in ("bridge", "host", "none"):
    c.ok(f"默认网络 {name} 存在", name in networks, networks.replace("\n", " ")[:60])

gateway = c.json("network", "inspect", "bridge")[0]["IPAM"]["Config"][0]["Gateway"]
c.ok("bridge 网关在 172.17 网段", gateway.startswith("172.17."), gateway)

a = c.name("a")
c.run("run", "-d", "--name", a, "alpine:3.20", "sleep", "120")
ip_a = c.container_ip(a)
c.ok("bridge 容器获得 172.17 地址", ip_a.startswith("172.17."), ip_a)

outbound = c.run("exec", a, "ping", "-c", "1", "-W", "3", "223.5.5.5")
c.ok("容器可通过 NAT 出网", outbound.returncode == 0,
     (outbound.stdout + outbound.stderr).strip().splitlines()[-1][:60] if (outbound.stdout + outbound.stderr).strip() else "")

b = c.name("b")
c.run("run", "-d", "--name", b, "alpine:3.20", "sleep", "120")
by_name = c.run("exec", a, "ping", "-c", "1", "-W", "2", b)
c.ok("默认 bridge 不能用容器名互访", by_name.returncode != 0,
     (by_name.stdout + by_name.stderr).strip().splitlines()[-1][:60] if (by_name.stdout + by_name.stderr).strip() else "")

ip_b = c.container_ip(b)
by_ip = c.run("exec", a, "ping", "-c", "1", "-W", "3", ip_b)
c.ok("同网段可用 IP 互通", by_ip.returncode == 0,
     (by_ip.stdout + by_ip.stderr).strip().splitlines()[-1][:60] if (by_ip.stdout + by_ip.stderr).strip() else "")

none_c = c.name("none")
c.run("run", "-d", "--name", none_c, "--network", "none", "alpine:3.20", "sleep", "120")
links = c.out("exec", none_c, "sh", "-c", "ip -o link show | wc -l").strip()
c.equal("none 网络只剩 loopback", links, "1")

host_c = c.name("hostnet")
c.run("run", "-d", "--name", host_c, "--network", "host", "alpine:3.20", "sleep", "120")
host_links = c.out("exec", host_c, "ip", "-o", "link", "show")
c.ok("host 网络能看到宿主网桥 docker0", "docker0" in host_links,
     f"{len(host_links.splitlines())} 个接口")

mode = c.out("inspect", "-f", "{{.HostConfig.NetworkMode}}", host_c)
c.equal("host 网络模式正确", mode, "host")

raise SystemExit(c.finish())
