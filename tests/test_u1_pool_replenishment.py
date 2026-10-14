from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from apps.runtime_vnext.worker.runtime_http import compose_vnext_runtime_service
from learning_kernel.domain.values import thaw_json
from learning_kernel.knowledge_packs.artifact import read_pack_artifact
from learning_kernel.knowledge_packs.math_u1_vnext.deterministic_generators import (
    build_u1_deterministic_generator_registry,
)
from learning_kernel.knowledge_packs.math_u1_vnext.pack import U1_PACK
from learning_kernel.knowledge_packs.math_u1_vnext.scope import PACK_ID, PACK_VERSION
from learning_kernel.knowledge_packs.math_u1_vnext.verification import (
    MathU1IndependentVerifier,
)

from api import seed_u1
from api.feedback_runtime import LearnerFeedbackRuntime
from api.migrations import apply_runtime_migrations
from api.replenish_u1_pool import replenish_once
from api.sqlite_d1 import SqliteD1Database


def _correct_response(artifact: dict[str, object]) -> object:
    response = artifact["response_specification"]
    validation = artifact["validation_payload"]
    kind = response["kind"]
    if kind == "classification":
        return validation["correct_classification"]
    if kind == "integer-selection":
        return [str(item) for item in validation.get("correct_values", [])]
    if kind == "multi-classification":
        return list(validation["correct_values"])
    if kind == "integer":
        return str(validation["correct_response"])
    if kind == "structured-factorization":
        return validation["correct_product_expression"]
    if kind == "text":
        return validation["correct_response"]
    raise AssertionError(f"No response fixture for {kind}")


def _capture(
    surface: dict[str, object],
    value: object,
    *,
    ordinal: int,
    captured_at: datetime,
) -> dict[str, object]:
    step_index = surface["execution"]["stepIndex"]
    step = surface["surface"]["payload"]["steps"][step_index]
    point = next(
        item
        for item in surface["lineage"]["reportableObservationPoints"]
        if item["stepIndex"] == step_index
    )
    response_block = next(
        block for block in step["blocks"] if block["capability"].startswith("response.")
    )
    return {
        "schemaVersion": surface["surface"]["observationCaptureVersion"],
        "decisionId": surface["lineage"]["decisionId"],
        "activityId": surface["surface"]["payload"]["activityId"],
        "stepIndex": step_index,
        "stepId": step["stepId"],
        "observationPointId": point["observationPointRef"]["localId"],
        "response": {
            "capability": response_block["capability"],
            "value": value,
        },
        "attempt": {
            "attemptId": f"attempt/{uuid.uuid4()}",
            "attemptOrdinal": ordinal,
            "attemptCount": ordinal,
            "activeWorkDurationMs": 1000,
        },
        "support": {
            "hintIdsUsed": [],
            "revealIdsUsed": [],
            "retryCount": ordinal - 1,
            "assistanceLevel": "independent",
        },
        "capturedAt": captured_at.isoformat().replace("+00:00", "Z"),
        "practiceMode": surface["execution"]["practiceMode"],
    }


class U1PoolReplenishmentLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_exhausted_family_refills_and_remains_shared_but_evidence_is_per_learner(
        self,
    ) -> None:
        sdk_root = (
            Path(__file__).resolve().parents[1] / "vendor" / "learning-kernel-sdk"
        )
        artifact_dir = (
            sdk_root / "artifacts" / "knowledge-packs" / PACK_ID / PACK_VERSION
        )
        artifact = read_pack_artifact(artifact_dir)
        migration_dir = sdk_root / "apps" / "runtime_vnext" / "migrations"
        origin = "http://localhost:18080"
        entry_place = U1_PACK.execution_contract.entry_points[0].place_local_id
        family_id = "u1-1/family/direct-prime-composite-classification"
        learner_a = "u1-refill-learner-a"
        learner_b = "u1-refill-learner-b"
        environment_id = "isolated-refill"
        region_ids = [region.local_id for region in U1_PACK.learning_map.regions]
        generated_by_id: dict[str, dict[str, object]] = {}
        base_time = datetime.now(UTC)

        with ExitStack() as cleanup:
            temporary = cleanup.enter_context(
                tempfile.TemporaryDirectory(prefix="lk-u1-refill-lifecycle-")
            )
            database_path = Path(temporary) / "runtime.sqlite3"
            database = SqliteD1Database.open(database_path)
            cleanup.callback(database.connection.close)
            apply_runtime_migrations(database.connection, migration_dir)
            runtime = compose_vnext_runtime_service(
                database,
                pool_admission_token=seed_u1.ADMISSION_TOKEN,
                surface_cors_origin=origin,
            )
            feedback = LearnerFeedbackRuntime(runtime, database)

            install = await runtime.handle_request(
                method="POST",
                path="/api/packs/install",
                body=json.dumps(
                    {
                        "manifest": thaw_json(artifact.manifest),
                        "content": thaw_json(artifact.content),
                        "installEnvironment": seed_u1._install_environment(),
                    },
                    ensure_ascii=False,
                ),
            )
            self.assertEqual(install.status, 200, install.body)

            release_path = (
                f"/api/packs/{quote(PACK_ID, safe='')}/releases/"
                f"{quote(PACK_VERSION, safe='')}"
            )
            for learner_id in (learner_a, learner_b):
                activated = await runtime.handle_request(
                    method="POST",
                    path=release_path + "/activate",
                    body=json.dumps(
                        {
                            "learnerId": learner_id,
                            "environmentId": environment_id,
                            "regionIds": region_ids,
                        },
                        separators=(",", ":"),
                    ),
                )
                self.assertEqual(activated.status, 200, activated.body)

            pool_payloads = seed_u1._pool_payloads(artifact.content_digest)
            generated_by_id = {
                entry["generatedActivityArtifact"]["local_id"]: entry[
                    "generatedActivityArtifact"
                ]
                for entry in pool_payloads
            }
            admission = await runtime.handle_request(
                method="POST",
                path=release_path + "/activity-pool/entries/batch",
                body=json.dumps({"entries": list(pool_payloads)}, ensure_ascii=False),
                authorization=f"Bearer {seed_u1.ADMISSION_TOKEN}",
            )
            self.assertIn(admission.status, (200, 201), admission.body)
            self.assertEqual(json.loads(admission.body)["entryCount"], 260)

            def learner_path(learner_id: str) -> str:
                return (
                    f"/api/learners/{quote(learner_id, safe='')}/environments/"
                    f"{quote(environment_id, safe='')}/packs/{quote(PACK_ID, safe='')}"
                )

            def surface_body(place_id: str) -> str:
                return json.dumps(
                    {
                        "currentContext": {
                            "currentPlaceLocalId": place_id,
                            "todayPractice": True,
                        }
                    },
                    separators=(",", ":"),
                )

            async def get_surface(learner_id: str) -> dict[str, object]:
                response = await feedback.handle_request(
                    method="POST",
                    path=learner_path(learner_id) + "/surface",
                    body=surface_body(entry_place),
                    origin=origin,
                )
                if response.status != 200:
                    return {
                        "httpStatus": response.status,
                        "error": json.loads(response.body),
                    }
                return json.loads(response.body)

            learner_a_activity_ids: set[str] = set()
            learner_a_prompts: set[str] = set()
            first_learner_a_activity_id: str | None = None
            for index in range(10):
                surface = await get_surface(learner_a)
                self.assertNotIn("httpStatus", surface, surface)
                self.assertEqual(
                    surface["lineage"]["taskFamilyRef"]["localId"], family_id
                )
                activity_id = surface["surface"]["payload"]["activityId"]
                step = surface["surface"]["payload"]["steps"][
                    surface["execution"]["stepIndex"]
                ]
                prompt = next(
                    block["props"]["text"]
                    for block in step["blocks"]
                    if block["capability"] == "content.text@1"
                )
                self.assertNotIn(activity_id, learner_a_activity_ids)
                self.assertNotIn(prompt, learner_a_prompts)
                if index == 0:
                    first_learner_a_activity_id = activity_id
                learner_a_activity_ids.add(activity_id)
                learner_a_prompts.add(prompt)
                answer = _correct_response(generated_by_id[activity_id])
                result = await feedback.handle_request(
                    method="POST",
                    path=learner_path(learner_a) + "/observations",
                    body=json.dumps(
                        _capture(
                            surface,
                            answer,
                            ordinal=1,
                            captured_at=base_time + timedelta(seconds=index),
                        ),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    origin=origin,
                )
                self.assertEqual(result.status, 202, result.body)
                self.assertEqual(
                    json.loads(result.body)["feedback"]["verdict"], "correct"
                )

            self.assertEqual(len(learner_a_activity_ids), 10)
            self.assertTrue(
                all(prompt.startswith("判斷 ") for prompt in learner_a_prompts)
            )
            depleted = await get_surface(learner_a)
            self.assertEqual(depleted["httpStatus"], 503)
            self.assertEqual(depleted["error"]["error"], "activity_supply_unavailable")
            self.assertEqual(depleted["error"]["task_family_id"], family_id)

            registry = build_u1_deterministic_generator_registry()
            refill = await replenish_once(
                database,
                runtime,
                artifact.content_digest,
                registry,
                MathU1IndependentVerifier(),
                no_supply_signatures={},
            )
            self.assertEqual(refill["entriesAdded"], 8)
            self.assertEqual(refill["families"], {family_id: 8})

            refilled_surface = await get_surface(learner_a)
            self.assertNotIn("httpStatus", refilled_surface, refilled_surface)
            refilled_id = refilled_surface["surface"]["payload"]["activityId"]
            self.assertNotIn(refilled_id, learner_a_activity_ids)
            self.assertEqual(
                next(
                    block["props"]["text"]
                    for block in refilled_surface["surface"]["payload"]["steps"][
                        refilled_surface["execution"]["stepIndex"]
                    ]["blocks"]
                    if block["capability"] == "content.text@1"
                ),
                "判斷 12 是質數還是合數。",
            )
            wrong = await feedback.handle_request(
                method="POST",
                path=learner_path(learner_a) + "/observations",
                body=json.dumps(
                    _capture(
                        refilled_surface,
                        "質數",
                        ordinal=1,
                        captured_at=base_time + timedelta(seconds=20),
                    ),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                origin=origin,
            )
            self.assertEqual(wrong.status, 202, wrong.body)
            self.assertEqual(json.loads(wrong.body)["feedback"]["verdict"], "incorrect")
            self.assertEqual(json.loads(wrong.body)["feedback"]["action"], "retry")
            retried = await feedback.handle_request(
                method="POST",
                path=learner_path(learner_a) + "/observations",
                body=json.dumps(
                    _capture(
                        refilled_surface,
                        "合數",
                        ordinal=2,
                        captured_at=base_time + timedelta(seconds=21),
                    ),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                origin=origin,
            )
            self.assertEqual(retried.status, 202, retried.body)
            self.assertEqual(json.loads(retried.body)["feedback"]["verdict"], "correct")

            learner_b_surface = await get_surface(learner_b)
            self.assertNotIn("httpStatus", learner_b_surface, learner_b_surface)
            learner_b_activity_id = learner_b_surface["surface"]["payload"][
                "activityId"
            ]
            self.assertEqual(learner_b_activity_id, first_learner_a_activity_id)
            learner_b_answer = _correct_response(generated_by_id[learner_b_activity_id])
            learner_b_result = await feedback.handle_request(
                method="POST",
                path=learner_path(learner_b) + "/observations",
                body=json.dumps(
                    _capture(
                        learner_b_surface,
                        learner_b_answer,
                        ordinal=1,
                        captured_at=base_time + timedelta(seconds=22),
                    ),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                origin=origin,
            )
            self.assertEqual(learner_b_result.status, 202, learner_b_result.body)
            self.assertEqual(
                json.loads(learner_b_result.body)["feedback"]["verdict"], "correct"
            )

            counts = {
                learner_id: database.connection.execute(
                    """
                    SELECT COUNT(DISTINCT activity_id)
                    FROM vnext_learner_evidence
                    WHERE learner_id = ? AND environment_id = ? AND pack_id = ?
                    """,
                    (learner_id, environment_id, PACK_ID),
                ).fetchone()[0]
                for learner_id in (learner_a, learner_b)
            }
            self.assertEqual(counts[learner_b], 1)
            self.assertGreaterEqual(counts[learner_a], 11)

            database.connection.close()
            restarted = SqliteD1Database.open(database_path)
            self.addCleanup(restarted.connection.close)
            try:
                apply_runtime_migrations(restarted.connection, migration_dir)
                pool_count = restarted.connection.execute(
                    "SELECT COUNT(*) FROM vnext_activity_pool_entries WHERE pack_id=? AND pack_version=?",
                    (PACK_ID, PACK_VERSION),
                ).fetchone()[0]
                self.assertEqual(pool_count, 268)
                self.assertEqual(
                    restarted.connection.execute(
                        "SELECT COUNT(*) FROM vnext_learner_evidence WHERE learner_id=? AND environment_id=? AND pack_id=?",
                        (learner_b, environment_id, PACK_ID),
                    ).fetchone()[0],
                    1,
                )
            finally:
                restarted.connection.close()
