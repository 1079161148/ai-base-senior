"""第 34 章 · GPU 与 AI 推理容器化：GPU 探测、模型挂载、缓存卷、批处理、显存/内存限制。"""

import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(34)

HERE = Path(__file__).parent
IMG = f"{c.prefix}-embed:v1"
MODEL_DIR = HERE / ".tmp-models"
CACHE_VOL = c.name("cache")
SVC = c.name("svc")
PORT = 18094

runtimes = json.loads(c.out("info", "--format", "{{json .Runtimes}}"))
c.ok("容器运行时可用（runc）", any("runc" in key for key in runtimes), str(list(runtimes))[:60])
c.ok("nvidia 运行时已注册（nvidia-container-toolkit 装的）",
     any("nvidia" in key for key in runtimes), str(list(runtimes)))
c.contains("CDI 规范目录已配置（GPU 设备的另一种接入方式）",
           c.out("info", "--format", "{{json .CDISpecDirs}}"), "/etc/cdi")

gpu = c.run("run", "-d", "--name", c.name("gpu"), "--gpus", "all", "alpine:3.20", "sleep", "20")
c.ok("--gpus all 参数被 daemon 接受", gpu.returncode == 0,
     (gpu.stderr or gpu.stdout).strip().splitlines()[-1][:60] if (gpu.stderr or gpu.stdout).strip() else "")
requests = json.loads(c.out("inspect", "-f", "{{json .HostConfig.DeviceRequests}}", c.name("gpu")))
c.ok("DeviceRequests 记录了 GPU 请求（Count=-1 表示全部）",
     bool(requests) and requests[0]["Count"] == -1 and requests[0]["Capabilities"] == [["gpu"]],
     json.dumps(requests)[:70])
no_device = c.run("exec", c.name("gpu"), "ls", "/dev/nvidia0")
c.ok("没有驱动/设备时容器内看不到 GPU（声明≠可用）", no_device.returncode != 0,
     (no_device.stderr or no_device.stdout).strip().splitlines()[-1][:50])
c.run("rm", "-f", c.name("gpu"))

compose_check = c.run("compose", "-f", str(HERE / "compose.yaml"), "-p", "ch34-infer", "config")
c.ok("compose 生产配置校验通过", compose_check.returncode == 0, compose_check.stderr.strip()[:60])
c.ok("compose 里模型是只读挂载、缓存是命名卷",
     "/models:ro" in compose_check.stdout or "target: /models" in compose_check.stdout, "")
gpu_compose = c.run("compose", "-f", str(HERE / "compose.gpu.yaml"), "-p", "ch34-gpu", "config")
c.ok("gpus: all 语法可被 compose 正确渲染",
     gpu_compose.returncode == 0 and "gpu" in gpu_compose.stdout.lower(), "")

build = c.run("build", "-t", IMG, str(HERE), timeout=600)
c.ok("推理服务镜像构建成功", build.returncode == 0, (build.stderr or build.stdout).strip()[-60:])
image_mb = int(c.out("image", "inspect", "-f", "{{.Size}}", IMG)) / 1024 / 1024
c.ok("镜像里不含模型权重（体积小）", image_mb < 200, f"{image_mb:.0f}MB")
c.equal("镜像内 /models 为空", c.out("run", "--rm", IMG, "sh", "-c", "ls -A /models | wc -l"), "0")

MODEL_DIR.mkdir(exist_ok=True)
weights = MODEL_DIR / "weights.bin"
with open(weights, "wb") as handle:
    handle.truncate(48 * 1024 * 1024)
c.equal("宿主侧模型文件 48MB", weights.stat().st_size, 48 * 1024 * 1024)

c.run("volume", "create", CACHE_VOL)
service = c.run("run", "-d", "--name", SVC, "-p", f"127.0.0.1:{PORT}:8000",
                "-v", f"{MODEL_DIR}:/models:ro", "-v", f"{CACHE_VOL}:/cache", IMG)
c.ok("服务容器启动", service.returncode == 0, (service.stderr or service.stdout).strip()[-50:])

started = time.time()
health = json.loads(c.wait_http(PORT, "/healthz", timeout=60))
c.equal("模型通过只读挂载进容器并可读", health["model_bytes"], 48 * 1024 * 1024)
c.ok("冷启动到就绪的耗时可测（用于容量规划）", time.time() - started < 60,
     f"{time.time() - started:.1f}s")

ro_write = c.run("exec", SVC, "sh", "-c", "touch /models/x")
c.ok("只读挂载不允许写模型目录", ro_write.returncode != 0,
     (ro_write.stderr or ro_write.stdout).strip().splitlines()[-1][:50])

request = urllib.request.Request(
    f"http://127.0.0.1:{PORT}/embed",
    data=json.dumps({"input": "docker 与 ai"}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=10) as response:
    embedding = json.loads(response.read())
c.equal("推理接口返回固定维度向量", len(embedding["embedding"]), 8)

batch_input = "\n".join(json.dumps({"input": text}) for text in ("a", "b", "c")) + "\n"
batch = c.run("run", "--rm", "-i", "-v", f"{MODEL_DIR}:/models:ro",
              "-v", f"{CACHE_VOL}:/cache", IMG, "python", "serve.py", "--batch",
              input_text=batch_input)
c.equal("批处理模式按行读入、按行输出", len(batch.stdout.strip().splitlines()), 3)

again = c.run("run", "--rm", "-v", f"{MODEL_DIR}:/models:ro", "-v", f"{CACHE_VOL}:/cache",
              IMG, "cat", "/cache/last_batch.json")
c.equal("命名卷让缓存跨容器复用", json.loads(again.stdout)["count"], 3)

oom = c.run("run", "-d", "--name", c.name("oom"), "--memory", "64m", "python:3.12-slim",
            "python", "-c", "b = bytearray(200 * 1024 * 1024)")
c.ok("内存受限容器启动", oom.returncode == 0, "")
c.wait_status(c.name("oom"), "exited", timeout=60)
c.equal("模型/数据超出内存上限会被 OOMKill",
        c.out("inspect", "-f", "{{.State.OOMKilled}}", c.name("oom")), "true")
c.equal("退出码为 137（SIGKILL）",
        c.out("inspect", "-f", "{{.State.ExitCode}}", c.name("oom")), "137")
c.equal("cgroup 内存上限写入 HostConfig",
        c.out("inspect", "-f", "{{.HostConfig.Memory}}", c.name("oom")), str(64 * 1024 * 1024))

c.run("rm", "-f", SVC, c.name("oom"))
shutil.rmtree(MODEL_DIR, ignore_errors=True)

raise SystemExit(c.finish())
