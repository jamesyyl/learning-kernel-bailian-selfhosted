"""A real LK five-step Surface, not five unrelated browser-issued questions."""

from __future__ import annotations

import json
import tempfile
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from apps.runtime_vnext.worker.runtime_http import compose_vnext_runtime_service
from learning_kernel.knowledge_packs.artifact import read_pack_artifact
from learning_kernel.knowledge_packs.math_u1_vnext.pack import U1_PACK
from learning_kernel.knowledge_packs.math_u1_vnext.scope import PACK_ID

from api import seed_u1
from api.feedback_runtime import LearnerFeedbackRuntime
from api.sqlite_d1 import SqliteD1Database

PRIMARY_FAMILY = "u1-5/family/problem-structure-recognition"
START_PLACE = "u1-5/problem-structure"


def _correct_value(generated: dict[str, object]) -> str:
    validation = generated["validation_payload"]
    kind = generated["response_specification"]["kind"]
    if kind == "classification":
        return str(validation["correct_classification"])
    if kind == "integer":
        return str(validation["correct_response"])
    raise AssertionError(f"Unsupported U1-5 compound response: {kind}")


class U1CompoundRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_five_steps_keep_one_context_and_save_separate_evidence(self) -> None:
        sdk_root = Path(__file__).resolve().parents[1] / "vendor" / "learning-kernel-sdk"
        migration_dir = sdk_root / "apps" / "runtime_vnext" / "migrations"
        learner_id = "u1-compound-owner-acceptance"
        environment_id = "isolated-compound"
        base_time = datetime.now(UTC) - timedelta(hours=1)

        with tempfile.TemporaryDirectory(prefix="lk-u1-compound-owner-") as temporary:
            db_path = Path(temporary) / "runtime.sqlite3"
            with patch.object(
                seed_u1,
                "ARTIFACT_DIR",
                sdk_root / "artifacts" / "knowledge-packs" / PACK_ID
                / U1_PACK.identity.pack_version,
            ), patch.dict(
                "os.environ",
                {
                    "LK_SDK_ROOT": str(sdk_root),
                    "LK_RUNTIME_MIGRATIONS_DIR": str(migration_dir),
                },
            ):
                await seed_u1.seed(db_path, learner_id, environment_id)

            artifact = read_pack_artifact(
                sdk_root / "artifacts" / "knowledge-packs" / PACK_ID
                / U1_PACK.identity.pack_version
            )
            pool = seed_u1._pool_payloads(artifact.content_digest)
            compound = {
                (
                    entry["generatedActivityArtifact"]["learner_payload"]["composition_context_id"],
                    entry["observationPointId"],
                ): entry["generatedActivityArtifact"]
                for entry in pool
                if "composition_context_id" in entry["generatedActivityArtifact"]["learner_payload"]
            }

            database = SqliteD1Database.open(db_path)
            self.addCleanup(database.connection.close)
            runtime = LearnerFeedbackRuntime(
                compose_vnext_runtime_service(database),
                database,
            )
            path = (
                f"/api/learners/{quote(learner_id, safe='')}/environments/"
                f"{quote(environment_id, safe='')}/packs/{quote(PACK_ID, safe='')}"
            )
            surface_response = await runtime.handle_request(
                method="POST",
                path=path + "/surface",
                body=json.dumps({
                    "currentContext": {
                        "currentPlaceLocalId": START_PLACE,
                        "todayPractice": False,
                        "learnerExplorationTaskFamilyIds": [PRIMARY_FAMILY],
                    }
                }),
            )
            self.assertEqual(surface_response.status, 200, surface_response.body)
            surface = json.loads(surface_response.body)
            self.assertEqual(surface["schemaVersion"], "learning-kernel.surface-ir@1")
            self.assertEqual(surface["lineage"]["taskFamilyRef"]["localId"], PRIMARY_FAMILY)
            points = surface["lineage"]["reportableObservationPoints"]
            self.assertEqual(len(points), 5)
            steps = surface["surface"]["payload"]["steps"]
            self.assertEqual(len(steps), 6)  # One Pack introduction and five answers.
            issued_id = surface["surface"]["payload"]["activityId"]
            primary = next(
                item["generatedActivityArtifact"] for item in pool
                if item["generatedActivityArtifact"]["local_id"] == issued_id
            )
            scenario_id = primary["learner_payload"]["composition_context_id"]
            operands = tuple(primary["learner_payload"]["operands"])
            evidence_ids = set()
            captured_count = 0

            for ordinal, point in enumerate(points):
                step_index = point["stepIndex"]
                step = steps[step_index]
                record = compound[(scenario_id, point["observationPointRef"]["localId"])]
                self.assertEqual(tuple(record["learner_payload"]["operands"]), operands)
                response = next(
                    block for block in step["blocks"]
                    if block["capability"].startswith("response.")
                )
                prompt = next(
                    block["props"]["text"] for block in step["blocks"]
                    if block["capability"] == "content.text@1"
                )
                self.assertIn(str(operands[0]), prompt)
                self.assertIn(str(operands[1]), prompt)
                correct = _correct_value(record)

                # Deliberately make a wrong model choice, then retry the *same*
                # observation. It must not erase earlier correct Evidence.
                answers = ["最小公倍數", correct] if ordinal == 1 else [correct]
                for attempt_number, answer in enumerate(answers, start=1):
                    capture = {
                        "schemaVersion": surface["surface"]["observationCaptureVersion"],
                        "decisionId": surface["lineage"]["decisionId"],
                        "activityId": issued_id,
                        "stepIndex": step_index,
                        "stepId": step["stepId"],
                        "observationPointId": point["observationPointRef"]["localId"],
                        "response": {"capability": response["capability"], "value": answer},
                        "attempt": {
                            "attemptId": f"attempt/{uuid.uuid4()}",
                            "attemptOrdinal": attempt_number,
                            "attemptCount": attempt_number,
                            "activeWorkDurationMs": 500,
                        },
                        "support": {
                            "hintIdsUsed": [],
                            "revealIdsUsed": [],
                            "retryCount": attempt_number - 1,
                            "assistanceLevel": "independent",
                        },
                        "capturedAt": (
                            base_time + timedelta(seconds=captured_count)
                        ).isoformat().replace("+00:00", "Z"),
                        "practiceMode": surface["execution"]["practiceMode"],
                    }
                    captured_count += 1
                    receipt = await runtime.handle_request(
                        method="POST",
                        path=path + "/observations",
                        body=json.dumps(capture, ensure_ascii=False),
                    )
                    self.assertEqual(receipt.status, 202, receipt.body)
                    result = json.loads(receipt.body)
                    evidence_ids.update(result["receipt"]["evidenceIds"])
                    if ordinal == 1 and attempt_number == 1:
                        self.assertEqual(result["feedback"]["verdict"], "incorrect")
                        self.assertEqual(result["feedback"]["action"], "retry")
                    else:
                        self.assertEqual(result["feedback"]["verdict"], "correct")
                        self.assertEqual(
                            result["feedback"]["action"],
                            "complete" if ordinal == 4 else "advance",
                        )

            self.assertGreaterEqual(len(evidence_ids), 5)
            self.assertEqual(surface["execution"]["practiceMode"], "learning")

            # Restart persistence check: both correct and incorrect learner
            # observations remain in the isolated SQLite database.
            database.connection.close()
            restarted = SqliteD1Database.open(db_path)
            try:
                saved = restarted.connection.execute(
                    "SELECT COUNT(*) FROM vnext_learner_records WHERE learner_id = ? AND record_kind = 'observation'",
                    (learner_id,),
                ).fetchone()[0]
                self.assertGreaterEqual(saved, 6)
            finally:
                restarted.connection.close()
