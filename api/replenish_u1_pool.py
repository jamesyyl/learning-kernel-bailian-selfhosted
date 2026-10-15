"""Continuously top up low-water Math U1 Families through validated Runtime admission."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import cast
from urllib.parse import quote

from apps.runtime_vnext.worker.runtime_http import compose_vnext_runtime_service
from learning_kernel.activity_generation.registry import GeneratorRegistry
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

from api.migrations import apply_runtime_migrations
from api.seed_u1 import (
    ADMISSION_TOKEN,
    COMPOUND_PRIMARY_FAMILY,
    COMPOUND_FAMILY_IDS,
    COMPOUND_VARIANT_START,
    ARTIFACT_DIR,
    GENERATOR_IMPLEMENTATION_VERSION,
    _pool_payload_for_variant,
)
from api.sqlite_d1 import SqliteD1Database

REFILL_BELOW_AVAILABLE = 4
REFILL_MAX_ENTRIES_PER_FAMILY = 10
REFILL_VARIANT_SCAN_LIMIT = 64
DEFAULT_INTERVAL_SECONDS = 2.0
_VARIANT_SUFFIX = re.compile(r"/variant-(\d+)$")


async def _rows(
    database: SqliteD1Database, query: str, values: tuple[object, ...]
) -> list[dict[str, object]]:
    result = await database.prepare(query).bind(*values).all()
    if not isinstance(result, dict) or result.get("success") is not True:
        raise RuntimeError(
            "SQLite Runtime returned an invalid Pool refill query result."
        )
    rows = result.get("results")
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError("SQLite Runtime returned malformed Pool refill rows.")
    return cast(list[dict[str, object]], rows)


def _family_id_for_activity(activity_id: str) -> str | None:
    prefix = "generated/"
    suffix = "/variant-"
    if not activity_id.startswith(prefix) or suffix not in activity_id:
        return None
    family_id, variant = activity_id[len(prefix) :].rsplit(suffix, 1)
    if not variant.isdigit():
        return None
    return family_id


def _pool_prompt(canonical_json: str) -> str:
    payload = json.loads(canonical_json)
    generated = payload.get("generatedActivityArtifact", {})
    learner_payload = generated.get("learner_payload", {})
    prompt = learner_payload.get("prompt")
    if type(prompt) is not str or not prompt:
        raise RuntimeError("Admitted Math U1 Pool entry has no learner prompt.")
    return prompt


def _availability_signature(
    pool_activity_ids: set[str],
    scopes: tuple[tuple[str, str], ...],
    issued_by_scope: dict[tuple[str, str], set[str]],
    family_id: str,
) -> str:
    family_pool = sorted(
        activity_id
        for activity_id in pool_activity_ids
        if _family_id_for_activity(activity_id) == family_id
    )
    learner_issued = [
        [
            learner_id,
            environment_id,
            sorted(
                activity_id
                for activity_id in issued_by_scope.get(
                    (learner_id, environment_id), set()
                )
                if _family_id_for_activity(activity_id) == family_id
            ),
        ]
        for learner_id, environment_id in scopes
    ]
    material = json.dumps([family_pool, learner_issued], separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def replenish_once(
    database: SqliteD1Database,
    service: object,
    content_digest: str,
    registry: GeneratorRegistry,
    verifier: MathU1IndependentVerifier,
    *,
    no_supply_signatures: dict[str, str] | None = None,
) -> dict[str, object]:
    """Generate unique low-water variants, verify them, then admit through Runtime."""
    release = (
        await database.prepare(
            """
        SELECT 1 AS installed FROM vnext_pack_releases
        WHERE pack_id = ? AND pack_version = ? AND content_digest = ?
        """
        )
        .bind(PACK_ID, PACK_VERSION, content_digest)
        .first("installed")
    )
    if release is None:
        return {"status": "pack-not-installed", "entriesAdded": 0}

    scope_rows = await _rows(
        database,
        """
        SELECT learner_id, environment_id FROM vnext_pack_activation_state
        WHERE pack_id = ? AND pack_version = ? AND content_digest = ?
        ORDER BY learner_id, environment_id
        """,
        (PACK_ID, PACK_VERSION, content_digest),
    )
    scopes = tuple(
        sorted(
            {(str(row["learner_id"]), str(row["environment_id"])) for row in scope_rows}
        )
    )
    if not scopes:
        return {"status": "no-active-learners", "entriesAdded": 0}

    pool_rows = await _rows(
        database,
        """
        SELECT entry_id, artifact_id, task_family_id, canonical_json
        FROM vnext_activity_pool_entries
        WHERE pack_id = ? AND pack_version = ? AND content_digest = ?
        ORDER BY task_family_id, artifact_id
        """,
        (PACK_ID, PACK_VERSION, content_digest),
    )
    pool_activity_ids: set[str] = set()
    prompts_by_family: dict[str, set[str]] = {}
    entry_ids: set[str] = set()
    max_variant_by_family: dict[str, int] = {}
    for row in pool_rows:
        entry_id = str(row["entry_id"])
        activity_id = str(row["artifact_id"])
        family_id = str(row["task_family_id"])
        # Supporting observations are not entry points. Counting them as
        # independently selectable supply masks depleted ordinary Families.
        if not (
            family_id in COMPOUND_FAMILY_IDS
            and family_id != COMPOUND_PRIMARY_FAMILY
            and (match := _VARIANT_SUFFIX.search(activity_id)) is not None
            and int(match.group(1)) >= COMPOUND_VARIANT_START
        ):
            pool_activity_ids.add(activity_id)
        entry_ids.add(entry_id)
        prompts_by_family.setdefault(family_id, set()).add(
            _pool_prompt(str(row["canonical_json"]))
        )
        match = _VARIANT_SUFFIX.search(activity_id)
        if match is not None:
            variant = int(match.group(1))
            # Secondary compound pieces may coexist with ordinary single-step
            # Family supply. Never let reserved 1000+ compound indices suppress
            # that Family's normal refill progression.
            if (family_id == COMPOUND_PRIMARY_FAMILY) == (
                variant >= COMPOUND_VARIANT_START
            ):
                max_variant_by_family[family_id] = max(
                    max_variant_by_family.get(family_id, -1), variant
                )

    issued_rows = await _rows(
        database,
        """
        SELECT learner_id, environment_id, activity_id
        FROM vnext_issued_activity_bindings
        WHERE pack_id = ? AND pack_version = ? AND content_digest = ?
        """,
        (PACK_ID, PACK_VERSION, content_digest),
    )
    issued_by_scope: dict[tuple[str, str], set[str]] = {}
    for row in issued_rows:
        scope = (str(row["learner_id"]), str(row["environment_id"]))
        issued_by_scope.setdefault(scope, set()).add(str(row["activity_id"]))

    additions: list[dict[str, object]] = []
    added_by_family: dict[str, int] = {}
    total_variants_scanned = 0
    blocked = no_supply_signatures if no_supply_signatures is not None else {}
    for requirement in U1_GENERATOR_REQUIREMENTS.requirements:
        family_id = requirement.task_family.local_id
        family_pool = {
            activity_id
            for activity_id in pool_activity_ids
            if _family_id_for_activity(activity_id) == family_id
        }
        remaining_by_scope = [
            len(family_pool - issued_by_scope.get(scope, set())) for scope in scopes
        ]
        minimum_remaining = min(remaining_by_scope, default=0)
        if minimum_remaining > REFILL_BELOW_AVAILABLE:
            blocked.pop(family_id, None)
            continue

        signature = _availability_signature(
            pool_activity_ids, scopes, issued_by_scope, family_id
        )
        if blocked.get(family_id) == signature:
            continue

        known_ids = set(family_pool)
        known_prompts = prompts_by_family.setdefault(family_id, set())
        start_variant = max_variant_by_family.get(family_id, -1) + 1
        family_additions = 0
        for variant_index in range(
            start_variant, start_variant + REFILL_VARIANT_SCAN_LIMIT
        ):
            if family_additions >= REFILL_MAX_ENTRIES_PER_FAMILY:
                break
            if (
                minimum_remaining + family_additions
                >= REFILL_BELOW_AVAILABLE + REFILL_MAX_ENTRIES_PER_FAMILY
            ):
                break
            total_variants_scanned += 1
            payload = _pool_payload_for_variant(
                content_digest=content_digest,
                requirement=requirement,
                variant_index=variant_index,
                registry=registry,
                verifier=verifier,
            )
            generated = cast(dict[str, object], payload["generatedActivityArtifact"])
            activity_id = str(generated["local_id"])
            prompt = str(
                cast(dict[str, object], generated["learner_payload"])["prompt"]
            )
            entry_id = str(payload["entryId"])
            if (
                activity_id in known_ids
                or prompt in known_prompts
                or entry_id in entry_ids
            ):
                continue
            additions.append(payload)
            family_additions += 1
            known_ids.add(activity_id)
            known_prompts.add(prompt)
            entry_ids.add(entry_id)
            pool_activity_ids.add(activity_id)
        if family_additions:
            added_by_family[family_id] = family_additions
            blocked.pop(family_id, None)
        else:
            blocked[family_id] = signature

    if not additions:
        return {
            "status": "pool-sufficient-or-generator-domain-exhausted",
            "entriesAdded": 0,
        }

    release_path = (
        f"/api/packs/{quote(PACK_ID, safe='')}/releases/{quote(PACK_VERSION, safe='')}"
    )
    response = await service.handle_request(
        method="POST",
        path=release_path + "/activity-pool/entries/batch",
        body=json.dumps(
            {"entries": additions}, ensure_ascii=False, separators=(",", ":")
        ),
        authorization=f"Bearer {ADMISSION_TOKEN}",
    )
    if response.status not in (200, 201):
        raise RuntimeError(
            f"Incremental Pool admission failed ({response.status}): {response.body.decode()}"
        )
    admitted = json.loads(response.body)
    if admitted.get("entryCount") != len(additions):
        raise RuntimeError(
            "Runtime admitted an unexpected number of refill Pool entries."
        )
    return {
        "status": "refilled",
        "entriesAdded": len(additions),
        "families": added_by_family,
        "scopesChecked": len(scopes),
        "variantsScanned": total_variants_scanned,
        "generatorImplementationVersion": GENERATOR_IMPLEMENTATION_VERSION,
    }


async def _run_watch(
    database_path: Path,
    migration_dir: Path,
    interval_seconds: float,
    *,
    once: bool,
) -> None:
    artifact = read_pack_artifact(ARTIFACT_DIR)
    if (
        artifact.pack_version != PACK_VERSION
        or artifact.content_digest != U1_PACK.lifecycle.content_digest
    ):
        raise RuntimeError("Math U1 source and released artifact do not match.")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    database = SqliteD1Database.open(database_path)
    try:
        apply_runtime_migrations(database.connection, migration_dir)
        service = compose_vnext_runtime_service(
            database,
            pool_admission_token=ADMISSION_TOKEN,
        )
        registry = build_u1_deterministic_generator_registry()
        verifier = MathU1IndependentVerifier()
        no_supply_signatures: dict[str, str] = {}
        while True:
            try:
                result = await replenish_once(
                    database,
                    service,
                    artifact.content_digest,
                    registry,
                    verifier,
                    no_supply_signatures=no_supply_signatures,
                )
                if once:
                    print(
                        json.dumps(result, ensure_ascii=False, sort_keys=True),
                        flush=True,
                    )
                    return
                if result.get("entriesAdded", 0):
                    print(
                        json.dumps(result, ensure_ascii=False, sort_keys=True),
                        flush=True,
                    )
            except Exception as error:  # Keep the independent supplier alive through transient SQLite busy windows.
                print(
                    f"Math U1 Pool refiller retryable error: {type(error).__name__}: {error}",
                    file=sys.stderr,
                    flush=True,
                )
            await asyncio.sleep(interval_seconds)
    finally:
        database.connection.close()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        dest="once",
        action="store_true",
        help="run one low-water scan and exit",
    )
    mode.add_argument(
        "--watch",
        dest="once",
        action="store_false",
        help="run as an independent background refiller",
    )
    parser.set_defaults(once=False)
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(
            os.getenv("U1_POOL_REFILL_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    if args.interval_seconds <= 0:
        raise SystemExit("--interval-seconds must be greater than zero")
    asyncio.run(
        _run_watch(
            Path(os.getenv("LK_DATABASE_PATH", "/data/learning-kernel.sqlite3")),
            Path(
                os.getenv(
                    "LK_RUNTIME_MIGRATIONS_DIR",
                    "/opt/lk/apps/runtime_vnext/migrations",
                )
            ),
            args.interval_seconds,
            once=args.once,
        )
    )


if __name__ == "__main__":
    main()
