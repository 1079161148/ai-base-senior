"""Agent 编排层（零依赖演示）：读提示词、发现工具、检查依赖、返回结构化回答。

真实项目换成 LangGraph / LlamaIndex / 自研编排均可，容器侧只关心：
  1. 依赖通过服务名访问（db / cache / tools）
  2. 提示词与配置从外部挂载进来
  3. 暴露 /healthz 供编排器判断就绪
"""

import json
import os
import socket
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
REDIS_HOST = os.environ.get("REDIS_HOST", "cache")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
TOOLS_URL = os.environ.get("TOOLS_URL", "http://tools:8001")
PROMPT_DIR = os.environ.get("PROMPT_DIR", "/prompts")


def tcp_ok(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def load_prompt() -> str:
    with open(os.path.join(PROMPT_DIR, "system.md"), encoding="utf-8") as handle:
        return handle.read()


def fetch_tools() -> list[dict]:
    with urllib.request.urlopen(f"{TOOLS_URL}/tools", timeout=3) as response:
        return json.loads(response.read())["tools"]


def redis_get(key: str) -> str | None:
    payload = f"*2\r\n$3\r\nGET\r\n${len(key)}\r\n{key}\r\n".encode()
    try:
        with socket.create_connection((REDIS_HOST, REDIS_PORT), timeout=2) as sock:
            sock.sendall(payload)
            data = sock.recv(4096)
    except OSError:
        return None
    if data.startswith(b"$-1"):
        return None
    if not data.startswith(b"$"):
        return None
    return data.split(b"\r\n", 1)[1].rstrip(b"\r\n").decode()


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._json(200, {
                "status": "ok",
                "db": "up" if tcp_ok(DB_HOST, DB_PORT) else "down",
                "redis": "up" if tcp_ok(REDIS_HOST, REDIS_PORT) else "down",
            })
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/chat":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        question = json.loads(self.rfile.read(length) or b"{}").get("question", "")
        try:
            tools = fetch_tools()
            prompt = load_prompt()
        except (OSError, ValueError) as exc:
            self._json(503, {"error": f"dependency unavailable: {exc}"})
            return
        cached = redis_get(f"answer:{question}") or ""
        self._json(200, {
            "question": question,
            "answer": f"[stub] {question} 已检索 {len(tools)} 个工具，命中缓存：{bool(cached)}",
            "tools": [tool["name"] for tool in tools],
            "prompt_chars": len(prompt),
        })

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
