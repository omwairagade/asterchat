"""Minimal production server for Aster's static site.

The only application endpoint is /healthz. All other GET requests serve committed
static files. There is intentionally no chat or model-provider API in this release.
"""

from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PUBLIC_DIR = Path(__file__).resolve().parent / "public"


class AsterHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/healthz":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if urlsplit(self.path).path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        super().do_HEAD()

    def log_message(self, format: str, *args) -> None:
        # Keep routine requests compact in container logs.
        print(f"{self.client_address[0]} - {format % args}", flush=True)


def main() -> None:
    port = int(os.environ.get("PORT", "3000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AsterHandler)
    print(f"Aster static server listening on 0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
