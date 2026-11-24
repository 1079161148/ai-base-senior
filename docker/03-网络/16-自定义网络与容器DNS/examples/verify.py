"""第 16 章 · 自定义网络：容器名解析、别名、隔离与连通。"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(16)

net = c.name("net")
c.run("network", "create", "--subnet", "172.28.0.0/16", net)
c.ok("自定义网络创建成功", c.network_exists(net))

subnet = c.json("network", "inspect", net)[0]["IPAM"]["Config"][0]["Subnet"]
c.equal("子网按指定创建", subnet, "172.28.0.0/16")

svc = c.name("svc")
c.run("run", "-d", "--name", svc, "--network", net, "--network-alias", "api", "alpine:3.20", "sleep", "180")

client = c.name("client")
c.run("run", "-d", "--name", client, "--network", net, "alpine:3.20", "sleep", "180")
time.sleep(2)

by_name = c.run("exec", client, "ping", "-c", "1", "-W", "3", svc)
c.ok("自定义网络可用容器名互访", by_name.returncode == 0,
     (by_name.stdout + by_name.stderr).strip().splitlines()[-1][:60])

by_alias = c.run("exec", client, "ping", "-c", "1", "-W", "3", "api")
c.ok("网络别名可被解析", by_alias.returncode == 0,
     (by_alias.stdout + by_alias.stderr).strip().splitlines()[-1][:60])

resolv = c.out("exec", client, "cat", "/etc/resolv.conf")
c.ok("内建 DNS 为 127.0.0.11", "127.0.0.11" in resolv, resolv.replace("\n", " ")[:60])

other_net = c.name("other")
c.run("network", "create", other_net)
outsider = c.name("outsider")
c.run("run", "-d", "--name", outsider, "--network", other_net, "alpine:3.20", "sleep", "180")
isolated = c.run("exec", outsider, "ping", "-c", "1", "-W", "2", svc)
c.ok("不同自定义网络默认隔离", isolated.returncode != 0,
     (isolated.stdout + isolated.stderr).strip().splitlines()[-1][:60])

c.run("network", "connect", net, outsider)
time.sleep(1)
connected = c.run("exec", outsider, "ping", "-c", "1", "-W", "3", svc)
c.ok("network connect 后可以互访", connected.returncode == 0,
     (connected.stdout + connected.stderr).strip().splitlines()[-1][:60])

c.run("network", "disconnect", net, outsider)
isolated_again = c.run("exec", outsider, "ping", "-c", "1", "-W", "2", svc)
c.ok("network disconnect 后恢复隔离", isolated_again.returncode != 0,
     (isolated_again.stdout + isolated_again.stderr).strip().splitlines()[-1][:60])

container_count = c.out("network", "inspect", "-f", "{{len .Containers}}", net)
c.equal("网络内容器数量可查", container_count, "2")

svc_ip = c.container_ip(svc, net)
c.ok("容器在自定义网络的 IP 落在指定子网", svc_ip.startswith("172.28."), svc_ip)

raise SystemExit(c.finish())
