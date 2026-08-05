"""Static server and same-origin proxy for the Shield workspace API."""
from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HOST = "127.0.0.1"
PORT = 5500
BACKEND_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent
MAX_PROXY_BODY = 1_200_000


class ChatbotHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/api/_proxy-health":
            self._json_response(200, {"status": "ok", "version": 2})
            return
        if self.path.startswith("/api/"):
            self._proxy("GET")
        else:
            super().do_GET()

    def do_POST(self) -> None:
        self._proxy("POST")

    def do_PUT(self) -> None:
        self._proxy("PUT")

    def do_PATCH(self) -> None:
        self._proxy("PATCH")

    def do_DELETE(self) -> None:
        self._proxy("DELETE")

    def _proxy(self, method: str) -> None:
        if not self.path.startswith("/api/"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_PROXY_BODY:
            self._json_response(413, {"detail": "Request body is too large"})
            return
        body = self.rfile.read(length) if length else None
        api_path = self.path[4:]
        if api_path == "/chat":
            api_path = "/v1/gateway/chat"
            if body:
                incoming = json.loads(body)
                body = json.dumps(
                    {
                        "prompt": incoming.get("prompt", ""),
                        "context_chunks": [],
                        "metadata": {"client": "shield-web"},
                    }
                ).encode()
        else:
            api_path = f"/v1{api_path}"

        headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
        for name in ("Authorization", "X-Filename"):
            if self.headers.get(name):
                headers[name] = self.headers[name]
        request = Request(f"{BACKEND_URL}{api_path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=180) as response:
                response_body = response.read()
                self._raw_response(response.status, response_body, response.headers.get("Content-Type"))
        except HTTPError as exc:
            self._raw_response(exc.code, exc.read(), exc.headers.get("Content-Type"))
        except (URLError, TimeoutError):
            self._json_response(503, {"detail": "Security Gateway is unavailable"})
        except (ValueError, json.JSONDecodeError):
            self._json_response(400, {"detail": "Invalid request"})

    def _raw_response(self, status: int, body: bytes, content_type: str | None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type or "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._raw_response(status, body, "application/json; charset=utf-8")


if __name__ == "__main__":
    print(f"Shield AI đang chạy tại http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), ChatbotHandler).serve_forever()
