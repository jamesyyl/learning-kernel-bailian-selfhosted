from __future__ import annotations

import json
import os
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
from api.learning_map import learning_map_payload
from api.sqlite_d1 import SqliteD1Database


def _correct_runtime_value(generated: dict[str, object]) -> object:
    response_kind = generated["response_specification"]["kind"]
    validation = generated["validation_payload"]
    if response_kind == "classification":
        return validation["correct_classification"]
    if response_kind == "integer-selection":
        return [
            str(item)
            for item in validation.get(
                "correct_values", validation.get("correct_response", [])
            )
        ]
    if response_kind == "multi-classification":
        return list(validation["correct_values"])
    if response_kind == "integer":
        return str(validation["correct_response"])
    if response_kind == "structured-factorization":
        return validation["correct_product_expression"]
    if response_kind == "text":
        return validation["correct_response"]
    raise AssertionError(f"No trusted response mapping for {response_kind}")


class MathU1FullSupplyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_learner_completes_ten_distinct_canonical_surfaces(self) -> None:
        sdk_root = Path(os.environ["LK_SDK_ROOT"]).resolve()
        migration_dir = sdk_root / "apps" / "runtime_vnext" / "migrations"
        learner_id = "u1-ten-step-acceptance"
        environment_id = "isolated-runtime-acceptance"

        with tempfile.TemporaryDirectory(prefix="lk-u1-ten-step-") as temporary:
            database_path = Path(temporary) / "acceptance.sqlite3"
            with (
                patch.dict(
                    os.environ,
                    {
                        "LK_SDK_ROOT": str(sdk_root),
                        "LK_RUNTIME_MIGRATIONS_DIR": str(migration_dir),
                    },
                ),
                patch.object(
                    seed_u1,
                    "ARTIFACT_DIR",
                    sdk_root
                    / "artifacts"
                    / "knowledge-packs"
                    / PACK_ID
                    / U1_PACK.identity.pack_version,
                ),
            ):
                await seed_u1.seed(database_path, learner_id, environment_id)

            database = SqliteD1Database.open(database_path)
            origin = "http://localhost:18080"
            service = LearnerFeedbackRuntime(
                compose_vnext_runtime_service(database, surface_cors_origin=origin),
                database,
            )
            artifact = read_pack_artifact(
                sdk_root
                / "artifacts"
                / "knowledge-packs"
                / PACK_ID
                / U1_PACK.identity.pack_version
            )
            pool_payloads = seed_u1._pool_payloads(artifact.content_digest)
            answer_by_activity = {
                entry["generatedActivityArtifact"]["local_id"]: entry[
                    "generatedActivityArtifact"
                ]
                for entry in pool_payloads
            }
            learner_path = (
                f"/api/learners/{quote(learner_id, safe='')}/environments/"
                f"{quote(environment_id, safe='')}/packs/{quote(PACK_ID, safe='')}"
            )
            entry_place = U1_PACK.execution_contract.entry_points[0].place_local_id
            base_time = datetime.now(UTC) - timedelta(hours=1)
            trace: list[dict[str, object]] = []
            activity_ids: set[str] = set()
            prompts: set[str] = set()
            evidence_ids: set[str] = set()
            route_kinds: set[str] = set()

            try:
                for index in range(10):
                    surface_response = await service.handle_request(
                        method="POST",
                        path=learner_path + "/surface",
                        body=json.dumps(
                            {
                                "currentContext": {
                                    "currentPlaceLocalId": entry_place,
                                    "todayPractice": True,
                                }
                            },
                            separators=(",", ":"),
                        ),
                        origin=origin,
                    )
                    self.assertEqual(
                        surface_response.status, 200, surface_response.body
                    )
                    surface = json.loads(surface_response.body)
                    self.assertEqual(
                        surface["schemaVersion"], "learning-kernel.surface-ir@1"
                    )
                    activity_id = surface["surface"]["payload"]["activityId"]
                    self.assertNotIn(activity_id, activity_ids)
                    activity_ids.add(activity_id)
                    generated = answer_by_activity[activity_id]
                    steps = surface["surface"]["payload"]["steps"]
                    step_index = surface["execution"]["stepIndex"]
                    step = steps[step_index]
                    response_block = next(
                        block
                        for block in step["blocks"]
                        if block["capability"].startswith("response.")
                    )
                    prompt = next(
                        block["props"]["text"]
                        for block in step["blocks"]
                        if block["capability"] == "content.text@1"
                    )
                    self.assertNotIn(prompt, prompts)
                    prompts.add(prompt)

                    response_kind = generated["response_specification"]["kind"]
                    validation = generated["validation_payload"]
                    if response_kind == "classification":
                        answer = validation["correct_classification"]
                    elif response_kind == "integer-selection":
                        answer = [
                            str(item)
                            for item in validation.get(
                                "correct_values", validation.get("correct_response", [])
                            )
                        ]
                    elif response_kind == "multi-classification":
                        answer = list(validation["correct_values"])
                    elif response_kind == "integer":
                        answer = str(validation["correct_response"])
                    elif response_kind == "structured-factorization":
                        answer = validation["correct_product_expression"]
                    elif response_kind == "text":
                        answer = validation["correct_response"]
                    else:
                        self.fail(f"No trusted response mapping for {response_kind}")

                    point = surface["lineage"]["reportableObservationPoints"][0]
                    capture_time = base_time + timedelta(seconds=index)
                    capture = {
                        "schemaVersion": surface["surface"][
                            "observationCaptureVersion"
                        ],
                        "decisionId": surface["lineage"]["decisionId"],
                        "activityId": activity_id,
                        "stepIndex": step_index,
                        "stepId": step["stepId"],
                        "observationPointId": point["observationPointRef"]["localId"],
                        "response": {
                            "capability": response_block["capability"],
                            "value": answer,
                        },
                        "attempt": {
                            "attemptId": f"attempt/{uuid.uuid4()}",
                            "attemptOrdinal": 1,
                            "attemptCount": 1,
                            "activeWorkDurationMs": 1000,
                        },
                        "support": {
                            "hintIdsUsed": [],
                            "revealIdsUsed": [],
                            "retryCount": 0,
                            "assistanceLevel": "independent",
                        },
                        "capturedAt": capture_time.isoformat().replace("+00:00", "Z"),
                        "practiceMode": surface["execution"]["practiceMode"],
                    }
                    observation = await service.handle_request(
                        method="POST",
                        path=learner_path + "/observations",
                        body=json.dumps(
                            capture, ensure_ascii=False, separators=(",", ":")
                        ),
                        origin=origin,
                    )
                    self.assertEqual(observation.status, 202, observation.body)
                    receipt = json.loads(observation.body)
                    self.assertEqual(receipt["feedback"]["verdict"], "correct")
                    self.assertTrue(receipt["receipt"]["evaluated"])
                    self.assertGreaterEqual(len(receipt["receipt"]["evidenceIds"]), 1)
                    evidence_ids.update(receipt["receipt"]["evidenceIds"])
                    route_kind = surface["execution"]["observation"]["routeKind"]
                    route_kinds.add(route_kind)
                    trace.append(
                        {
                            "index": index + 1,
                            "activityId": activity_id,
                            "taskFamilyId": generated["task_family"]["local_id"],
                            "prompt": prompt,
                            "responseCapability": response_block["capability"],
                            "routeKind": route_kind,
                            "decisionId": surface["lineage"]["decisionId"],
                            "evidenceIds": receipt["receipt"]["evidenceIds"],
                        }
                    )

                self.assertEqual(len(trace), 10)
                self.assertEqual(len(activity_ids), 10)
                self.assertEqual(len(prompts), 10)
                self.assertGreaterEqual(len(evidence_ids), 10)
                self.assertGreaterEqual(len(route_kinds), 2)

                place_surface_trace: list[dict[str, object]] = []
                place_activity_ids: set[str] = set()
                place_evidence_ids: set[str] = set()
                place_prompts: set[str] = set()
                place_route_kinds: set[str] = set()
                selected_families: set[str] = set()
                renderer_capabilities: set[str] = set()
                family_exploration_trace: list[dict[str, object]] = []
                family_exploration_activity_ids: set[str] = set()
                family_exploration_evidence_ids: set[str] = set()
                family_exploration_capabilities: set[str] = set()
                map_learner_id = "u1-place-surface-coverage"
                release_path = (
                    f"/api/packs/{quote(PACK_ID, safe='')}/releases/"
                    f"{quote(U1_PACK.identity.pack_version, safe='')}"
                )
                map_activation = await service.handle_request(
                    method="POST",
                    path=release_path + "/activate",
                    body=json.dumps(
                        {
                            "learnerId": map_learner_id,
                            "environmentId": environment_id,
                            "regionIds": [
                                region.local_id
                                for region in U1_PACK.learning_map.regions
                            ],
                        },
                        separators=(",", ":"),
                    ),
                )
                self.assertEqual(map_activation.status, 200, map_activation.body)
                map_learner_path = (
                    f"/api/learners/{quote(map_learner_id, safe='')}/environments/"
                    f"{quote(environment_id, safe='')}/packs/{quote(PACK_ID, safe='')}"
                )
                for place in U1_PACK.learning_map.places:
                    place_surface = await service.handle_request(
                        method="POST",
                        path=map_learner_path + "/surface",
                        body=json.dumps(
                            {
                                "currentContext": {
                                    "currentPlaceLocalId": place.local_id,
                                    "todayPractice": True,
                                }
                            },
                            separators=(",", ":"),
                        ),
                        origin=origin,
                    )
                    self.assertEqual(
                        place_surface.status,
                        200,
                        (place.local_id, place_surface.body),
                    )
                    place_payload = json.loads(place_surface.body)
                    family_id = place_payload["lineage"]["taskFamilyRef"]["localId"]
                    activity_id = place_payload["surface"]["payload"]["activityId"]
                    generated = answer_by_activity[activity_id]
                    step = place_payload["surface"]["payload"]["steps"][
                        place_payload["execution"]["stepIndex"]
                    ]
                    prompt = next(
                        block["props"]["text"]
                        for block in step["blocks"]
                        if block["capability"] == "content.text@1"
                    )
                    response_capability = next(
                        block["capability"]
                        for block in step["blocks"]
                        if block["capability"].startswith("response.")
                    )
                    selected_families.add(family_id)
                    renderer_capabilities.add(response_capability)
                    self.assertNotIn(activity_id, place_activity_ids)
                    self.assertNotIn(prompt, place_prompts)
                    place_activity_ids.add(activity_id)
                    place_prompts.add(prompt)

                    response_kind = generated["response_specification"]["kind"]
                    validation = generated["validation_payload"]
                    if response_kind == "classification":
                        answer = validation["correct_classification"]
                    elif response_kind == "integer-selection":
                        answer = [
                            str(item)
                            for item in validation.get(
                                "correct_values", validation.get("correct_response", [])
                            )
                        ]
                    elif response_kind == "multi-classification":
                        answer = list(validation["correct_values"])
                    elif response_kind == "integer":
                        answer = str(validation["correct_response"])
                    elif response_kind == "structured-factorization":
                        answer = validation["correct_product_expression"]
                    elif response_kind == "text":
                        answer = validation["correct_response"]
                    else:
                        self.fail(
                            f"No trusted Map response mapping for {response_kind}"
                        )

                    point = place_payload["lineage"]["reportableObservationPoints"][0]
                    capture = {
                        "schemaVersion": place_payload["surface"][
                            "observationCaptureVersion"
                        ],
                        "decisionId": place_payload["lineage"]["decisionId"],
                        "activityId": activity_id,
                        "stepIndex": place_payload["execution"]["stepIndex"],
                        "stepId": step["stepId"],
                        "observationPointId": point["observationPointRef"]["localId"],
                        "response": {
                            "capability": response_capability,
                            "value": answer,
                        },
                        "attempt": {
                            "attemptId": f"attempt/{uuid.uuid4()}",
                            "attemptOrdinal": 1,
                            "attemptCount": 1,
                            "activeWorkDurationMs": 1000,
                        },
                        "support": {
                            "hintIdsUsed": [],
                            "revealIdsUsed": [],
                            "retryCount": 0,
                            "assistanceLevel": "independent",
                        },
                        "capturedAt": (
                            base_time
                            + timedelta(seconds=100 + len(place_surface_trace))
                        )
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "practiceMode": place_payload["execution"]["practiceMode"],
                    }
                    place_observation = await service.handle_request(
                        method="POST",
                        path=map_learner_path + "/observations",
                        body=json.dumps(
                            capture,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        origin=origin,
                    )
                    self.assertEqual(
                        place_observation.status,
                        202,
                        (place.local_id, place_observation.body),
                    )
                    place_receipt = json.loads(place_observation.body)
                    self.assertEqual(place_receipt["feedback"]["verdict"], "correct")
                    place_evidence_ids.update(place_receipt["receipt"]["evidenceIds"])
                    route_kind = place_payload["execution"]["observation"]["routeKind"]
                    place_route_kinds.add(route_kind)
                    place_surface_trace.append(
                        {
                            "placeId": place.local_id,
                            "taskFamilyId": family_id,
                            "activityId": activity_id,
                            "prompt": prompt,
                            "responseCapability": response_capability,
                            "routeKind": route_kind,
                            "decisionId": place_payload["lineage"]["decisionId"],
                            "evidenceIds": place_receipt["receipt"]["evidenceIds"],
                        }
                    )

                family_place_ids = {
                    family["id"]: family["placeIds"]
                    for family in learning_map_payload()["taskFamilies"]
                }
                self.assertEqual(
                    set(family_place_ids),
                    {family.local_id for family in U1_PACK.task_families.families},
                )
                for family_index, family in enumerate(U1_PACK.task_families.families):
                    place_ids = family_place_ids[family.local_id]
                    self.assertTrue(place_ids, family.local_id)
                    place_id = place_ids[0]
                    family_surface = await service.handle_request(
                        method="POST",
                        path=map_learner_path + "/surface",
                        body=json.dumps(
                            {
                                "currentContext": {
                                    "currentPlaceLocalId": place_id,
                                    "todayPractice": True,
                                    "learnerExplorationTaskFamilyIds": [
                                        family.local_id
                                    ],
                                }
                            },
                            separators=(",", ":"),
                        ),
                        origin=origin,
                    )
                    self.assertEqual(
                        family_surface.status,
                        200,
                        (family.local_id, place_id, family_surface.body),
                    )
                    family_payload = json.loads(family_surface.body)
                    self.assertEqual(
                        family_payload["lineage"]["taskFamilyRef"]["localId"],
                        family.local_id,
                    )
                    self.assertEqual(
                        family_payload["execution"]["observation"]["routeKind"],
                        "learner_exploration",
                    )
                    activity_id = family_payload["surface"]["payload"]["activityId"]
                    self.assertNotIn(activity_id, place_activity_ids)
                    self.assertNotIn(activity_id, family_exploration_activity_ids)
                    family_exploration_activity_ids.add(activity_id)
                    generated = answer_by_activity[activity_id]
                    step_index = family_payload["execution"]["stepIndex"]
                    step = family_payload["surface"]["payload"]["steps"][step_index]
                    prompt = next(
                        block["props"]["text"]
                        for block in step["blocks"]
                        if block["capability"] == "content.text@1"
                    )
                    response_capability = next(
                        block["capability"]
                        for block in step["blocks"]
                        if block["capability"].startswith("response.")
                    )
                    family_exploration_capabilities.add(response_capability)
                    point = family_payload["lineage"]["reportableObservationPoints"][0]
                    family_capture = {
                        "schemaVersion": family_payload["surface"][
                            "observationCaptureVersion"
                        ],
                        "decisionId": family_payload["lineage"]["decisionId"],
                        "activityId": activity_id,
                        "stepIndex": step_index,
                        "stepId": step["stepId"],
                        "observationPointId": point["observationPointRef"]["localId"],
                        "response": {
                            "capability": response_capability,
                            "value": _correct_runtime_value(generated),
                        },
                        "attempt": {
                            "attemptId": f"attempt/{uuid.uuid4()}",
                            "attemptOrdinal": 1,
                            "attemptCount": 1,
                            "activeWorkDurationMs": 1000,
                        },
                        "support": {
                            "hintIdsUsed": [],
                            "revealIdsUsed": [],
                            "retryCount": 0,
                            "assistanceLevel": "independent",
                        },
                        "capturedAt": (
                            base_time + timedelta(seconds=300 + family_index)
                        )
                        .isoformat()
                        .replace("+00:00", "Z"),
                        "practiceMode": family_payload["execution"]["practiceMode"],
                    }
                    family_observation = await service.handle_request(
                        method="POST",
                        path=map_learner_path + "/observations",
                        body=json.dumps(
                            family_capture,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        origin=origin,
                    )
                    self.assertEqual(
                        family_observation.status,
                        202,
                        (family.local_id, family_observation.body),
                    )
                    family_receipt = json.loads(family_observation.body)
                    self.assertEqual(family_receipt["feedback"]["verdict"], "correct")
                    family_exploration_evidence_ids.update(
                        family_receipt["receipt"]["evidenceIds"]
                    )
                    family_exploration_trace.append(
                        {
                            "placeId": place_id,
                            "taskFamilyId": family.local_id,
                            "activityId": activity_id,
                            "prompt": prompt,
                            "responseCapability": response_capability,
                            "routeKind": family_payload["execution"]["observation"][
                                "routeKind"
                            ],
                            "evidenceIds": family_receipt["receipt"]["evidenceIds"],
                        }
                    )

                self.assertEqual(
                    len(place_surface_trace),
                    len(U1_PACK.learning_map.places),
                )
                self.assertGreater(len(selected_families), 0)
                self.assertEqual(
                    len(place_activity_ids), len(U1_PACK.learning_map.places)
                )
                self.assertEqual(len(place_prompts), len(U1_PACK.learning_map.places))
                self.assertGreaterEqual(
                    len(place_evidence_ids), len(U1_PACK.learning_map.places)
                )
                self.assertEqual(
                    len(family_exploration_trace),
                    len(U1_PACK.task_families.families),
                )
                self.assertEqual(
                    len(family_exploration_activity_ids),
                    len(U1_PACK.task_families.families),
                )
                self.assertEqual(
                    len(family_exploration_evidence_ids),
                    len(U1_PACK.task_families.families),
                )
                self.assertEqual(
                    family_exploration_capabilities,
                    {
                        "response.single-choice@1",
                        "response.multi-choice@1",
                        "response.math@1",
                        "response.text@1",
                    },
                )
                self.assertEqual(
                    renderer_capabilities,
                    {
                        "response.single-choice@1",
                        "response.multi-choice@1",
                        "response.math@1",
                        "response.text@1",
                    },
                )

                evidence_tables = [
                    row[0]
                    for row in database.connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                    if "evidence" in row[0].lower()
                ]
                persisted = 0
                for table_name in evidence_tables:
                    escaped = table_name.replace('"', '""')
                    persisted += database.connection.execute(
                        f'SELECT COUNT(*) FROM "{escaped}"'
                    ).fetchone()[0]
                expected_evidence_count = (
                    len(evidence_ids)
                    + len(place_evidence_ids)
                    + len(family_exploration_evidence_ids)
                )
                self.assertGreaterEqual(
                    persisted,
                    expected_evidence_count,
                    evidence_tables,
                )

                trace_path_value = os.environ.get("LK_U1_ACCEPTANCE_TRACE_PATH")
                if trace_path_value:
                    trace_path = Path(trace_path_value)
                    trace_path.parent.mkdir(parents=True, exist_ok=True)
                    report = {
                        "reportSchema": "math-u1-canonical-runtime-trace@1",
                        "status": "PASS",
                        "pack": {
                            "id": PACK_ID,
                            "version": artifact.pack_version,
                            "contentDigest": artifact.content_digest,
                        },
                        "counts": {
                            "verifiedPoolEntries": len(pool_payloads),
                            "taskFamiliesWithPoolSupply": len(
                                {
                                    entry["generatedActivityArtifact"]["task_family"][
                                        "local_id"
                                    ]
                                    for entry in pool_payloads
                                }
                            ),
                            "completedActivities": len(trace),
                            "distinctActivityIds": len(activity_ids),
                            "distinctPrompts": len(prompts),
                            "persistedEvidenceIds": len(evidence_ids),
                            "persistedEvidenceRows": persisted,
                            "mapPlacesWithCanonicalSurface": len(place_surface_trace),
                            "taskFamiliesSelectedFromMap": len(selected_families),
                            "responseCapabilitiesFromMapSurfaces": len(
                                renderer_capabilities
                            ),
                            "completedActivitiesAtMapPlaces": len(place_surface_trace),
                            "distinctMapActivityIds": len(place_activity_ids),
                            "mapEvidenceIds": len(place_evidence_ids),
                            "familyExplorationActivities": len(
                                family_exploration_trace
                            ),
                            "familyExplorationEvidenceIds": len(
                                family_exploration_evidence_ids
                            ),
                            "familiesWithCanonicalExplorationSurface": len(
                                {
                                    item["taskFamilyId"]
                                    for item in family_exploration_trace
                                }
                            ),
                        },
                        "mapSurfaceTrace": place_surface_trace,
                        "mapRouteKinds": sorted(place_route_kinds),
                        "mapSurfaceResponseCapabilities": sorted(renderer_capabilities),
                        "taskFamiliesSelectedFromMap": sorted(selected_families),
                        "familyExplorationTrace": family_exploration_trace,
                        "familyExplorationResponseCapabilities": sorted(
                            family_exploration_capabilities
                        ),
                        "responseCapabilities": sorted(
                            {item["responseCapability"] for item in trace}
                        ),
                        "routeKinds": sorted(route_kinds),
                        "trace": trace,
                    }
                    trace_path.write_text(
                        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
            finally:
                database.connection.close()


if __name__ == "__main__":
    unittest.main()
