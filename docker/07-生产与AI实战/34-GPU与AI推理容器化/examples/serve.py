"""零依赖的"推理服务"骨架：只演示容器化工程面（模型挂载、缓存、健康检查、批处理）。

真正的模型加载与推理换成 transformers / vLLM 即可，容器侧配置完全一致。
"""

import hashlib
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_DIR = os.environ.get("MODEL_DIR", "/models")
CACHE_DIR = os.environ.get("CACHE_DIR", "/cache")
DIM = int(os.environ.get("EMBED_DIM", "8"))


def model_size() -> int:
    total = 0
    for name in os.listdir(MODEL_DIR):
        path = os.path.join(MODEL_DIR, name)
        if os.path.isfile(path):
            total += os.path.getsize(path)
    return total


def embed(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode()).digest()
    return [round(digest[i] / 255, 4) for i in range(DIM)]


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            try:
                size = model_size()
            except OSError as exc:
                self._json(503, {"status": "unhealthy", "error": str(exc)})
                return
            self._json(200, {"status": "ok", "model_bytes": size, "dim": DIM})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            text = str(payload.get("input", ""))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "invalid json"})
            return
        self._json(200, {"input": text, "embedding": embed(text)})

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)


def batch() -> int:
    """离线批处理模式：每行一条 JSON，输出到 stdout。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    count = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        text = json.loads(line).get("input", "")
        print(json.dumps({"input": text, "embedding": embed(text)}), flush=True)
        count += 1
    with open(os.path.join(CACHE_DIR, "last_batch.json"), "w", encoding="utf-8") as handle:
        json.dump({"count": count, "model_bytes": model_size()}, handle)
    return 0


if __name__ == "__main__":
    if "--batch" in sys.argv:
        raise SystemExit(batch())
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
