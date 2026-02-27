#!/usr/bin/env python3
"""Простой прокси для API Яндекс.Маркета recommended-buildings.

Слушает локально (например, на 0.0.0.0:8001) и проксирует запросы вида:
  GET /ym_recommended_buildings?zoom=...&minLat=...&maxLat=...&minLon=...&maxLon=...

дальше на:
  https://hubs.market.yandex.ru/api/partner-gateway/outlet-map/recommended-buildings

и возвращает JSON, добавляя CORS-заголовки для фронта.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import sys

import requests

TARGET_BASE = "https://hubs.market.yandex.ru/api/partner-gateway/outlet-map/outlet-map/recommended-buildings".replace(
    "/outlet-map/outlet-map/", "/outlet-map/"
)


class ProxyHandler(BaseHTTPRequestHandler):
    def _set_headers(self, status: int = 200, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):  # noqa: N802
        self._set_headers(200)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/ym_recommended_buildings":
            self._set_headers(404)
            payload = {"error": "unknown path"}
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        qs = parse_qs(parsed.query)
        params = {}
        for key in ("zoom", "minLat", "maxLat", "minLon", "maxLon"):
            if key in qs and qs[key]:
                params[key] = qs[key][0]

        try:
            resp = requests.get(TARGET_BASE, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            self._set_headers(502)
            payload = {"error": "upstream failed", "detail": str(e)}
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        self._set_headers(200)
        self.wfile.write(resp.content)


def run(host: str = "0.0.0.0", port: int = 8001) -> None:
    server_address = (host, port)
    httpd = HTTPServer(server_address, ProxyHandler)
    print(f"[ym_proxy] Serving on {host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    host = "0.0.0.0"
    port = 8001
    if len(sys.argv) >= 2:
        port = int(sys.argv[1])
    run(host, port)
