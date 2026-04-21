from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from bhargava_engine_hosted import calculate_panchanga


ROOT = Path(__file__).resolve().parent


class BhargavaHostedHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/panchanga":
            self._handle_panchanga(parsed.query)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def _handle_panchanga(self, query: str):
        params = parse_qs(query)
        try:
            date = params["date"][0]
            time_text = params.get("time", [None])[0]
            latitude = float(params["lat"][0])
            longitude = float(params["lon"][0])
            timezone_name = params.get("timezone", ["Asia/Kolkata"])[0]
            tz_offset = float(params["tz"][0]) if "tz" in params else None
            payload = calculate_panchanga(
                date,
                latitude,
                longitude,
                timezone_name=timezone_name,
                timezone_offset_hours=tz_offset,
                time_text=time_text,
            )
            body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=True).encode("utf-8")
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def main():
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), BhargavaHostedHandler)
    print(f"Bhargava Panchangam hosted app: http://{host}:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
