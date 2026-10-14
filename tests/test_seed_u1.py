from __future__ import annotations

import json
import sqlite3
import unittest
from types import SimpleNamespace

from api import seed_u1


class SeedSurfaceIdempotencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute(
            """
            CREATE TABLE vnext_issued_activity_bindings (
                learner_id TEXT,
                environment_id TEXT,
                pack_id TEXT,
                pack_version TEXT,
                content_digest TEXT,
                canonical_json TEXT
            )
            """
        )
        self.database = SimpleNamespace(connection=self.connection)
        self.content_digest = seed_u1.U1_PACK.lifecycle.content_digest

    def tearDown(self) -> None:
        self.connection.close()

    def test_no_prior_surface_allows_initial_seed_smoke_check(self) -> None:
        self.assertFalse(
            seed_u1._has_existing_seed_surface_binding(
                self.database,
                "learner-1",
                "home",
                self.content_digest,
            )
        )

    def test_matching_surface_binding_is_reused(self) -> None:
        binding = {
            "pack": {
                "packId": seed_u1.PACK_ID,
                "packVersion": seed_u1.PACK_VERSION,
                "contentDigest": self.content_digest,
            },
            "surfaceDigest": "sha256:test-surface",
        }
        self.connection.execute(
            """
            INSERT INTO vnext_issued_activity_bindings
                (learner_id, environment_id, pack_id, pack_version,
                 content_digest, canonical_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "learner-1",
                "home",
                seed_u1.PACK_ID,
                seed_u1.PACK_VERSION,
                self.content_digest,
                json.dumps(binding),
            ),
        )
        self.connection.commit()

        self.assertTrue(
            seed_u1._has_existing_seed_surface_binding(
                self.database,
                "learner-1",
                "home",
                self.content_digest,
            )
        )

    def test_existing_binding_with_wrong_lineage_fails_closed(self) -> None:
        binding = {
            "pack": {
                "packId": seed_u1.PACK_ID,
                "packVersion": "0.0.0",
                "contentDigest": self.content_digest,
            },
            "surfaceDigest": "sha256:test-surface",
        }
        self.connection.execute(
            """
            INSERT INTO vnext_issued_activity_bindings
                (learner_id, environment_id, pack_id, pack_version,
                 content_digest, canonical_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "learner-1",
                "home",
                seed_u1.PACK_ID,
                seed_u1.PACK_VERSION,
                self.content_digest,
                json.dumps(binding),
            ),
        )
        self.connection.commit()

        with self.assertRaisesRegex(
            RuntimeError, "Existing Surface binding has unexpected Pack lineage"
        ):
            seed_u1._has_existing_seed_surface_binding(
                self.database,
                "learner-1",
                "home",
                self.content_digest,
            )
