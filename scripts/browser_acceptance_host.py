"""Run the real Bailian browser UI against the canonical Runtime in a temp SQLite DB.

This local-only host avoids Docker and never opens or reuses ``data/*.sqlite3``.
It serves the checked-in web files and forwards the learner HTTP routes to the
same SDK Runtime/Feedback adapters used by the self-hosted application.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import os
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from api.feedback_runtime import LearnerFeedbackRuntime
from api.learning_map import learning_map_payload
from api.seed_u1 import seed
from api.sqlite_d1 import SqliteD1Database
from apps.runtime_vnext.worker.runtime_http import compose_vnext_runtime_service


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = (ROOT / "web").resolve()
LEARNER_ID = "local-learner-001"
ENVIRONMENT_ID = "home"


class _AcceptanceHandler(BaseHTTPRequestHandler):
    server_version = "BailianLocalAcceptance"
    sys_version = ""

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/api/learning-map":
            self._send(
                200,
                json.dumps(learning_map_payload(), ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        if parsed.path.startswith("/api/"):
            self._forward(method="GET", path=parsed.path, body=None)
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        raw_length = self.headers.get("content-length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self._send(400, b'{"error":"invalid_content_length"}', "application/json")
            return
        if length < 0 or length > 4_000_000:
            self._send(413, b'{"error":"request_too_large"}', "application/json")
            return
        body = self.rfile.read(length) if length else None
        self._forward(method="POST", path=parsed.path, body=body)

    def do_OPTIONS(self) -> None:
        parsed = urlsplit(self.path)
        self._forward(method="OPTIONS", path=parsed.path, body=None)

    def _forward(self, *, method: str, path: str, body: bytes | None) -> None:
        try:
            response = asyncio.run(
                self.server.runtime_service.handle_request(  # type: ignore[attr-defined]
                    method=method,
                    path=path,
                    body=body,
                    origin=self.headers.get("origin"),
                )
            )
            content_type = response.headers.get(
                "content-type", "application/json; charset=utf-8"
            )
            self._send(response.status, response.body, content_type)
        except Exception:
            self._send(503, b'{"error":"runtime_unavailable"}', "application/json")

    def _serve_static(self, request_path: str) -> None:
        relative = unquote(request_path).lstrip("/") or "index.html"
        candidate = (WEB_ROOT / relative).resolve()
        if not candidate.is_relative_to(WEB_ROOT) or not candidate.is_file():
            self._send(404, b"not found\n", "text/plain; charset=utf-8")
            return
        self._send(
            200,
            candidate.read_bytes(),
            mimetypes.guess_type(candidate.name)[0] or "application/octet-stream",
        )

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)


def main() -> None:
    database_temporary = tempfile.TemporaryDirectory(prefix="lk-u1-browser-")
    database_path = Path(database_temporary.name) / "acceptance.sqlite3"
    server = HTTPServer(("127.0.0.1", 0), _AcceptanceHandler)
    port = server.server_address[1]
    origin = f"http://127.0.0.1:{port}"
    sdk_root = Path(os.environ.get("LK_SDK_ROOT", "/opt/lk"))
    migrations = Path(
        os.environ.get(
            "LK_RUNTIME_MIGRATIONS_DIR",
            sdk_root / "apps" / "runtime_vnext" / "migrations",
        )
    )
    os.environ["LK_RUNTIME_MIGRATIONS_DIR"] = str(migrations)
    database = None
    try:
        asyncio.run(seed(database_path, LEARNER_ID, ENVIRONMENT_ID))
        database = SqliteD1Database.open(database_path)
        runtime_service = compose_vnext_runtime_service(
            database,
            surface_cors_origin=origin,
            allow_home_projection=False,
        )
        server.runtime_service = LearnerFeedbackRuntime(runtime_service, database)  # type: ignore[attr-defined]
        print(f"BROWSER_URL={origin}", flush=True)
        server.serve_forever(poll_interval=0.25)
    finally:
        server.server_close()
        if database is not None:
            database.connection.close()
        database_temporary.cleanup()


if __name__ == "__main__":
    main()
