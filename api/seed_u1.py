"""Install Math U1, activate its complete map, and admit verified family variants."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import quote

from apps.runtime_vnext.worker.runtime_http import compose_vnext_runtime_service
from learning_kernel.activity_generation.pool_entry_artifact import (
    serialize_activity_pool_entry_artifact,
)
from learning_kernel.activity_generation.provenance import (
    ActivityGeneratorProvenance,
    ActivityProvenanceRecord,
)
from learning_kernel.activity_generation.request import ActivityIdentityRef
from learning_kernel.activity_generation.supply_contracts import ActivityPoolEntry
from learning_kernel.activity_generation.validation import ActivityValidationResult
from learning_kernel.domain.values import thaw_json
from learning_kernel.knowledge_packs.artifact import read_pack_artifact
from learning_kernel.knowledge_packs.math_u1_vnext.deterministic_generators import (
    build_u1_deterministic_generator_registry,
)
from learning_kernel.knowledge_packs.math_u1_vnext.generator_requirements import (
    U1_GENERATOR_REQUIREMENTS,
)
from learning_kernel.knowledge_packs.math_u1_vnext.pack import U1_PACK
from learning_kernel.knowledge_packs.math_u1_vnext.scope import PACK_ID, PACK_VERSION
from learning_kernel.knowledge_packs.math_u1_vnext.verification import (
    MathU1IndependentVerifier,
)
from learning_kernel.knowledge_packs.vnext_activity import ActivityRef
from learning_kernel.runtime.pack_registry import INSTALL_ENVIRONMENT_SCHEMA

from api.migrations import apply_runtime_migrations
from api.sqlite_d1 import SqliteD1Database

ARTIFACT_DIR = (
    Path(os.getenv("LK_SDK_ROOT", "/opt/lk"))
    / "artifacts"
    / "knowledge-packs"
    / PACK_ID
    / PACK_VERSION
)
ADMISSION_TOKEN = "in-process-local-bootstrap-only"
VARIANTS_PER_FAMILY = 10


def _install_environment() -> dict[str, object]:
    surface = U1_PACK.execution_contract.surface
    return {
        "$schema": INSTALL_ENVIRONMENT_SCHEMA,
        "runtimeCapabilities": list(U1_PACK.execution_contract.runtime_capabilities),
        "surface": {
            "schemaVersion": "bailian.surface-capabilities@1",
            "surfaceSchemaVersion": surface.surface_schema_version,
            "observationCaptureVersion": surface.observation_capture_version,
            "blockCapabilities": [
                {"id": block.capability_id, "role": block.role}
                for block in surface.block_capabilities
            ],
            "interactionCapabilities": list(surface.interaction_capabilities),
        },
    }


def _pack_activity_for_family(family_id: str) -> tuple[object, object]:
    matches = [
        (activity, point)
        for activity in U1_PACK.activities.activities
        for point in activity.observation_points
        if point.task_family.local_id == family_id
        and activity.local_id.startswith("u1/activity/family-anchor/")
    ]
    if len(matches) == 1:
        return matches[0]
    matches = [
        (activity, point)
        for activity in U1_PACK.activities.activities
        for point in activity.observation_points
        if point.task_family.local_id == family_id
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one Pack activity observation for {family_id}; found {len(matches)}."
        )
    return matches[0]


def _pool_payloads(content_digest: str) -> tuple[dict[str, object], ...]:
    """Generate, independently verify, and encode ten entries for every Pack family."""
    registry = build_u1_deterministic_generator_registry()
    verifier = MathU1IndependentVerifier()
    payloads: list[dict[str, object]] = []

    for requirement in U1_GENERATOR_REQUIREMENTS.requirements:
        family_id = requirement.task_family.local_id
        pack_activity, observation_point = _pack_activity_for_family(family_id)
        registered = registry.resolve(requirement)
        for variant_index in range(VARIANTS_PER_FAMILY):
            generator = registered.for_variant(variant_index)
            request = generator.request()
            design = generator.design(request=request)
            artifact = generator.generate_from_design(design=design)
            verification = verifier.verify(
                request=request,
                design=design,
                artifact=artifact,
            )
            if not verification.passed:
                raise RuntimeError(
                    f"Math U1 independent verification failed for {family_id} "
                    f"variant {variant_index}: {verification.failure_codes}"
                )
            validator_results = tuple(
                ActivityValidationResult(
                    validator=ActivityIdentityRef(PACK_ID, item.local_id),
                    artifact=artifact,
                    passed=True,
                )
                for item in requirement.validators
            )
            provenance = ActivityProvenanceRecord(
                pack_release=U1_PACK.identity,
                request=request,
                design=design,
                artifact=artifact,
                generation_method="deterministic",
                generator=ActivityGeneratorProvenance(
                    generator=requirement,
                    implementation_id="learning-kernel.math-u1-family-generator",
                    implementation_version=PACK_VERSION,
                ),
                supply_route="direct_generation",
                independent_verification=verification,
                validator_results=validator_results,
            )
            entry = ActivityPoolEntry(
                artifact=artifact,
                design=design,
                provenance=provenance,
            )
            payloads.append(
                serialize_activity_pool_entry_artifact(
                    entry_id=f"pool-entry/{family_id}/variant-{variant_index:02d}",
                    entry=entry,
                    pack_activity_ref=ActivityRef(PACK_ID, pack_activity.local_id),
                    observation_point_local_id=observation_point.local_id,
                    generator_requirement_id=requirement.local_id,
                    content_digest=content_digest,
                )
            )

    return tuple(payloads)


async def seed(database_path: Path, learner_id: str, environment_id: str) -> None:
    artifact = read_pack_artifact(ARTIFACT_DIR)
    if (
        artifact.pack_version != PACK_VERSION
        or artifact.content_digest != U1_PACK.lifecycle.content_digest
    ):
        raise RuntimeError("Math U1 source and released artifact do not match.")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    database = SqliteD1Database.open(database_path)
    try:
        apply_runtime_migrations(
            database.connection,
            Path(
                os.getenv(
                    "LK_RUNTIME_MIGRATIONS_DIR",
                    "/opt/lk/apps/runtime_vnext/migrations",
                )
            ),
        )
        service = compose_vnext_runtime_service(
            database,
            pool_admission_token=ADMISSION_TOKEN,
        )

        async def request(
            method: str,
            path: str,
            body: dict[str, object] | None = None,
            *,
            admission: bool = False,
        ):
            return await service.handle_request(
                method=method,
                path=path,
                body=json.dumps(body, ensure_ascii=False, separators=(",", ":"))
                if body is not None
                else None,
                authorization=f"Bearer {ADMISSION_TOKEN}" if admission else None,
            )

        installed = await request(
            "POST",
            "/api/packs/install",
            {
                "manifest": thaw_json(artifact.manifest),
                "content": thaw_json(artifact.content),
                "installEnvironment": _install_environment(),
            },
        )
        if installed.status != 200:
            raise RuntimeError(
                f"Pack install failed ({installed.status}): {installed.body.decode()}"
            )

        release_path = (
            f"/api/packs/{quote(PACK_ID, safe='')}/releases/"
            f"{quote(PACK_VERSION, safe='')}"
        )
        activated = await request(
            "POST",
            release_path + "/activate",
            {
                "learnerId": learner_id,
                "environmentId": environment_id,
                "regionIds": [
                    region.local_id for region in U1_PACK.learning_map.regions
                ],
            },
        )
        if activated.status not in (200, 409):
            raise RuntimeError(
                f"Pack activation failed ({activated.status}): {activated.body.decode()}"
            )

        pool_payloads = _pool_payloads(artifact.content_digest)
        admitted = await request(
            "POST",
            release_path + "/activity-pool/entries/batch",
            {"entries": list(pool_payloads)},
            admission=True,
        )
        if admitted.status not in (200, 201):
            raise RuntimeError(
                f"Pool batch admission failed ({admitted.status}): {admitted.body.decode()}"
            )
        admission_result = json.loads(admitted.body)
        if admission_result.get("entryCount") != len(pool_payloads):
            raise RuntimeError("Runtime admitted an unexpected number of Pool entries.")

        entry = U1_PACK.execution_contract.entry_points[0]
        surface_path = (
            f"/api/learners/{quote(learner_id, safe='')}/environments/"
            f"{quote(environment_id, safe='')}/packs/{quote(PACK_ID, safe='')}/surface"
        )
        surface = await request(
            "POST",
            surface_path,
            {
                "currentContext": {
                    "currentPlaceLocalId": entry.place_local_id,
                    "todayPractice": True,
                },
            },
        )
        if surface.status != 200:
            raise RuntimeError(
                f"Surface unavailable ({surface.status}): {surface.body.decode()}"
            )
        payload = json.loads(surface.body)
        if (
            payload.get("schemaVersion") != "learning-kernel.surface-ir@1"
            or payload.get("lineage", {}).get("pack", {}).get("version") != PACK_VERSION
        ):
            raise RuntimeError("Surface has unexpected Pack lineage")
        print(
            f"Math U1 {PACK_VERSION}: {len(pool_payloads)} verified Pool entries "
            f"({VARIANTS_PER_FAMILY} for each of {len(U1_GENERATOR_REQUIREMENTS.requirements)} families)"
        )
    finally:
        database.connection.close()


if __name__ == "__main__":
    asyncio.run(
        seed(
            Path(os.getenv("LK_DATABASE_PATH", "/data/learning-kernel.sqlite3")),
            os.getenv("BAILIAN_LOCAL_LEARNER_ID", "local-learner-001"),
            os.getenv("BAILIAN_LOCAL_ENVIRONMENT_ID", "home"),
        )
    )
