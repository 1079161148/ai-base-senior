"""零依赖演示服务：用标准库访问 Redis 与 PostgreSQL 的 TCP 端口。

只用 socket 是为了说明一件事：容器间通信就是普通的 TCP，
服务名被 Docker 内置 DNS 解析成 IP，不依赖任何客户端库。
"""

import json
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB_HOST = os.environ.get("DB_HOST", "db")
DB_PORT = int(os.environ.get("DB_PORT", "5432"))
REDIS_HOST = os.environ.get("REDIS_HOST", "redis")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))


def tcp_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def redis_incr(key: str) -> int | None:
    """发一条最小 RESP 命令，解析 :<数字> 响应。"""
    payload = f"*2\r\n$4\r\nINCR\r\n${len(key)}\r\n{key}\r\n".encode()
    try:
        with socket.create_connection((REDIS_HOST, REDIS_PORT), timeout=2) as sock:
            sock.sendall(payload)
            data = sock.recv(64)
    except OSError:
        return None
    if not data.startswith(b":"):
        return None
    return int(data[1:].split(b"\r\n")[0])


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802  标准库要求的命名
        hits = redis_incr("hits")
        body = json.dumps({
            "path": self.path,
            "hits": hits,
            "db": "up" if tcp_reachable(DB_HOST, DB_PORT) else "down",
            "redis": "up" if hits is not None else "down",
        }).encode()
        self.send_response(200 if hits is not None else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
