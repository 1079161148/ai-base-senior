"""第 09 章 · 日志、进入容器、文件复制与资源监控。"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(9)

web = c.name("web")
c.run("run", "-d", "--name", web, "-p", "127.0.0.1:18090:80", "nginx:1.27-alpine", timeout=300)
c.wait_http(18090)

logs = c.container_logs(web)
c.ok("logs 可读容器输出", len(logs.strip()) > 0, logs.strip().splitlines()[0][:60] if logs.strip() else "")

tail = c.out("logs", "--tail", "2", web)
c.ok("logs --tail 可限制行数", len(tail.splitlines()) <= 4, f"{len(tail.splitlines())} 行")

version = c.run("exec", web, "nginx", "-v")
c.ok("exec 在运行容器内执行命令", version.returncode == 0 and "nginx" in (version.stdout + version.stderr).lower(),
     (version.stdout + version.stderr).strip()[:50])

c.ok("exec 后容器仍运行", c.container_running(web))

host_file = Path(tempfile.gettempdir()) / f"{c.prefix}-hello.txt"
host_file.write_text("hello-cp", encoding="utf-8")
c.run("cp", str(host_file), f"{web}:/usr/share/nginx/html/hello.txt")
c.equal("cp 从宿主复制到容器", c.http_get(18090, "/hello.txt").strip(), "hello-cp")

back_file = Path(tempfile.gettempdir()) / f"{c.prefix}-nginx.conf"
c.run("cp", f"{web}:/etc/nginx/nginx.conf", str(back_file))
c.ok("cp 从容器复制回宿主", back_file.exists() and back_file.stat().st_size > 0,
     f"{back_file.stat().st_size} bytes")
host_file.unlink(missing_ok=True)
back_file.unlink(missing_ok=True)

stats = c.out("stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}}", web)
c.ok("stats 可读资源占用", web in stats, stats.replace("\n", " ")[:50])

top = c.out("top", web)
c.ok("top 可看容器内进程", "nginx" in top, top.splitlines()[0][:60] if top else "")

ip = c.container_ip(web)
c.ok("inspect 可取容器 IP", ip.startswith("172."), ip)

c.run("exec", web, "sh", "-c", "echo x > /tmp/newfile")
diff = c.out("diff", web)
c.ok("diff 可看可写层文件变更", "/tmp/newfile" in diff, diff[:80])

inspect_type = c.out("inspect", "-f", "{{.State.Status}}", web)
c.equal("inspect 取状态字段", inspect_type, "running")

raise SystemExit(c.finish())
