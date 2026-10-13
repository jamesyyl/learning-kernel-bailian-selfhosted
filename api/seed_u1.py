"""Install one verified Math U1 activity for private local development.

Run from the Runtime container with ``python -m api.seed_u1``. Pack controls and
Pool admission are invoked in-process; the browser-facing HTTP allowlist stays
limited to Surface and raw observations.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import quote

from apps.runtime_vnext.worker.runtime_http import compose_vnext_runtime_service
from learning_kernel.activity_generation.artifact import GeneratedActivityArtifact
from learning_kernel.activity_generation.design import (
    ActivityDesignSpec,
    ActivityMechanismCandidate,
    ActivityVariationPolicy,
)
from learning_kernel.activity_generation.pool_entry_artifact import (
    serialize_activity_pool_entry_artifact,
)
from learning_kernel.activity_generation.provenance import (
    ActivityGeneratorProvenance,
    ActivityProvenanceRecord,
)
from learning_kernel.activity_generation.request import (
    ActivityChallengeSelection,
    ActivityIdentityRef,
    ActivityRequest,
    ActivityVariationConstraint,
)
from learning_kernel.activity_generation.supply_contracts import ActivityPoolEntry
from learning_kernel.activity_generation.validation import ActivityValidationResult
from learning_kernel.activity_generation.verification import (
    ActivityIndependentVerificationResult,
)
from learning_kernel.domain.values import thaw_json
from learning_kernel.knowledge_packs.artifact import read_pack_artifact
from learning_kernel.knowledge_packs.math_u1_vnext.challenge_profiles import (
    build_u1_challenge_profile,
)
from learning_kernel.knowledge_packs.math_u1_vnext.deterministic_generators import (
    DirectPrimeCompositeGenerator,
    TransferPrimeCompositeGenerator,
)
from learning_kernel.knowledge_packs.math_u1_vnext.generator_requirements import (
    U1_GENERATOR_REQUIREMENTS,
)
from learning_kernel.knowledge_packs.math_u1_vnext.pack import U1_PACK
from learning_kernel.knowledge_packs.math_u1_vnext.runtime_contract import (
    U1_EXECUTION_CONTRACT,
)
from learning_kernel.knowledge_packs.math_u1_vnext.u1_1 import (
    FAMILY_CLASSIFICATION_TRANSFER,
    FAMILY_DIRECT_CLASSIFICATION,
    FAMILY_DIVISIBILITY_SCREEN,
)
from learning_kernel.knowledge_packs.math_u1_vnext.verification import (
    MathU1IndependentVerifier,
)
from learning_kernel.knowledge_packs.vnext_activity import ActivityRef
from learning_kernel.knowledge_packs.vnext_task_family import (
    ChallengeLevelSelection,
    ChallengeProfile,
)
from learning_kernel.runtime.pack_registry import INSTALL_ENVIRONMENT_SCHEMA

from api.migrations import apply_runtime_migrations
from api.sqlite_d1 import SqliteD1Database

PACK_ID = U1_PACK.pack_id
PACK_VERSION = U1_PACK.identity.pack_version
ARTIFACT_DIR = (
    Path(os.getenv("LK_SDK_ROOT", "/opt/lk"))
    / "artifacts"
    / "knowledge-packs"
    / PACK_ID
    / PACK_VERSION
)
ADMISSION_TOKEN = "in-process-local-bootstrap-only"


def _install_environment() -> dict[str, object]:
    surface = U1_EXECUTION_CONTRACT.surface
    return {
        "$schema": INSTALL_ENVIRONMENT_SCHEMA,
        "runtimeCapabilities": list(U1_EXECUTION_CONTRACT.runtime_capabilities),
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


def _pool_payloads(content_digest: str) -> tuple[dict[str, object], ...]:
    classification = FAMILY_DIRECT_CLASSIFICATION
    request = ActivityRequest(
        observable_capability=classification.primary_capability,
        task_family=classification,
        challenge_profile=build_u1_challenge_profile(
            classification.local_id,
            {
                "u1-1/challenge/evidence-directness": "partial",
                "u1-1/challenge/number-familiarity": "within-20-core",
            },
        ),
    )
    generator = DirectPrimeCompositeGenerator()
    design = generator.design(
        request=request, variation_policy=ActivityVariationPolicy(intent="fluency")
    )
    artifact = generator.generate_from_design(design=design)
    verification = MathU1IndependentVerifier().verify(
        request=request, design=design, artifact=artifact
    )
    if not verification.passed:
        raise RuntimeError("U1 classification verification failed")
    requirement = next(
        item
        for item in U1_GENERATOR_REQUIREMENTS.requirements
        if item.task_family == classification.ref
    )
    validator_results = tuple(
        ActivityValidationResult(
            validator=ActivityIdentityRef(PACK_ID, item.local_id),
            artifact=ActivityIdentityRef(PACK_ID, artifact.local_id),
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
            implementation_id="selfhosted.local-u1-bootstrap",
            implementation_version="1.0.0",
        ),
        supply_route="direct_generation",
        independent_verification=verification,
        validator_results=validator_results,
    )
    first = ActivityPoolEntry(artifact=artifact, design=design, provenance=provenance)

    divisibility = FAMILY_DIVISIBILITY_SCREEN
    second_request = ActivityRequest(
        observable_capability=divisibility.primary_capability,
        task_family=divisibility,
        challenge_profile=ChallengeProfile(
            task_family=divisibility,
            selections=(
                ChallengeLevelSelection(
                    "u1-1/challenge/number-familiarity", "within-20-core"
                ),
            ),
        ),
    )
    policy = ActivityVariationPolicy(intent="fluency")
    second_design = ActivityDesignSpec(
        request=second_request,
        candidate=ActivityMechanismCandidate(
            local_id="design/selfhosted-divisibility-15",
            observable_capability=divisibility.primary_capability,
            task_family=divisibility.ref,
            mechanism="check-divisibility-by-declared-small-primes",
            required_operations=("check divisibility by 2, 3, and 5",),
            representation_intent="integer-selection",
            variation_policy=policy,
        ),
    )
    second_artifact = GeneratedActivityArtifact(
        pack_id=PACK_ID,
        local_id="generated/selfhosted-divisibility-15",
        observable_capability=ActivityIdentityRef(
            PACK_ID, divisibility.primary_capability.local_id
        ),
        task_family=ActivityIdentityRef(PACK_ID, divisibility.local_id),
        challenge_selections=(
            ActivityChallengeSelection(
                "u1-1/challenge/number-familiarity", "within-20-core"
            ),
        ),
        variation_selections=(),
        learner_payload={
            "prompt": "從 2、3、5 中，選出能整除 15 的數。",
            "numbers": [2, 3, 5],
        },
        response_specification={
            "kind": "integer-selection",
            "minSelections": 1,
            "maxSelections": 2,
        },
        validation_payload={"correct_response": [3, 5]},
    )
    computed = [number for number in (2, 3, 5) if 15 % number == 0]
    if (
        computed != [3, 5]
        or second_artifact.validation_payload.get("correct_response") != tuple(computed)
        or not all(
            str(number) in second_artifact.learner_payload["prompt"]
            for number in (2, 3, 5)
        )
    ):
        raise RuntimeError("U1 divisibility verification failed")
    second_requirement = next(
        item
        for item in U1_GENERATOR_REQUIREMENTS.requirements
        if item.task_family == divisibility.ref
    )
    second_provenance = ActivityProvenanceRecord(
        pack_release=U1_PACK.identity,
        request=second_request,
        design=second_design,
        artifact=second_artifact,
        generation_method="deterministic",
        generator=ActivityGeneratorProvenance(
            generator=second_requirement,
            implementation_id="selfhosted.local-u1-bootstrap",
            implementation_version="1.0.0",
        ),
        supply_route="direct_generation",
        independent_verification=ActivityIndependentVerificationResult(
            verifier=ActivityIdentityRef(
                PACK_ID, "u1/activity-verifier/selfhosted-divisibility"
            ),
            artifact=ActivityIdentityRef(PACK_ID, second_artifact.local_id),
            passed=True,
        ),
        validator_results=tuple(
            ActivityValidationResult(
                validator=ActivityIdentityRef(PACK_ID, item.local_id),
                artifact=ActivityIdentityRef(PACK_ID, second_artifact.local_id),
                passed=True,
            )
            for item in second_requirement.validators
        ),
    )
    second = ActivityPoolEntry(
        artifact=second_artifact, design=second_design, provenance=second_provenance
    )

    transfer = FAMILY_CLASSIFICATION_TRANSFER
    transfer_request = ActivityRequest(
        observable_capability=transfer.primary_capability,
        task_family=transfer,
        challenge_profile=build_u1_challenge_profile(
            transfer.local_id,
            {
                "u1-1/challenge/transfer-distance": "reasoning",
                "u1-1/challenge/number-familiarity": "within-20-core",
            },
        ),
        variation_constraints=(
            ActivityVariationConstraint(
                "u1-1/variation/response-quantity",
                ("set",),
            ),
        ),
    )
    transfer_generator = TransferPrimeCompositeGenerator()
    transfer_design = transfer_generator.design(
        request=transfer_request,
        variation_policy=ActivityVariationPolicy(intent="fluency"),
    )
    transfer_artifact = transfer_generator.generate_from_design(design=transfer_design)
    transfer_verification = MathU1IndependentVerifier().verify(
        request=transfer_request,
        design=transfer_design,
        artifact=transfer_artifact,
    )
    if not transfer_verification.passed:
        raise RuntimeError("U1 classification transfer verification failed")
    transfer_requirement = next(
        item
        for item in U1_GENERATOR_REQUIREMENTS.requirements
        if item.task_family == transfer.ref
    )
    transfer_entry = ActivityPoolEntry(
        artifact=transfer_artifact,
        design=transfer_design,
        provenance=ActivityProvenanceRecord(
            pack_release=U1_PACK.identity,
            request=transfer_request,
            design=transfer_design,
            artifact=transfer_artifact,
            generation_method="deterministic",
            generator=ActivityGeneratorProvenance(
                generator=transfer_requirement,
                implementation_id="selfhosted.local-u1-transfer",
                implementation_version="1.0.0",
            ),
            supply_route="direct_generation",
            independent_verification=transfer_verification,
            validator_results=tuple(
                ActivityValidationResult(
                    validator=ActivityIdentityRef(PACK_ID, item.local_id),
                    artifact=ActivityIdentityRef(PACK_ID, transfer_artifact.local_id),
                    passed=True,
                )
                for item in transfer_requirement.validators
            ),
        ),
    )
    entries = []
    for entry_id, entry, family, req in (
        ("pool-entry/selfhosted-classification-1", first, classification, requirement),
        (
            "pool-entry/selfhosted-divisibility-1",
            second,
            divisibility,
            second_requirement,
        ),
        (
            "pool-entry/selfhosted-classification-transfer-1",
            transfer_entry,
            transfer,
            transfer_requirement,
        ),
    ):
        activity, point = next(
            (activity, point)
            for activity in U1_PACK.activities.activities
            for point in activity.observation_points
            if point.task_family == family.ref
            and (
                family != classification
                or point.capability == family.primary_capability
            )
            and (
                family != divisibility
                or activity.local_id == "u1/activity/prime-composite-17-15"
            )
        )
        entries.append(
            serialize_activity_pool_entry_artifact(
                entry_id=entry_id,
                entry=entry,
                pack_activity_ref=ActivityRef(PACK_ID, activity.local_id),
                observation_point_local_id=point.local_id,
                generator_requirement_id=req.local_id,
                content_digest=content_digest,
            )
        )
    return tuple(entries)


async def seed(database_path: Path, learner_id: str, environment_id: str) -> None:
    artifact = read_pack_artifact(ARTIFACT_DIR)
    db = SqliteD1Database.open(database_path)
    try:
        apply_runtime_migrations(
            db.connection,
            Path(
                os.getenv(
                    "LK_RUNTIME_MIGRATIONS_DIR", "/opt/lk/apps/runtime_vnext/migrations"
                )
            ),
        )
        service = compose_vnext_runtime_service(
            db, pool_admission_token=ADMISSION_TOKEN
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

        base = f"/api/packs/{quote(PACK_ID, safe='')}/releases/{quote(PACK_VERSION, safe='')}"
        activated = await request(
            "POST",
            base + "/activate",
            {
                "learnerId": learner_id,
                "environmentId": environment_id,
                "regionIds": [U1_EXECUTION_CONTRACT.entry_points[0].region_id],
            },
        )
        if activated.status not in (200, 409):
            raise RuntimeError(
                f"Pack activation failed ({activated.status}): {activated.body.decode()}"
            )

        for payload in _pool_payloads(artifact.content_digest):
            admitted = await request(
                "POST", base + "/activity-pool/entries", payload, admission=True
            )
            if admitted.status not in (200, 201):
                raise RuntimeError(
                    f"Pool admission failed ({admitted.status}): {admitted.body.decode()}"
                )

        surface_path = (
            f"/api/learners/{quote(learner_id, safe='')}/environments/"
            f"{quote(environment_id, safe='')}/packs/{quote(PACK_ID, safe='')}/surface"
        )
        surface = await request(
            "POST",
            surface_path,
            {
                "currentContext": {
                    "currentPlaceLocalId": U1_EXECUTION_CONTRACT.entry_points[
                        0
                    ].place_local_id,
                    "todayPractice": True,
                },
            },
        )
        if surface.status != 200:
            raise RuntimeError(
                f"Surface unavailable ({surface.status}): {surface.body.decode()}"
            )
        payload = json.loads(surface.body)
        pack = payload["lineage"]["pack"]
        if (
            payload.get("schemaVersion") != "learning-kernel.surface-ir@1"
            or pack["version"] != PACK_VERSION
        ):
            raise RuntimeError("Surface has unexpected Pack lineage")
        print(f"Math U1 {PACK_VERSION} ready for {learner_id}/{environment_id}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(
        seed(
            Path(os.getenv("LK_DATABASE_PATH", "/data/learning-kernel.sqlite3")),
            os.getenv("BAILIAN_LOCAL_LEARNER_ID", "local-learner-001"),
            os.getenv("BAILIAN_LOCAL_ENVIRONMENT_ID", "home"),
        )
    )
