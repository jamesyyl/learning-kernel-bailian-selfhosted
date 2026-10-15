"""Refilling U1-5 must admit complete five-step scenarios, never orphan primaries."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from apps.runtime_vnext.worker.runtime_http import compose_vnext_runtime_service
from learning_kernel.knowledge_packs.math_u1_vnext.pack import U1_PACK
from learning_kernel.knowledge_packs.math_u1_vnext.scope import PACK_ID, PACK_VERSION
from learning_kernel.knowledge_packs.math_u1_vnext.deterministic_generators import (
    build_u1_deterministic_generator_registry,
)
from learning_kernel.knowledge_packs.math_u1_vnext.verification import (
    MathU1IndependentVerifier,
)

from api import seed_u1
from api.replenish_u1_pool import replenish_once
from api.sqlite_d1 import SqliteD1Database


class U1CompoundRefillContinuityTests(unittest.IsolatedAsyncioTestCase):
    async def test_exhausted_primary_adds_whole_scenarios_and_preserves_history(
        self,
    ) -> None:
        learner, environment = "u1-compound-refill-learner", "isolated"
        with tempfile.TemporaryDirectory(prefix="lk-u1-compound-refill-") as temp:
            database_path = Path(temp) / "learning.sqlite3"
            await seed_u1.seed(database_path, learner, environment)
            database = SqliteD1Database.open(database_path)
            try:
                connection = database.connection
                primary = seed_u1.COMPOUND_PRIMARY_FAMILY
                rows = connection.execute(
                    """
                    SELECT artifact_id FROM vnext_activity_pool_entries
                    WHERE pack_id = ? AND pack_version = ? AND task_family_id = ?
                    ORDER BY artifact_id
                    """,
                    (PACK_ID, PACK_VERSION, primary),
                ).fetchall()
                self.assertEqual(len(rows), 10)
                now = datetime.now(UTC).isoformat()
                for number, (activity_id,) in enumerate(rows):
                    connection.execute(
                        """
                        INSERT INTO vnext_issued_activity_bindings(
                            learner_id, environment_id, pack_id, pack_version,
                            content_digest, decision_id, activity_id,
                            surface_digest, canonical_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            learner,
                            environment,
                            PACK_ID,
                            PACK_VERSION,
                            U1_PACK.lifecycle.content_digest,
                            f"decision/test-issued/{number}",
                            activity_id,
                            "sha256:" + "0" * 64,
                            "{}",
                            now,
                        ),
                    )
                connection.commit()
                original_count = connection.execute(
                    "SELECT COUNT(*) FROM vnext_activity_pool_entries"
                ).fetchone()[0]
                origin = "http://localhost:18085"
                runtime = compose_vnext_runtime_service(
                    database,
                    pool_admission_token=seed_u1.ADMISSION_TOKEN,
                    surface_cors_origin=origin,
                )
                results = await replenish_once(
                    database,
                    runtime,
                    U1_PACK.lifecycle.content_digest,
                    build_u1_deterministic_generator_registry(),
                    MathU1IndependentVerifier(),
                )
                self.assertEqual(results["status"], "refilled")
                self.assertEqual(results["families"], {primary: 10})
                self.assertEqual(results["entriesAdded"], 50)
                new_rows = connection.execute(
                    """
                    SELECT task_family_id, artifact_id,
                           json_extract(
                               canonical_json,
                               '$.generatedActivityArtifact.learner_payload.composition_context_id'
                           )
                    FROM vnext_activity_pool_entries
                    WHERE artifact_id LIKE '%/variant-101%'
                    """
                ).fetchall()
                self.assertEqual(len(new_rows), 50)
                by_scenario: dict[str, set[str]] = {}
                for family_id, activity_id, scenario_id in new_rows:
                    self.assertIsNotNone(scenario_id)
                    self.assertIn(family_id, seed_u1.COMPOUND_FAMILY_IDS)
                    self.assertIn("/variant-101", activity_id)
                    by_scenario.setdefault(scenario_id, set()).add(family_id)
                self.assertEqual(len(by_scenario), 10)
                self.assertTrue(
                    all(
                        value == set(seed_u1.COMPOUND_FAMILY_IDS)
                        for value in by_scenario.values()
                    )
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM vnext_activity_pool_entries"
                    ).fetchone()[0],
                    original_count + 50,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM vnext_issued_activity_bindings"
                    ).fetchone()[0],
                    10,
                )
                surface = await runtime.handle_request(
                    method="POST",
                    path=(
                        f"/api/learners/{quote(learner, safe='')}"
                        f"/environments/{quote(environment, safe='')}"
                        f"/packs/{quote(PACK_ID, safe='')}/surface"
                    ),
                    body=json.dumps(
                        {
                            "currentContext": {
                                "currentPlaceLocalId": "u1-5/problem-structure",
                                "todayPractice": False,
                                "learnerExplorationTaskFamilyIds": [primary],
                            }
                        }
                    ),
                    origin=origin,
                )
                self.assertEqual(surface.status, 200, surface.body)
                payload = json.loads(surface.body)
                self.assertEqual(
                    len(payload["lineage"]["reportableObservationPoints"]), 5
                )
            finally:
                database.connection.close()
