"""Fail-closed checks for the standalone Docker + SQLite acceptance gate."""

from __future__ import annotations

import sqlite3
import subprocess
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import run_selfhost_gate as gate


def test_every_root_test_is_explicit_and_no_platform_suite_is_selected() -> None:
    sdk = gate.ROOT / "vendor" / "learning-kernel-sdk"
    gate.validate_test_contract(sdk)
    selected = (*gate.SELFHOST_TESTS, *gate.CANONICAL_SDK_TESTS)
    assert len(selected) == len(set(selected))
    assert not any(
        "wrangler" in file or "test_runtime_vnext_worker.py" in file
        for file in selected
    )


def test_skipped_test_is_not_accepted_as_a_green_gate() -> None:
    with patch.object(
        gate.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(
            args=["pytest"], returncode=0, stdout="1 passed, 1 skipped in 0.12s\n"
        ),
    ):
        result = gate.run_group(
            "simulated-skip",
            gate.ROOT,
            ("tests/test_selfhost_gate_contract.py",),
            gate.ROOT / "vendor" / "learning-kernel-sdk",
        )
    assert result["passed"] is False
    assert result["skipped"] is True


def _fake_sdk(tmp_path: Path) -> Path:
    sdk = tmp_path / "sdk"
    scope = sdk / "learning_kernel" / "knowledge_packs" / "math_u1_vnext" / "scope.py"
    scope.parent.mkdir(parents=True)
    scope.write_text('PACK_VERSION = "0.3.7"\n', encoding="utf-8")
    migrations = sdk / "apps" / "runtime_vnext" / "migrations"
    migrations.mkdir(parents=True)
    for filename in gate.MIGRATION_FILENAMES:
        (migrations / filename).write_text(f"-- fixture {filename}\n", encoding="utf-8")
    return sdk


def _metadata_db(path: Path, *, revision: str, sdk: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE vnext_runtime_metadata(key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.executemany(
            "INSERT INTO vnext_runtime_metadata(key, value) VALUES (?, ?)",
            [
                ("schema_family", gate.EXPECTED_SCHEMA_FAMILY),
                ("schema_revision", revision),
            ],
        )
        connection.execute(
            "CREATE TABLE selfhosted_migrations("
            "migration_name TEXT PRIMARY KEY, content_sha256 TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO selfhosted_migrations(migration_name, content_sha256) VALUES (?, ?)",
            [
                (
                    filename,
                    sha256(
                        (
                            sdk / "apps" / "runtime_vnext" / "migrations" / filename
                        ).read_bytes()
                    ).hexdigest(),
                )
                for filename in gate.MIGRATION_FILENAMES
            ],
        )


def test_live_gate_reads_sqlite_without_mutating(tmp_path: Path) -> None:
    database = tmp_path / "isolated.sqlite3"
    sdk = _fake_sdk(tmp_path)
    _metadata_db(database, revision="4", sdk=sdk)
    original = database.read_bytes()
    with patch.object(
        gate,
        "_json_get",
        side_effect=[
            {"ready": True},
            {"places": [{}] * 17, "pack": {"version": "0.3.7"}},
        ],
    ):
        result = gate.check_live_service("http://127.0.0.1:18085", database, sdk)
    assert result["passed"] is True
    assert result["schemaRevision"] == "4"
    assert database.read_bytes() == original


def test_live_gate_rejects_wrong_sqlite_revision(tmp_path: Path) -> None:
    database = tmp_path / "wrong-revision.sqlite3"
    sdk = _fake_sdk(tmp_path)
    _metadata_db(database, revision="3", sdk=sdk)
    with (
        patch.object(
            gate,
            "_json_get",
            side_effect=[
                {"ready": True},
                {"places": [{}] * 17, "pack": {"version": "0.3.7"}},
            ],
        ),
        pytest.raises(RuntimeError, match="revision"),
    ):
        gate.check_live_service("http://127.0.0.1:18085", database, sdk)


def test_compose_production_path_uses_local_sqlite_without_cloudflare() -> None:
    compose = (gate.ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "runtime:" in compose and "pool-refiller:" in compose and "web:" in compose
    assert "LK_DATABASE_PATH: /data/learning-kernel.sqlite3" in compose
    assert "wrangler" not in compose.casefold()
    assert "cloudflare" not in compose.casefold()
    assert "D1_DATABASE_ID" not in compose


def test_live_gate_rejects_modified_migration_checksum(tmp_path: Path) -> None:
    sdk = _fake_sdk(tmp_path)
    database = tmp_path / "tampered.sqlite3"
    _metadata_db(database, revision="4", sdk=sdk)
    migration = (
        sdk / "apps" / "runtime_vnext" / "migrations" / gate.MIGRATION_FILENAMES[2]
    )
    migration.write_text("-- modified after DB migration\n", encoding="utf-8")
    with (
        patch.object(
            gate,
            "_json_get",
            side_effect=[
                {"ready": True},
                {"places": [{}] * 17, "pack": {"version": "0.3.7"}},
            ],
        ),
        pytest.raises(RuntimeError, match="checksum"),
    ):
        gate.check_live_service("http://127.0.0.1:18085", database, sdk)


def test_live_gate_rejects_pack_release_drift(tmp_path: Path) -> None:
    sdk = _fake_sdk(tmp_path)
    database = tmp_path / "wrong-pack.sqlite3"
    _metadata_db(database, revision="4", sdk=sdk)
    with (
        patch.object(
            gate,
            "_json_get",
            side_effect=[
                {"ready": True},
                {"places": [{}] * 17, "pack": {"version": "0.3.6"}},
            ],
        ),
        pytest.raises(RuntimeError, match="release"),
    ):
        gate.check_live_service("http://127.0.0.1:18085", database, sdk)
