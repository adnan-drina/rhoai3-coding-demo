#!/usr/bin/env python3
"""Coolstore catalog microservice stub (runtime-gate prerequisite).

The coolstore-cart specimen's CatalogService @FeignClient calls
GET ${CATALOG_ENDPOINT}/api/products (default http://localhost:8081). That
service does not exist in the specimen repo — any gate that needs a running
app (vendor Skill health check, runtime parity, …) needs this stub.

Lives in the **harness**, not the specimen (Architect E-20260807T155304Z):
committing a stub into coolstore-cart-legacy would make the specimen less
representative of a real customer gap.

Product payload matches coolstore-cart-legacy's ProductsObjectMother
createVehicleProducts() (ids 1111 / 2222).

Usage:
  python3 scripts/coolstore-catalog-stub.py          # :8081
  CATALOG_STUB_PORT=18081 python3 scripts/coolstore-catalog-stub.py
  # then: export CATALOG_ENDPOINT=http://localhost:8081
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ProductsObjectMother.createVehicleProducts() — coolstore-cart-legacy
PRODUCTS = [
    {"itemId": "1111", "name": "Car", "desc": "Super car", "price": 1000.0},
    {"itemId": "2222", "name": "Bike", "desc": "Super bike", "price": 200.0},
]

PRODUCTS_JSON = json.dumps(PRODUCTS).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        path = self.path.split("?", 1)[0]
        if path in ("/api/products", "/api/products/"):
            self._send(200, PRODUCTS_JSON, "application/json")
            return
        if path in ("/health", "/q/health", "/"):
            body = b'{"status":"UP","service":"coolstore-catalog-stub"}\n'
            self._send(200, body, "application/json")
            return
        self._send(404, b'{"error":"not found"}\n', "application/json")


def main() -> int:
    host = os.environ.get("CATALOG_STUB_HOST", "0.0.0.0")
    port = int(os.environ.get("CATALOG_STUB_PORT", "8081"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(
        f"coolstore-catalog-stub listening on http://{host}:{port} "
        f"(GET /api/products → {len(PRODUCTS)} ProductsObjectMother items)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
