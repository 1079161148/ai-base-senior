"""37 章共用的 Docker 验收工具：通过 docker CLI 做真实容器验收。

每章用 chNN- 前缀隔离自己创建的容器、镜像、网络、卷：
进入时先清理本章残留，结束时（含异常）自动清理，互不污染。
公共镜像（nginx、alpine 等）拉取后保留复用，不参与清理。
"""

from __future__ import annotations

import atexit
import json
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any

DOCKER = "docker"


class DockerError(RuntimeError):
    """docker 命令以非零状态退出。"""


def docker(
    *args: str,
    timeout: int = 300,
    input_text: str | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """执行 docker 命令，统一按 UTF-8 解码，避免 Windows 默认 GBK 乱码。"""
    proc = subprocess.run(
        [DOCKER, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        input=input_text,
    )
    if check and proc.returncode != 0:
        raise DockerError(f"docker {' '.join(args)} 失败：{proc.stderr.strip()}")
    return proc


def docker_out(*args: str, timeout: int = 300) -> str:
    """执行 docker 命令并返回 stdout，失败即抛异常。"""
    return docker(*args, timeout=timeout, check=True).stdout


class Checker:
    """章节级验收器：命名隔离 + 自动清理 + 计数输出。"""

    def __init__(self, chapter: int, cleanup: bool = True) -> None:
        self.chapter = chapter
        self.prefix = f"ch{chapter:02d}"
        self.passed = 0
        self.failed = 0
        self._cleanup_enabled = cleanup
        if cleanup:
            self.cleanup()
            atexit.register(self.cleanup)

    # ---------- 命名 ----------
    def name(self, suffix: str) -> str:
        """生成带章节前缀的资源名，保证不与其它章冲突。"""
        return f"{self.prefix}-{suffix}"

    # ---------- 执行 ----------
    def run(self, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return docker(*args, **kwargs)

    def out(self, *args: str) -> str:
        return docker_out(*args).strip()

    def json(self, *args: str) -> Any:
        return json.loads(docker_out(*args))

    # ---------- 查询 ----------
    def container_exists(self, name: str) -> bool:
        return self.run("inspect", name).returncode == 0

    def container_running(self, name: str) -> bool:
        proc = self.run("inspect", "-f", "{{.State.Running}}", name)
        return proc.returncode == 0 and proc.stdout.strip() == "true"

    def container_status(self, name: str) -> str:
        proc = self.run("inspect", "-f", "{{.State.Status}}", name)
        return proc.stdout.strip() if proc.returncode == 0 else "missing"

    def image_exists(self, ref: str) -> bool:
        return self.run("image", "inspect", ref).returncode == 0

    def network_exists(self, name: str) -> bool:
        return self.run("network", "inspect", name).returncode == 0

    def volume_exists(self, name: str) -> bool:
        return self.run("volume", "inspect", name).returncode == 0

    def container_ip(self, name: str, network: str | None = None) -> str:
        # Docker 29 起不再有顶层 NetworkSettings.IPAddress，需从 Networks 里取。
        if network:
            template = f'{{{{(index .NetworkSettings.Networks "{network}").IPAddress}}}}'
        else:
            template = "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"
        return self.out("inspect", "-f", template, name)

    def container_logs(self, name: str, tail: int = 50) -> str:
        return self.out("logs", "--tail", str(tail), name)

    # ---------- 网络访问 ----------
    def http_get(self, port: int, path: str = "/", timeout: float = 5.0,
                 headers: dict[str, str] | None = None) -> str:
        """请求宿主机映射端口，返回响应文本；连接失败抛异常。"""
        url = f"http://127.0.0.1:{port}{path}"
        request = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    def wait_http(self, port: int, path: str = "/", timeout: float = 40.0) -> str:
        """轮询直到端口可访问，超时抛异常。用于容器刚启动的场景。"""
        deadline = time.time() + timeout
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                return self.http_get(port, path, timeout=3.0)
            except (urllib.error.URLError, ConnectionError, OSError) as exc:
                last_error = exc
                time.sleep(0.5)
        raise DockerError(f"等待 127.0.0.1:{port} 超时：{last_error}")

    def wait_status(self, name: str, status: str, timeout: float = 60.0) -> bool:
        """轮询容器状态，返回是否在超时前达成。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.container_status(name) == status:
                return True
            time.sleep(0.3)
        return False

    # ---------- 断言 ----------
    def ok(self, label: str, condition: bool, detail: str = "") -> None:
        # detail 语义是"失败原因"，只在失败时打印，避免 PASS 行出现"未找到"之类的误导信息
        if condition:
            self.passed += 1
            print(f"[PASS] {label}")
        else:
            self.failed += 1
            print(f"[FAIL] {label}" + (f" -> {detail}" if detail else ""))

    def equal(self, label: str, actual: Any, expected: Any) -> None:
        self.ok(label, actual == expected, f"实际={actual!r} 期望={expected!r}")

    def contains(self, label: str, haystack: str, needle: str) -> None:
        self.ok(label, needle in haystack, f"未找到 {needle!r}")

    # ---------- 清理 ----------
    def cleanup(self) -> None:
        """删除本前缀的容器、网络、卷与自建镜像；公共镜像保留。"""
        if not self._cleanup_enabled:
            return
        containers = self.run(
            "ps", "-aq", "--filter", f"name=^{self.prefix}-"
        ).stdout.split()
        if containers:
            self.run("rm", "-f", *containers)

        networks = self.run(
            "network", "ls", "-q", "--filter", f"name=^{self.prefix}-"
        ).stdout.split()
        for network in networks:
            self.run("network", "rm", network)

        volumes = self.run(
            "volume", "ls", "-q", "--filter", f"name=^{self.prefix}-"
        ).stdout.split()
        for volume in volumes:
            self.run("volume", "rm", volume)

        # 必须按 repository 前缀精确删除，不能用镜像 ID：
        # 别名与原镜像共享 ID，rmi -f <ID> 会连带删掉公共镜像的所有 tag。
        images = self.run("images", "--format", "{{.Repository}}:{{.Tag}}").stdout.split()
        for image in images:
            repository = image.rsplit(":", 1)[0]
            if repository.startswith(f"{self.prefix}-") or repository.startswith(f"{self.prefix}/"):
                self.run("rmi", "-f", image)

    def finish(self) -> int:
        total = self.passed + self.failed
        print(f"\n结果：{self.passed}/{total} 通过")
        self.cleanup()
        return 1 if self.failed else 0
