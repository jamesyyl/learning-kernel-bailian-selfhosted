"""Learner-safe feedback and idempotent replay for the canonical Runtime host."""

from __future__ import annotations

import contextvars
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from api.sqlite_d1 import SqliteD1Database

_OBSERVATION_PATH = re.compile(
    r"^/api/learners/[^/]+/environments/[^/]+/packs/[^/]+/observations$"
)
_FEEDBACK = {
    "correct": ("success", "答對了！"),
    "incorrect": ("retry", "這次不對，再試一次！"),
    "indeterminate": ("neutral", "這次暫時無法判斷，學習紀錄已保存。"),
}
_REPLAY_TABLE = "bailian_observation_response_cache"


@dataclass(frozen=True, slots=True)
class CachedRuntimeResponse:
    status: int
    body: bytes
    headers: dict[str, str]


class LearnerFeedbackRuntime:
    """Decorate the one canonical evaluation result; never evaluate in this adapter."""

    def __init__(self, runtime_service: object, database: SqliteD1Database) -> None:
        self._runtime_service = runtime_service
        self._database = database
        self._evaluation_status: contextvars.ContextVar[str | None] = (
            contextvars.ContextVar(
                "bailian_trusted_evaluation_status",
                default=None,
            )
        )
        self._database.connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_REPLAY_TABLE} (
                request_digest TEXT PRIMARY KEY,
                response_status INTEGER NOT NULL CHECK (response_status = 202),
                response_body BLOB NOT NULL,
                response_headers_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._capture_canonical_evaluation()

    def _capture_canonical_evaluation(self) -> None:
        evaluator = getattr(self._runtime_service, "evaluate_raw_observation", None)
        if not callable(evaluator):
            raise TypeError("Pinned Runtime does not expose its server-only evaluator.")

        async def capture(*args: Any, **kwargs: Any) -> object:
            result = await evaluator(*args, **kwargs)
            answer_status = getattr(result, "answer_status", None)
            verdict = getattr(answer_status, "value", answer_status)
            if verdict not in _FEEDBACK:
                raise RuntimeError(
                    "Canonical evaluator returned an unsupported verdict."
                )
            self._evaluation_status.set(verdict)
            return result

        try:
            setattr(self._runtime_service, "evaluate_raw_observation", capture)
        except (AttributeError, TypeError) as error:
            raise TypeError(
                "Pinned Runtime evaluator cannot be safely observed."
            ) from error

    async def handle_request(
        self,
        *,
        method: str,
        path: str,
        body: str | bytes | None = None,
        authorization: str | None = None,
        origin: str | None = None,
    ) -> object:
        request_digest = _request_digest(
            method=method, path=path, body=body, origin=origin
        )
        if request_digest is not None:
            cached = await self._read_cached_response(request_digest)
            if cached is not None:
                return cached

        token = self._evaluation_status.set(None)
        try:
            response = await self._runtime_service.handle_request(
                method=method,
                path=path,
                body=body,
                authorization=authorization,
                origin=origin,
            )
            if request_digest is None or response.status != 202:
                return response

            verdict = self._evaluation_status.get()
            if verdict not in _FEEDBACK:
                return _json_response(
                    template=response,
                    status=503,
                    payload={"error": "trusted_evaluation_unavailable"},
                )
            try:
                payload = json.loads(response.body)
            except (TypeError, ValueError):
                return _json_response(
                    template=response,
                    status=503,
                    payload={"error": "trusted_evaluation_unavailable"},
                )
            directive = payload.get("directive") if isinstance(payload, dict) else None
            if directive not in {"advance", "complete"}:
                return _json_response(
                    template=response,
                    status=503,
                    payload={"error": "runtime_directive_unavailable"},
                )

            tone, message = _FEEDBACK[verdict]
            payload["feedback"] = {
                "tone": tone,
                "verdict": verdict,
                "action": "retry" if verdict == "incorrect" else directive,
                "message": message,
            }
            enriched = _json_response(template=response, status=202, payload=payload)
            await self._store_response(request_digest, enriched)
            return enriched
        finally:
            self._evaluation_status.reset(token)

    async def _read_cached_response(
        self, request_digest: str
    ) -> CachedRuntimeResponse | None:
        row = (
            await self._database.prepare(
                f"""
            SELECT response_status, response_body, response_headers_json
            FROM {_REPLAY_TABLE}
            WHERE request_digest = ?
            """
            )
            .bind(request_digest)
            .first()
        )
        if row is None:
            return None
        if not isinstance(row, dict):
            raise RuntimeError("SQLite returned an invalid feedback replay record.")
        status = row.get("response_status")
        body = row.get("response_body")
        headers_json = row.get("response_headers_json")
        if type(status) is not int or status != 202 or not isinstance(body, bytes):
            raise RuntimeError("SQLite feedback replay record failed validation.")
        if not isinstance(headers_json, str):
            raise RuntimeError("SQLite feedback replay headers are invalid.")
        try:
            headers = json.loads(headers_json)
        except ValueError as error:
            raise RuntimeError("SQLite feedback replay headers are corrupt.") from error
        if not isinstance(headers, dict) or any(
            not isinstance(name, str) or not isinstance(value, str)
            for name, value in headers.items()
        ):
            raise RuntimeError("SQLite feedback replay headers failed validation.")
        return CachedRuntimeResponse(status=status, body=body, headers=headers)

    async def _store_response(
        self,
        request_digest: str,
        response: CachedRuntimeResponse,
    ) -> None:
        headers_json = json.dumps(
            response.headers,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        await (
            self._database.prepare(
                f"""
            INSERT OR IGNORE INTO {_REPLAY_TABLE} (
                request_digest, response_status, response_body, response_headers_json
            ) VALUES (?, ?, ?, ?)
            """
            )
            .bind(request_digest, response.status, response.body, headers_json)
            .run()
        )
        cached = await self._read_cached_response(request_digest)
        if cached != response:
            raise RuntimeError(
                "SQLite feedback replay response conflicts with this request."
            )


def _request_digest(
    *,
    method: str,
    path: str,
    body: str | bytes | None,
    origin: str | None,
) -> str | None:
    if (
        method.upper() != "POST"
        or _OBSERVATION_PATH.fullmatch(path) is None
        or body is None
    ):
        return None
    body_bytes = body.encode("utf-8") if isinstance(body, str) else body
    digest = hashlib.sha256()
    for value in (method.upper(), path, origin or ""):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    digest.update(len(body_bytes).to_bytes(8, "big"))
    digest.update(body_bytes)
    return digest.hexdigest()


def _json_response(
    *, template: object, status: int, payload: dict[str, object]
) -> object:
    headers = dict(getattr(template, "headers", {}))
    headers["content-type"] = "application/json; charset=utf-8"
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return CachedRuntimeResponse(status=status, body=body, headers=headers)


__all__ = ["LearnerFeedbackRuntime"]
