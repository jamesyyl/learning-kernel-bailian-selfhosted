from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from api.migrations import apply_runtime_migrations

_MIGRATIONS = (
    Path(__file__).parents[1]
    / "vendor"
    / "learning-kernel-sdk"
    / "apps"
    / "runtime_vnext"
    / "migrations"
)


@unittest.skipUnless(_MIGRATIONS.is_dir(), "initialize the pinned SDK submodule to run")
class PinnedSdkSqliteMigrationTests(unittest.TestCase):
    def test_canonical_runtime_migrations_apply_to_sqlite(self) -> None:
        connection = sqlite3.connect(":memory:", isolation_level=None)
        try:
            revision = apply_runtime_migrations(connection, _MIGRATIONS)
            self.assertEqual(revision, 4)
            self.assertTrue(
                connection.execute(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = 'vnext_learner_evidence'"
                ).fetchone()
            )
            self.assertEqual(apply_runtime_migrations(connection, _MIGRATIONS), 4)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
