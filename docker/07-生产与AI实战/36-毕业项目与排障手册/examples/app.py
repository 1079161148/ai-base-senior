"""毕业项目的最小应用：暴露版本与健康检查，用来演练发布、重建、回滚。"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = os.environ.get("APP_VERSION", "unknown")


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/version":
            self._json(200, {"version": VERSION, "pid": os.getpid()})
        elif self.path == "/healthz":
            self._json(200, {"status": "ok", "version": VERSION})
        elif self.path == "/crash":
            raise SystemExit(3)
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
