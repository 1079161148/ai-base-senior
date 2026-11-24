"""第 31 章 · 日志与指标：日志驱动与轮转、logs 过滤、stats、events、监控栈配置校验。"""

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(31)

HERE = Path(__file__).parent
MONITOR_DIR = HERE / "monitoring"

c.equal("本机默认日志驱动是 json-file", c.out("info", "--format", "{{.LoggingDriver}}"), "json-file")

logger = c.name("logger")
c.run("run", "-d", "--name", logger, "alpine:3.20",
      "sh", "-c", "echo to-stdout; echo to-stderr 1>&2; sleep 5")
time.sleep(2)

log_path = c.out("inspect", "-f", "{{.LogPath}}", logger)
c.ok("json-file 驱动会在宿主上落一个日志文件",
     log_path.endswith("-json.log"), log_path[-40:])

c.contains("docker logs 能看到 stdout", c.run("logs", logger).stdout, "to-stdout")
c.contains("docker logs 合并了 stderr（内容不丢）",
           c.run("logs", logger).stdout + c.run("logs", logger).stderr, "to-stderr")

tail_one = c.run("logs", "--tail", "1", logger)
c.equal("--tail 只取最后一行", len((tail_one.stdout + tail_one.stderr).splitlines()), 1)

stamped = c.out("logs", "--timestamps", logger)
c.ok("--timestamps 给每行加 RFC3339 时间戳",
     stamped.split(" ")[0].startswith(datetime.now().strftime("%Y-%m-%dT")), stamped[:30])

since = (datetime.now() - timedelta(minutes=10)).isoformat()
since_logs = c.run("logs", "--since", since, logger)
c.contains("--since 按时间过滤历史日志", since_logs.stdout + since_logs.stderr, "to-stdout")

none_driver = c.name("nolog")
c.run("run", "-d", "--name", none_driver, "--log-driver", "none", "alpine:3.20", "sleep", "30")
none_logs = c.run("logs", none_driver)
c.ok("--log-driver none 之后无法读取日志",
     none_logs.returncode != 0 and "does not support reading" in (none_logs.stderr + none_logs.stdout),
     (none_logs.stderr + none_logs.stdout).strip().splitlines()[-1][:70])

rotating = c.name("rotating")
c.run("run", "-d", "--name", rotating,
      "--log-opt", "max-size=1m", "--log-opt", "max-file=2",
      "alpine:3.20", "sh", "-c", "echo rotate; sleep 30")
log_config = c.out("inspect", "-f", "{{json .HostConfig.LogConfig}}", rotating)
c.ok("日志轮转通过 log-opt 配置", "max-size" in log_config and "max-file" in log_config,
     log_config[:90])
c.equal("轮转参数被 docker 记录",
        json.loads(log_config)["Config"].get("max-file"), "2")

burster = c.name("burster")
c.run("run", "-d", "--name", burster, "--log-opt", "max-size=1m", "--log-opt", "max-file=1",
      "alpine:3.20", "sh", "-c", "yes 'burst line for rotation test' | head -c 5000000; sleep 30")
time.sleep(3)
burst_path = c.out("inspect", "-f", "{{.LogPath}}", burster)
c.ok("大量输出时日志文件仍按 max-size 滚动（路径存在即可读）",
     burst_path != "" and c.run("logs", "--tail", "1", burster).returncode == 0, burst_path[-40:])

c.run("run", "-d", "--name", c.name("worker"), "--memory", "64m", "--cpus", "0.5",
      "alpine:3.20", "sh", "-c", "while true; do :; done")
time.sleep(3)
stats = c.run("stats", "--no-stream", "--format", "{{json .}}").stdout.strip().splitlines()
rows = [json.loads(line) for line in stats if line.strip()]
c.ok("docker stats --format json 可被程序消费", len(rows) >= 1 and "CPUPerc" in rows[0],
     f"{len(rows)} 行")
worker_row = next((row for row in rows if row["Name"] == c.name("worker")), None)
c.ok("stats 反映真实 CPU 占用", worker_row is not None and worker_row["CPUPerc"] != "0.00%",
     worker_row["CPUPerc"] if worker_row else "missing")
c.contains("stats 显示内存上限（--memory 64m）",
           worker_row["MemUsage"] if worker_row else "", "64MiB")

start = time.time()
event_since = (datetime.now() - timedelta(seconds=5)).isoformat()
c.run("run", "--name", c.name("event"), "alpine:3.20", "true")
time.sleep(1)
event_until = (datetime.now() + timedelta(seconds=1)).isoformat()
events = c.run("events", "--filter", f"container={c.name('event')}",
               "--since", event_since, "--until", event_until,
               "--format", "{{json .}}").stdout
c.contains("docker events 能取到容器 start 事件", events, '"Action":"start"')
c.contains("能取到容器 die 事件", events, '"Action":"die"')

monitor_config = c.run("compose", "-f", str(MONITOR_DIR / "compose.yaml"), "-p", "ch31-monitor",
                       "config")
c.ok("监控栈 compose 配置校验通过", monitor_config.returncode == 0,
     monitor_config.stderr.strip()[:70])
render = monitor_config.stdout
scrape = (MONITOR_DIR / "prometheus.yml").read_text(encoding="utf-8")
c.ok("监控栈声明了 cadvisor / prometheus / grafana 三个服务",
     all(name in render for name in ("cadvisor", "prometheus", "grafana")), "")
c.contains("Prometheus 抓取目标指向 cadvisor:8080", scrape, "cadvisor:8080")

raise SystemExit(c.finish())
