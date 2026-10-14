"""Minimal same-origin HTTP host for the canonical vNext Runtime service."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from api.feedback_runtime import LearnerFeedbackRuntime
from api.migrations import apply_runtime_migrations
from api.sqlite_d1 import SqliteD1Database

_LOGGER = logging.getLogger("bailian_runtime")
_MAX_REQUEST_BYTES = 4_000_000
_LEARNING_MAP_PATH = "/api/learning-map"
_LEARNER_ROUTE = re.compile(
    r"^/api/learners/[^/]+/environments/[^/]+/packs/[^/]+/"
    r"(?:surface|observations)$"
)
_SDK_SOURCE_SHA = "851698a7a79d7a6942692e97f8a54f025d09a9c2"


def _json_error(status: int, error: str) -> tuple[int, bytes, dict[str, str]]:
    body = json.dumps({"error": error}, separators=(",", ":")).encode("utf-8")
    return status, body, {"content-type": "application/json; charset=utf-8"}


def _learner_route_allowed(method: str, path: str) -> bool:
    """Keep the browser boundary to Surface reads and raw-observation writes."""
    if path == "/api/ready":
        return method == "GET"
    if path == _LEARNING_MAP_PATH:
        return method == "GET"
    if _LEARNER_ROUTE.fullmatch(path) is None:
        return False
    if path.endswith("/surface"):
        return method in {"POST", "OPTIONS"}
    return method in {"POST", "OPTIONS"}


def _runtime_service(database: SqliteD1Database):
    """Load the pinned SDK Worker glue after Docker places it on PYTHONPATH."""
    from apps.runtime_vnext.worker.runtime_http import (
        RuntimeDeploymentIdentity,
        compose_vnext_runtime_service,
    )

    origin = os.environ["BAILIAN_ORIGIN"].strip()
    service = compose_vnext_runtime_service(
        database,
        deployment_identity=RuntimeDeploymentIdentity(
            service_name="learning-kernel-runtime-vnext",
            environment="selfhosted",
            service_version="0.1.0",
            source_sha=_SDK_SOURCE_SHA,
            source_sha_status="reported",
        ),
        surface_cors_origin=origin,
        allow_home_projection=False,
    )
    return LearnerFeedbackRuntime(service, database)


class _RuntimeRequestHandler(BaseHTTPRequestHandler):
    server_version = "LearningKernelRuntime"
    sys_version = ""

    def log_message(self, _format: str, *_args: object) -> None:
        # Request paths include learner and Pack identifiers; keep them out of logs.
        return

    def do_GET(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_OPTIONS(self) -> None:
        self._dispatch()

    def _dispatch(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/internal/healthz":
            self._send(200, b"ok\n", {"content-type": "text/plain; charset=utf-8"})
            return
        if parsed.path == "/internal/readyz":
            try:
                response = asyncio.run(
                    self.server.runtime_service.handle_request(  # type: ignore[attr-defined]
                        method="GET",
                        path="/api/ready",
                    )
                )
            except Exception:
                _LOGGER.exception("Runtime readiness check failed")
                self._send(*_json_error(503, "runtime_unavailable"))
                return
            self._send(response.status, response.body, response.headers)
            return
        if not _learner_route_allowed(self.command, parsed.path):
            self._send(*_json_error(404, "not_found"))
            return

        expected_secret = self.server.binding_secret  # type: ignore[attr-defined]
        supplied_secret = self.headers.get("x-lk-bailian-service-secret")
        from apps.runtime_vnext.worker.runtime_http import (
            is_valid_service_binding_secret,
        )

        if not is_valid_service_binding_secret(expected_secret, supplied_secret):
            self._send(*_json_error(404, "not_found"))
            return

        if parsed.path == _LEARNING_MAP_PATH:
            try:
                from api.learning_map import learning_map_payload

                payload = json.dumps(
                    learning_map_payload(),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            except Exception:
                _LOGGER.exception("Learning Map read failed")
                self._send(*_json_error(503, "learning_map_unavailable"))
                return
            self._send(
                200,
                payload,
                {"content-type": "application/json; charset=utf-8"},
            )
            return

        body: bytes | None = None
        if self.command in {"POST", "PUT", "PATCH"}:
            raw_length = self.headers.get("content-length", "0")
            try:
                body_length = int(raw_length)
            except ValueError:
                self._send(*_json_error(400, "invalid_content_length"))
                return
            if body_length < 0 or body_length > _MAX_REQUEST_BYTES:
                self._send(*_json_error(413, "request_too_large"))
                return
            body = self.rfile.read(body_length) if body_length else None

        try:
            response = asyncio.run(
                self.server.runtime_service.handle_request(  # type: ignore[attr-defined]
                    method=self.command,
                    path=parsed.path,
                    body=body,
                    authorization=self.headers.get("authorization"),
                    origin=self.headers.get("origin"),
                )
            )
        except Exception:
            _LOGGER.exception("Runtime request failed")
            self._send(*_json_error(500, "runtime_unavailable"))
            return
        self._send(response.status, response.body, response.headers)

    def _send(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.send_response(status)
        sent_content_type = False
        for name, value in headers.items():
            lower_name = name.lower()
            if lower_name in {"content-length", "connection", "transfer-encoding"}:
                continue
            if lower_name == "content-type":
                sent_content_type = True
            self.send_header(name, value)
        if not sent_content_type:
            self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)


def create_server(
    *,
    host: str,
    port: int,
    runtime_service: object,
    binding_secret: str,
) -> HTTPServer:
    server = HTTPServer((host, port), _RuntimeRequestHandler)
    server.runtime_service = runtime_service  # type: ignore[attr-defined]
    server.binding_secret = binding_secret  # type: ignore[attr-defined]
    return server


def main() -> None:
    sdk_root = Path(os.environ.get("LK_SDK_ROOT", "/opt/lk"))
    if str(sdk_root) not in sys.path:
        sys.path.insert(0, str(sdk_root))

    binding_secret = os.environ["BAILIAN_SERVICE_BINDING_SECRET"]
    from apps.runtime_vnext.worker.runtime_http import is_valid_service_binding_secret

    if not is_valid_service_binding_secret(binding_secret, binding_secret):
        raise ValueError(
            "BAILIAN_SERVICE_BINDING_SECRET must contain at least 32 bytes."
        )

    database_path = Path(
        os.environ.get("LK_DATABASE_PATH", "/data/learning-kernel.sqlite3")
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database = SqliteD1Database.open(database_path)
    migrations = Path(
        os.environ.get(
            "LK_RUNTIME_MIGRATIONS_DIR",
            "/opt/lk/apps/runtime_vnext/migrations",
        )
    )
    try:
        service = _runtime_service(database)
        revision = apply_runtime_migrations(database.connection, migrations)
        _LOGGER.info("SQLite Runtime schema ready at revision %s", revision)
        host = os.environ.get("LK_RUNTIME_HOST", "0.0.0.0")
        port = int(os.environ.get("LK_RUNTIME_PORT", "8000"))
        server = create_server(
            host=host,
            port=port,
            runtime_service=service,
            binding_secret=binding_secret,
        )
        _LOGGER.info("Self-hosted Runtime listening on internal port %s", port)
        try:
            server.serve_forever()
        finally:
            server.server_close()
    finally:
        database.connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    main()
