"""MCP 风格的工具网关（零依赖演示）：Agent 通过 HTTP 发现与调用工具。

真实项目里这个角色由 MCP server（stdio/SSE）、FastAPI 工具服务或 Dify/n8n 插件承担。
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOLS = [
    {"name": "kb.search", "description": "按语义检索知识库", "params": ["query", "top_k"]},
    {"name": "kb.upsert", "description": "写入或更新知识条目", "params": ["content"]},
    {"name": "web.fetch", "description": "抓取网页正文", "params": ["url"]},
]

PORT = int(os.environ.get("PORT", "8001"))


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/tools":
            self._json(200, {"tools": TOOLS})
        elif self.path == "/healthz":
            self._json(200, {"status": "ok", "tools": len(TOOLS)})
        else:
            self._json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    print(f"tool gateway listening on {PORT}, {len(TOOLS)} tools", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
