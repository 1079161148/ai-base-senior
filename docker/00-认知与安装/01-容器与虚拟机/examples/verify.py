"""第 01 章 · 容器与虚拟机：隔离三件套实证。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(1)

driver = c.out("info", "--format", "{{.Driver}}")
c.ok("存储驱动是联合文件系统", driver in ("overlayfs", "overlay2"), driver)

kernel = c.out("run", "--rm", "alpine:3.20", "uname", "-r")
c.ok("容器内可见 Linux 内核（共用内核）", bool(kernel), kernel)

hostname = c.out("run", "--rm", "alpine:3.20", "hostname")
c.ok("hostname 被隔离", len(hostname) >= 12, hostname)

pid1 = c.out("run", "--rm", "alpine:3.20", "cat", "/proc/1/comm")
c.ok("PID 1 是容器主进程而非 systemd", pid1 not in ("systemd", "init"), pid1)

ns = c.out("run", "--rm", "alpine:3.20", "ls", "/proc/1/ns")
for name in ("pid", "net", "mnt", "uts"):
    c.ok(f"{name} namespace 存在", name in ns, ns.replace("\n", " "))

count = int(c.out("run", "--rm", "alpine:3.20", "sh", "-c", "ps -e | wc -l").strip())
c.ok("进程视图被隔离", count < 10, f"容器内进程行数={count}")

memory_script = (
    "cat /sys/fs/cgroup/memory.max 2>/dev/null "
    "|| cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null"
)
limit = c.out("run", "--rm", "--memory", "64m", "alpine:3.20", "sh", "-c", memory_script).strip()
c.equal("内存限制生效", limit, "67108864")

cpu_name = c.name("cpu")
c.run("run", "-d", "--name", cpu_name, "--cpus", "0.5", "alpine:3.20", "sleep", "30")
nanocpus = c.out("inspect", "-f", "{{.HostConfig.NanoCpus}}", cpu_name)
c.equal("CPU 限制生效", nanocpus, "500000000")

isolated = c.out(
    "run", "--rm", "--network", "none", "alpine:3.20", "sh", "-c", "ip addr show | grep -c '^[0-9]'"
).strip()
c.ok("none 网络只保留 loopback", isolated == "1", f"网卡数={isolated}")

raise SystemExit(c.finish())
