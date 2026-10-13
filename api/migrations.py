"""Apply the canonical vNext SQL migrations to the self-hosted SQLite store."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

RUNTIME_MIGRATIONS = (
    "0001_vnext_runtime.sql",
    "0002_vnext_activity_pool.sql",
    "0003_vnext_issued_activity_bindings.sql",
    "0004_vnext_learner_evidence_release_lookup.sql",
)
EXPECTED_SCHEMA_REVISION = 4


def apply_runtime_migrations(
    connection: sqlite3.Connection, migration_dir: Path
) -> int:
    """Apply each pinned upstream migration once and reject changed history."""
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS selfhosted_migrations (
            migration_name TEXT PRIMARY KEY,
            content_sha256 TEXT NOT NULL,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    for migration_name in RUNTIME_MIGRATIONS:
        migration_path = migration_dir / migration_name
        migration_bytes = migration_path.read_bytes()
        checksum = hashlib.sha256(migration_bytes).hexdigest()
        existing = connection.execute(
            "SELECT content_sha256 FROM selfhosted_migrations WHERE migration_name = ?",
            (migration_name,),
        ).fetchone()
        if existing is not None:
            if existing[0] != checksum:
                raise RuntimeError(f"Applied migration changed: {migration_name}")
            continue

        migration_sql = migration_bytes.decode("utf-8")
        transaction_script = (
            "BEGIN IMMEDIATE;\n"
            + migration_sql
            + "\nINSERT INTO selfhosted_migrations (migration_name, content_sha256) "
            + f"VALUES ('{migration_name}', '{checksum}');\nCOMMIT;"
        )
        try:
            connection.executescript(transaction_script)
        except BaseException:
            if connection.in_transaction:
                connection.rollback()
            raise

    revision = connection.execute(
        "SELECT value FROM vnext_runtime_metadata WHERE key = 'schema_revision'"
    ).fetchone()
    if revision is None or revision[0] != str(EXPECTED_SCHEMA_REVISION):
        actual = None if revision is None else revision[0]
        raise RuntimeError(f"Unsupported vNext SQLite schema revision: {actual!r}")
    return EXPECTED_SCHEMA_REVISION


__all__ = ["EXPECTED_SCHEMA_REVISION", "RUNTIME_MIGRATIONS", "apply_runtime_migrations"]
