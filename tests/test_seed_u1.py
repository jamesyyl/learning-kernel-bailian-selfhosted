from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning_kernel.knowledge_packs.artifact import read_pack_artifact
from learning_kernel.knowledge_packs.math_u1_vnext.scope import PACK_ID, PACK_VERSION

from api import seed_u1


class _Response:
    def __init__(self, status: int, payload: dict[str, object]) -> None:
        self.status = status
        self.body = json.dumps(payload).encode("utf-8")


class _BootstrapService:
    def __init__(self) -> None:
        self.paths: list[str] = []

    async def handle_request(
        self,
        *,
        method: str,
        path: str,
        body: str | None = None,
        authorization: str | None = None,
    ) -> _Response:
        self.paths.append(path)
        if path.endswith("/activity-pool/entries/batch"):
            payload = json.loads(body or "{}")
            return _Response(201, {"entryCount": len(payload.get("entries", []))})
        return _Response(200, {})


class SeedBootstrapSurfaceTests(unittest.TestCase):
    def test_repeated_bootstrap_admits_pool_without_issuing_learner_surfaces(
        self,
    ) -> None:
        sdk_root = (
            Path(__file__).resolve().parents[1] / "vendor" / "learning-kernel-sdk"
        )
        artifact = read_pack_artifact(
            sdk_root / "artifacts" / "knowledge-packs" / PACK_ID / PACK_VERSION
        )
        service = _BootstrapService()

        async def run_seed(database_path: Path) -> None:
            with (
                patch.object(seed_u1, "read_pack_artifact", return_value=artifact),
                patch.object(seed_u1, "_pool_payloads", return_value=()),
                patch.object(
                    seed_u1, "compose_vnext_runtime_service", return_value=service
                ),
                patch.dict(
                    "os.environ",
                    {
                        "LK_RUNTIME_MIGRATIONS_DIR": str(
                            sdk_root / "apps" / "runtime_vnext" / "migrations"
                        )
                    },
                ),
            ):
                await seed_u1.seed(database_path, "bootstrap-learner", "home")

        with tempfile.TemporaryDirectory(prefix="lk-u1-seed-bootstrap-") as temporary:
            database_path = Path(temporary) / "runtime.sqlite3"
            asyncio.run(run_seed(database_path))
            asyncio.run(run_seed(database_path))

            self.assertEqual(len(service.paths), 6)
            self.assertFalse(any(path.endswith("/surface") for path in service.paths))
            self.assertEqual(
                service.paths,
                [
                    "/api/packs/install",
                    f"/api/packs/{PACK_ID}/releases/{PACK_VERSION}/activate",
                    f"/api/packs/{PACK_ID}/releases/{PACK_VERSION}/activity-pool/entries/batch",
                ]
                * 2,
            )
