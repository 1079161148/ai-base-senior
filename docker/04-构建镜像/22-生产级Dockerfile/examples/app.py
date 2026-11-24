import http.server
import os
import signal
import sys

port = int(os.environ.get("PORT", "8000"))


def shutdown(signum, frame):
    print("graceful shutdown", flush=True)
    sys.exit(0)


signal.signal(signal.SIGTERM, shutdown)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, fmt, *args) -> None:
        return None


server = http.server.HTTPServer(("0.0.0.0", port), Handler)
print(f"serving on 0.0.0.0:{port}", flush=True)
server.serve_forever()
