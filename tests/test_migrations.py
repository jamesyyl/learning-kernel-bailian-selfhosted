from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from api.migrations import RUNTIME_MIGRATIONS, apply_runtime_migrations


class RuntimeMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.migration_dir = Path(self.temp_dir.name)
        self.connection = sqlite3.connect(":memory:", isolation_level=None)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp_dir.cleanup()

    def _write_migrations(self) -> None:
        for index, migration_name in enumerate(RUNTIME_MIGRATIONS, start=1):
            metadata = (
                "CREATE TABLE vnext_runtime_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);\n"
                "INSERT INTO vnext_runtime_metadata (key, value) "
                "VALUES ('schema_revision', '0');\n"
                if index == 1
                else ""
            )
            sql = (
                f"CREATE TABLE migration_{index} (value TEXT NOT NULL);\n"
                f"INSERT INTO migration_{index} (value) VALUES ('{index}');\n"
                + metadata
                + "INSERT INTO vnext_runtime_metadata (key, value) "
                + f"VALUES ('schema_revision', '{index}') "
                + "ON CONFLICT(key) DO UPDATE SET value = excluded.value;\n"
            )
            self.migration_dir.joinpath(migration_name).write_text(
                sql, encoding="utf-8"
            )

    def test_applies_in_order_and_is_idempotent(self) -> None:
        self._write_migrations()

        revision = apply_runtime_migrations(self.connection, self.migration_dir)
        second_revision = apply_runtime_migrations(self.connection, self.migration_dir)

        self.assertEqual(revision, 4)
        self.assertEqual(second_revision, 4)
        applied = self.connection.execute(
            "SELECT COUNT(*) FROM selfhosted_migrations"
        ).fetchone()
        values = self.connection.execute("SELECT value FROM migration_4").fetchall()
        self.assertEqual(applied, (4,))
        self.assertEqual(values, [("4",)])

    def test_rejects_changed_applied_migration(self) -> None:
        self._write_migrations()
        apply_runtime_migrations(self.connection, self.migration_dir)
        first_migration = self.migration_dir / RUNTIME_MIGRATIONS[0]
        first_migration.write_text(
            "CREATE TABLE IF NOT EXISTS migration_1 (value TEXT NOT NULL);\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(RuntimeError, "Applied migration changed"):
            apply_runtime_migrations(self.connection, self.migration_dir)

    def test_failed_migration_rolls_back_its_schema_and_record(self) -> None:
        self._write_migrations()
        bad_migration = self.migration_dir / RUNTIME_MIGRATIONS[1]
        bad_migration.write_text("CREATE TABLE migration_2 (\n", encoding="utf-8")

        with self.assertRaises(sqlite3.OperationalError):
            apply_runtime_migrations(self.connection, self.migration_dir)

        recorded = self.connection.execute(
            "SELECT migration_name FROM selfhosted_migrations ORDER BY migration_name"
        ).fetchall()
        table = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'migration_2'"
        ).fetchone()
        self.assertEqual(recorded, [(RUNTIME_MIGRATIONS[0],)])
        self.assertIsNone(table)


if __name__ == "__main__":
    unittest.main()
