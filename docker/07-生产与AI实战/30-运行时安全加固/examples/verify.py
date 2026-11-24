"""第 30 章 · 运行时安全加固：capabilities、no-new-privileges、只读根、pids、非 root、seccomp。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(30)

IMG = "alpine:3.20"


def run_cmd(flags: list[str], cmd: list[str], timeout: int = 120):
    """docker run --rm <flags> <镜像> <命令>：flags 必须在镜像名之前。"""
    return c.run("run", "--rm", *flags, IMG, *cmd, timeout=timeout)


def last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1][:70] if lines else ""


def cap_eff(flags: list[str]) -> str:
    """读取容器内进程的有效能力位图（CapEff）。"""
    proc = run_cmd(flags, ["sh", "-c", "grep CapEff /proc/self/status"])
    parts = proc.stdout.split()
    return parts[1] if proc.returncode == 0 and len(parts) >= 2 else ""


default_caps = cap_eff([])
c.ok("默认容器只带一份裁剪过的能力集（不是全开）",
     default_caps not in ("", "0000000000000000", "000001ffffffffff"), default_caps)

mount_denied = run_cmd([], ["mount", "-t", "tmpfs", "none", "/mnt"])
c.ok("默认没有 CAP_SYS_ADMIN，容器内 mount 被拒", mount_denied.returncode != 0,
     last_line(mount_denied.stderr or mount_denied.stdout))

c.equal("--cap-drop ALL 后有效能力为 0", cap_eff(["--cap-drop", "ALL"]), "0000000000000000")
c.equal("--cap-add 精确授予单项能力（NET_BIND_SERVICE = 0x400）",
        cap_eff(["--cap-drop", "ALL", "--cap-add", "NET_BIND_SERVICE"]),
        "0000000000000400")

nnp = c.run("run", "-d", "--name", c.name("nnp"),
            "--security-opt", "no-new-privileges:true", IMG, "sleep", "30")
c.ok("no-new-privileges 容器可启动", nnp.returncode == 0, last_line(nnp.stderr))
c.contains("HostConfig 记录了 no-new-privileges",
           c.out("inspect", "-f", "{{json .HostConfig.SecurityOpt}}", c.name("nnp")),
           "no-new-privileges")

ro_write = run_cmd(["--read-only"], ["sh", "-c", "touch /blocked"])
c.ok("只读根文件系统下写 / 失败", ro_write.returncode != 0,
     last_line(ro_write.stderr or ro_write.stdout))

ro_tmpfs = run_cmd(["--read-only", "--tmpfs", "/tmp"],
                   ["sh", "-c", "touch /tmp/ok && echo WRITABLE"])
c.contains("--tmpfs 保留可写目录（只读根的标准搭配）", ro_tmpfs.stdout, "WRITABLE")

small_tmpfs = run_cmd(["--tmpfs", "/tmp:size=1m"],
                      ["sh", "-c", "dd if=/dev/zero of=/tmp/big bs=1024 count=2048 2>&1; echo DONE"])
c.ok("tmpfs 的 size 是硬限制，写超即失败",
     "No space left" in (small_tmpfs.stdout + small_tmpfs.stderr), last_line(small_tmpfs.stdout))

c.equal("--user 指定 UID 运行", run_cmd(["--user", "10001:10001"], ["id", "-u"]).stdout.strip(), "10001")

user_write = run_cmd(["--user", "10001:10001"], ["sh", "-c", "mkdir /forbidden"])
c.ok("非 root 无法在 root 拥有的根目录下建目录", user_write.returncode != 0,
     last_line(user_write.stderr or user_write.stdout))

pids = c.run("run", "-d", "--name", c.name("pids"), "--pids-limit", "32", IMG, "sleep", "60")
c.ok("--pids-limit 容器可启动", pids.returncode == 0, last_line(pids.stderr))
c.equal("HostConfig 记录 pids 上限",
        c.out("inspect", "-f", "{{.HostConfig.PidsLimit}}", c.name("pids")), "32")

fork = c.run("exec", c.name("pids"), "sh", "-c",
             "i=0; while [ $i -lt 100 ]; do sleep 30 & i=$((i+1)); done; echo spawned=$i", timeout=60)
c.ok("进程数达上限后 fork 失败",
     "Resource temporarily unavailable" in (fork.stdout + fork.stderr),
     last_line(fork.stdout + fork.stderr))

privileged_caps = cap_eff(["--privileged"])
c.ok("--privileged 等于交出全部能力（生产禁用）",
     privileged_caps.startswith("000001ffffffffff") or privileged_caps.startswith("0000003fffffffff"),
     privileged_caps)

seccomp = c.run("run", "-d", "--name", c.name("seccomp"),
                "--security-opt", "seccomp=unconfined", IMG, "sleep", "30")
c.ok("可以显式关闭 seccomp（不推荐）", seccomp.returncode == 0, last_line(seccomp.stderr))
c.contains("HostConfig 记录了 seccomp=unconfined",
           c.out("inspect", "-f", "{{json .HostConfig.SecurityOpt}}", c.name("seccomp")),
           "seccomp=unconfined")
c.contains("daemon 默认启用 seccomp（默认 profile 生效）",
           c.out("info", "--format", "{{json .SecurityOptions}}"), "seccomp")

raise SystemExit(c.finish())
