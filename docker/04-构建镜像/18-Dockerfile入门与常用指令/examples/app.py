import http.server
import os
import sys

port = int(os.environ.get("PORT", "8000"))
if "--port" in sys.argv:
    port = int(sys.argv[sys.argv.index("--port") + 1])

os.chdir("/www")

server = http.server.HTTPServer(("0.0.0.0", port), http.server.SimpleHTTPRequestHandler)
print(f"serving on 0.0.0.0:{port}", flush=True)
server.serve_forever()
