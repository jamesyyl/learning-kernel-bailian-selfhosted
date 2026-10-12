from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from api.feedback_runtime import LearnerFeedbackRuntime
from api.sqlite_d1 import SqliteD1Database


class _Response:
    def __init__(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.status = status
        self.body = body
        self.headers = headers


class _FakeRuntimeService:
    def __init__(
        self,
        *,
        answer_status: str = "correct",
        directive: str = "advance",
        evaluate_during_request: bool = True,
        status_code: int = 202,
    ) -> None:
        self.answer_status = answer_status
        self.directive = directive
        self.evaluate_during_request = evaluate_during_request
        self.status_code = status_code
        self.evaluation_calls = 0
        self.request_calls = 0

    async def evaluate_raw_observation(
        self,
        *,
        scope: object,
        pack_id: str,
        record_id: str,
    ) -> object:
        self.evaluation_calls += 1
        return SimpleNamespace(
            answer_status=SimpleNamespace(value=self.answer_status),
            source_record_id=record_id,
        )

    async def handle_request(
        self,
        *,
        method: str,
        path: str,
        body: str | bytes | None = None,
        authorization: str | None = None,
        origin: str | None = None,
    ) -> _Response:
        self.request_calls += 1
        if path.endswith("/observations") and self.evaluate_during_request:
            await self.evaluate_raw_observation(
                scope=None, pack_id="math-u1", record_id="record-1"
            )
        response_body = json.dumps(
            {
                "directive": self.directive,
                "feedback": {
                    "tone": "neutral",
                    "message": "已收到作答；學習紀錄已保存。",
                },
                "receipt": {"evaluated": self.evaluate_during_request},
            },
            separators=(",", ":"),
        ).encode("utf-8")
        return _Response(
            self.status_code,
            response_body,
            {
                "content-type": "application/json; charset=utf-8",
                "access-control-allow-origin": origin or "",
            },
        )


class LearnerFeedbackRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_verdict_and_action_are_mapped_from_the_canonical_result(
        self,
    ) -> None:
        expected = {
            "correct": ("success", "答對了！", "advance"),
            "incorrect": ("retry", "這次不對，再試一次！", "retry"),
            "indeterminate": (
                "neutral",
                "這次暫時無法判斷，學習紀錄已保存。",
                "advance",
            ),
        }

        for verdict, (tone, message, action) in expected.items():
            with self.subTest(verdict=verdict):
                database = SqliteD1Database.open(":memory:")
                service = _FakeRuntimeService(answer_status=verdict)
                runtime = LearnerFeedbackRuntime(service, database)
                response = await runtime.handle_request(
                    method="POST",
                    path=_OBSERVATION_PATH,
                    body=_CAPTURE_BODY,
                    origin=_ORIGIN,
                )

                payload = json.loads(response.body)
                self.assertEqual(response.status, 202)
                self.assertEqual(payload["directive"], "advance")
                self.assertEqual(
                    payload["feedback"],
                    {
                        "tone": tone,
                        "verdict": verdict,
                        "action": action,
                        "message": message,
                    },
                )
                self.assertNotIn("correct_response", payload)
                self.assertNotIn("validation_payload", payload)
                self.assertNotIn("answer_key", payload)
                self.assertEqual(service.evaluation_calls, 1)
                await database.close()

    async def test_incorrect_feedback_does_not_override_the_runtime_directive(
        self,
    ) -> None:
        database = SqliteD1Database.open(":memory:")
        service = _FakeRuntimeService(answer_status="incorrect", directive="complete")
        runtime = LearnerFeedbackRuntime(service, database)

        response = await runtime.handle_request(
            method="POST",
            path=_OBSERVATION_PATH,
            body=_CAPTURE_BODY,
            origin=_ORIGIN,
        )

        payload = json.loads(response.body)
        self.assertEqual(payload["directive"], "complete")
        self.assertEqual(payload["feedback"]["action"], "retry")
        self.assertEqual(service.evaluation_calls, 1)
        await database.close()

    async def test_correct_final_step_keeps_runtime_complete_directive(self) -> None:
        database = SqliteD1Database.open(":memory:")
        service = _FakeRuntimeService(answer_status="correct", directive="complete")
        runtime = LearnerFeedbackRuntime(service, database)

        response = await runtime.handle_request(
            method="POST",
            path=_OBSERVATION_PATH,
            body=_CAPTURE_BODY,
            origin=_ORIGIN,
        )

        payload = json.loads(response.body)
        self.assertEqual(payload["feedback"]["verdict"], "correct")
        self.assertEqual(payload["feedback"]["action"], "complete")
        self.assertEqual(payload["directive"], "complete")
        await database.close()

    async def test_exact_transport_replay_uses_cached_response_without_runtime_work(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "learner.sqlite3"
            database = SqliteD1Database.open(database_path)
            first_service = _FakeRuntimeService(answer_status="incorrect")
            first_runtime = LearnerFeedbackRuntime(first_service, database)
            first_response = await first_runtime.handle_request(
                method="POST",
                path=_OBSERVATION_PATH,
                body=_CAPTURE_BODY,
                origin=_ORIGIN,
            )
            await database.close()

            restarted_database = SqliteD1Database.open(database_path)
            restarted_service = _FakeRuntimeService(answer_status="correct")
            restarted_runtime = LearnerFeedbackRuntime(
                restarted_service, restarted_database
            )
            replayed_response = await restarted_runtime.handle_request(
                method="POST",
                path=_OBSERVATION_PATH,
                body=_CAPTURE_BODY,
                origin=_ORIGIN,
            )

            self.assertEqual(replayed_response.status, first_response.status)
            self.assertEqual(replayed_response.body, first_response.body)
            self.assertEqual(replayed_response.headers, first_response.headers)
            self.assertEqual(first_service.evaluation_calls, 1)
            self.assertEqual(restarted_service.request_calls, 0)
            self.assertEqual(restarted_service.evaluation_calls, 0)
            await restarted_database.close()

    async def test_changed_capture_or_origin_does_not_replay_another_response(
        self,
    ) -> None:
        database = SqliteD1Database.open(":memory:")
        service = _FakeRuntimeService(answer_status="correct")
        runtime = LearnerFeedbackRuntime(service, database)
        first_response = await runtime.handle_request(
            method="POST",
            path=_OBSERVATION_PATH,
            body=_CAPTURE_BODY,
            origin=_ORIGIN,
        )
        changed_body_response = await runtime.handle_request(
            method="POST",
            path=_OBSERVATION_PATH,
            body=_CAPTURE_BODY + b" ",
            origin=_ORIGIN,
        )
        changed_origin_response = await runtime.handle_request(
            method="POST",
            path=_OBSERVATION_PATH,
            body=_CAPTURE_BODY,
            origin="http://localhost:8081",
        )

        self.assertEqual(first_response.status, 202)
        self.assertEqual(changed_body_response.status, 202)
        self.assertEqual(changed_origin_response.status, 202)
        self.assertEqual(service.request_calls, 3)
        self.assertEqual(service.evaluation_calls, 3)
        await database.close()

    async def test_success_without_canonical_evaluation_fails_closed(self) -> None:
        database = SqliteD1Database.open(":memory:")
        service = _FakeRuntimeService(evaluate_during_request=False)
        runtime = LearnerFeedbackRuntime(service, database)

        response = await runtime.handle_request(
            method="POST",
            path=_OBSERVATION_PATH,
            body=_CAPTURE_BODY,
            origin=_ORIGIN,
        )

        self.assertEqual(response.status, 503)
        self.assertEqual(
            json.loads(response.body), {"error": "trusted_evaluation_unavailable"}
        )
        await database.close()


_OBSERVATION_PATH = (
    "/api/learners/learner-1/environments/home/packs/math-u1/observations"
)
_ORIGIN = "http://localhost:8080"
_CAPTURE_BODY = b'{"attempt":{"attemptId":"attempt-1"},"response":{"value":"prime"}}'


if __name__ == "__main__":
    unittest.main()
