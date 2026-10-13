"""Build a Pack-derived Math U1 supply coverage matrix.

Run with Python 3.12 from the repository root. The report includes the immutable
Pack graph, declared generation requirements, concrete generator registrations,
the seed's actual Pool payloads, and the Surface response capabilities rendered
by Bailian. It deliberately does not serialize validation payloads or answers.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SDK_ROOT = Path(os.environ.get("LK_SDK_ROOT", ROOT / "vendor" / "learning-kernel-sdk"))
sys.path[:0] = [str(ROOT), str(SDK_ROOT)]
os.environ.setdefault("LK_SDK_ROOT", str(SDK_ROOT))

from learning_kernel.knowledge_packs.artifact import read_pack_artifact  # noqa: E402
from learning_kernel.knowledge_packs.math_u1_vnext.activities import (  # noqa: E402
    U1_FAMILY_ANCHOR_ACTIVITIES,
    U1_FIXED_ACTIVITIES,
)
from learning_kernel.knowledge_packs.math_u1_vnext.deterministic_generators import (  # noqa: E402
    _DETERMINISTIC_GENERATORS,
    build_u1_deterministic_generator_registry,
)
from learning_kernel.knowledge_packs.math_u1_vnext.pack import (  # noqa: E402
    U1_VALIDATED_PACK,
)

from api.seed_u1 import ARTIFACT_DIR, _pool_payloads  # noqa: E402


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            field.name: _plain(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_plain(item) for item in value]
    return value


def _local_id(value: Any) -> str | None:
    return getattr(value, "local_id", None)


def _build_matrix(trace_path: Path | None) -> dict[str, Any]:
    pack = U1_VALIDATED_PACK
    artifact = read_pack_artifact(ARTIFACT_DIR)
    pool_payloads = _pool_payloads(artifact.content_digest)
    runtime_trace = (
        json.loads(trace_path.read_text(encoding="utf-8"))
        if trace_path is not None and trace_path.exists()
        else None
    )
    trace_family_ids = (
        {
            item["taskFamilyId"]
            for item in runtime_trace.get("trace", [])
            if isinstance(item.get("taskFamilyId"), str)
        }
        if isinstance(runtime_trace, dict)
        else set()
    )
    map_trace_family_ids = (
        set(runtime_trace.get("taskFamiliesSelectedFromMap", []))
        if isinstance(runtime_trace, dict)
        else set()
    )
    exploration_trace_family_ids = (
        {
            item["taskFamilyId"]
            for item in runtime_trace.get("familyExplorationTrace", [])
            if isinstance(item.get("taskFamilyId"), str)
        }
        if isinstance(runtime_trace, dict)
        else set()
    )
    places = {item.local_id: item for item in pack.learning_map.places}
    roads = {item.local_id: item for item in pack.learning_map.roads}
    regions = {
        item.local_id: {
            "id": item.local_id,
            "title": item.title,
            "placeIds": [ref.local_id for ref in item.places],
        }
        for item in pack.learning_map.regions
    }
    place_regions = {
        ref.local_id: region_id
        for region_id, region in ((key, value) for key, value in regions.items())
        for ref in pack.learning_map.regions[
            next(
                index
                for index, candidate in enumerate(pack.learning_map.regions)
                if candidate.local_id == region_id
            )
        ].places
    }

    requirement_by_family = {
        item.task_family.local_id: item
        for item in pack.generator_requirements.requirements
    }
    family_anchor_ids = {
        item.local_id for item in U1_FAMILY_ANCHOR_ACTIVITIES.activities
    }
    fixed_activities: dict[str, list[dict[str, str]]] = {}
    family_anchors: dict[str, list[dict[str, str]]] = {}
    activities = []
    for activity in pack.activities.activities:
        observations = []
        for point in activity.observation_points:
            family_id = point.task_family.local_id
            observation = {
                "id": point.local_id,
                "taskFamilyId": family_id,
                "capabilityId": point.capability.local_id,
            }
            observations.append(observation)
            destination = (
                family_anchors
                if activity.local_id in family_anchor_ids
                else fixed_activities
            )
            destination.setdefault(family_id, []).append(
                {"activityId": activity.local_id, "observationPointId": point.local_id}
            )
        activities.append(
            {
                "id": activity.local_id,
                "title": activity.title,
                "kind": (
                    "family-anchor"
                    if activity.local_id in family_anchor_ids
                    else "reviewed-fixed"
                ),
                "observationPoints": observations,
            }
        )

    generator_registry = build_u1_deterministic_generator_registry()
    generator_by_family = {
        requirement.task_family.local_id: type(
            generator_registry.resolve(requirement)
        ).__name__
        for requirement in pack.generator_requirements.requirements
    }
    pool_by_family: dict[str, list[dict[str, Any]]] = {}
    for payload in pool_payloads:
        generated = payload["generatedActivityArtifact"]
        family_id = generated["task_family"]["local_id"]
        pool_by_family.setdefault(family_id, []).append(
            {
                "entryId": payload["entryId"],
                "generatedActivityId": generated["local_id"],
                "packActivityId": payload["packActivityRef"]["localId"],
                "observationPointId": payload["observationPointId"],
                "responseKind": generated["response_specification"]["kind"],
                "generationMethod": payload["activityProvenanceRecord"].get(
                    "generationMethod"
                ),
                "implementationId": payload["activityProvenanceRecord"]
                .get("generator", {})
                .get("implementation_id"),
                "verificationStatus": payload["activityProvenanceRecord"]
                .get("independentVerification", {})
                .get("passed"),
                "learnerPayload": generated["learner_payload"],
            }
        )

    app_source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    response_match = re.search(
        r"lkResponseBlock\s*=\s*blocks\.find\(\(block\)\s*=>\s*\[(.*?)\]\.includes\(block\.capability\)",
        app_source,
        flags=re.DOTALL,
    )
    rendered_response_capabilities = (
        re.findall(r"[\"'](response\.[^\"']+@1)[\"']", response_match.group(1))
        if response_match
        else []
    )
    declared_response_capabilities = [
        item.capability_id
        for item in pack.execution_contract.surface.block_capabilities
        if item.role == "response"
    ]

    family_rows = []
    for family in pack.task_families.families:
        capability = next(
            item
            for item in pack.capabilities.capabilities
            if item.ref == family.primary_capability
        )
        map_refs = _plain(capability.map_refs)
        related_place_ids: set[str] = set()
        related_road_ids: set[str] = set()
        for map_ref in capability.map_refs:
            if map_ref.kind == "place" and map_ref.local_id in places:
                related_place_ids.add(map_ref.local_id)
            elif map_ref.kind == "road" and map_ref.local_id in roads:
                related_road_ids.add(map_ref.local_id)
                road = roads[map_ref.local_id]
                related_place_ids.update(
                    (road.from_place.local_id, road.to_place.local_id)
                )
        requirement = requirement_by_family.get(family.local_id)
        entries = pool_by_family.get(family.local_id, [])
        declared_capability_ids = [
            "response.single-choice@1"
            if item["responseKind"] == "classification"
            else "response.multi-choice@1"
            if item["responseKind"] in {"integer-selection", "multi-classification"}
            else "response.math@1"
            if item["responseKind"] in {"integer", "structured-factorization"}
            else "response.text@1"
            if item["responseKind"] == "text"
            else "response.math@1"
            for item in entries
        ]
        missing_renderer = sorted(
            set(declared_capability_ids) - set(rendered_response_capabilities)
        )
        place_ids = sorted(related_place_ids)
        region_ids = sorted(
            {place_regions[item] for item in place_ids if item in place_regions}
        )
        family_rows.append(
            {
                "id": family.local_id,
                "title": family.title,
                "regionIds": region_ids,
                "placeIds": place_ids,
                "roadIds": sorted(related_road_ids),
                "capability": {
                    "id": capability.local_id,
                    "statement": capability.statement,
                    "demonstration": capability.demonstration,
                    "mapRefs": map_refs,
                },
                "observationPurpose": family.observation_purpose,
                "invariantCore": list(family.invariant_core),
                "variationDimensions": _plain(family.variation_dimensions),
                "challengeDimensions": _plain(family.challenge_dimensions),
                "navigationUses": _plain(family.navigation_uses),
                "generatorRequirement": _plain(requirement) if requirement else None,
                "concreteGeneratorClass": generator_by_family.get(family.local_id),
                "reviewedFixedActivityObservations": fixed_activities.get(
                    family.local_id, []
                ),
                "familyAnchorObservations": family_anchors.get(family.local_id, []),
                "packActivityObservations": [
                    *fixed_activities.get(family.local_id, []),
                    *family_anchors.get(family.local_id, []),
                ],
                "poolEntries": entries,
                "generatedPoolEntryCount": len(entries),
                "distinctGeneratedActivityCount": len(
                    {item["generatedActivityId"] for item in entries}
                ),
                "distinctQuestionCount": len(
                    {
                        json.dumps(
                            item["learnerPayload"], ensure_ascii=False, sort_keys=True
                        )
                        for item in entries
                    }
                ),
                "surfaceCandidateGenerated": bool(entries),
                "responseCapabilitiesDeclaredForPack": declared_response_capabilities,
                "responseCapabilitiesRenderedByBailian": rendered_response_capabilities,
                "missingRendererCapabilitiesForSeededEntries": missing_renderer,
                "trustedEvidenceContractReady": bool(entries) and not missing_renderer,
                "canonicalDecisionObservedInTenStepTrace": family.local_id
                in trace_family_ids,
                "trustedEvidenceObservedInTenStepTrace": family.local_id
                in trace_family_ids,
                "canonicalDecisionObservedFromMapPlaceTrace": family.local_id
                in map_trace_family_ids,
                "trustedEvidenceObservedFromMapPlaceTrace": family.local_id
                in map_trace_family_ids,
                "canonicalSurfaceSelectedByMapExploration": family.local_id
                in exploration_trace_family_ids,
                "trustedEvidencePersistedFromMapExploration": family.local_id
                in exploration_trace_family_ids,
                "coverageBlockers": [
                    reason
                    for reason, condition in (
                        (
                            "no generator registered",
                            family.local_id not in generator_by_family,
                        ),
                        (
                            "no Pack Activity observation anchor",
                            family.local_id not in fixed_activities
                            and family.local_id not in family_anchors,
                        ),
                        ("no generated Activity Pool candidate", not entries),
                        (
                            "Surface response has no Bailian renderer",
                            bool(missing_renderer),
                        ),
                    )
                    if condition
                ],
            }
        )

    return {
        "reportSchema": "math-u1-supply-matrix@1",
        "phase": "current-implementation",
        "pack": {
            "id": pack.pack_id,
            "version": pack.identity.pack_version,
            "releaseKey": pack.release_key,
            "contentDigest": artifact.content_digest,
        },
        "counts": {
            "regions": len(regions),
            "places": len(places),
            "roads": len(roads),
            "relations": len(pack.learning_map.relations),
            "junctions": len(pack.learning_map.junctions),
            "capabilities": len(pack.capabilities.capabilities),
            "taskFamilies": len(pack.task_families.families),
            "generatorRequirements": len(pack.generator_requirements.requirements),
            "registeredGeneratorImplementations": len(generator_by_family),
            "registeredGeneratorClasses": len(set(generator_by_family.values())),
            "legacyGeneratorClassesRetained": len(
                {
                    type(generator).__name__
                    for _family, generator in _DETERMINISTIC_GENERATORS
                }
            ),
            "reviewedFixedActivities": len(U1_FIXED_ACTIVITIES.activities),
            "reviewedFixedObservationPoints": sum(
                len(item.observation_points) for item in U1_FIXED_ACTIVITIES.activities
            ),
            "familyAnchorActivities": len(U1_FAMILY_ANCHOR_ACTIVITIES.activities),
            "familyAnchorObservationPoints": sum(
                len(item.observation_points)
                for item in U1_FAMILY_ANCHOR_ACTIVITIES.activities
            ),
            "packActivities": len(activities),
            "packObservationPoints": sum(
                len(item["observationPoints"]) for item in activities
            ),
            "familiesWithReviewedFixedObservation": len(fixed_activities),
            "familiesWithDedicatedAnchor": len(family_anchors),
            "generatedPoolEntryCandidates": len(pool_payloads),
            "distinctGeneratedActivityIds": len(
                {
                    item["generatedActivityArtifact"]["local_id"]
                    for item in pool_payloads
                }
            ),
            "distinctPackActivityIds": len(
                {item["packActivityRef"]["localId"] for item in pool_payloads}
            ),
            "familiesWithPoolCandidates": len(pool_by_family),
            "runtimeAdmissionStatus": (
                "PASS"
                if isinstance(runtime_trace, dict)
                and runtime_trace.get("status") == "PASS"
                else "not-recorded"
            ),
            "runtimeAdmittedPoolEntryCount": (
                runtime_trace.get("counts", {}).get("verifiedPoolEntries")
                if isinstance(runtime_trace, dict)
                else None
            ),
            "canonicalActivitiesInRuntimeTrace": (
                runtime_trace.get("counts", {}).get("completedActivities")
                if isinstance(runtime_trace, dict)
                else None
            ),
            "mapPlaceActivitiesCompleted": (
                runtime_trace.get("counts", {}).get("completedActivitiesAtMapPlaces")
                if isinstance(runtime_trace, dict)
                else None
            ),
            "taskFamiliesSelectedFromMapPlaces": len(map_trace_family_ids),
            "canonicalFamilyExplorationSurfaces": len(exploration_trace_family_ids),
            "responseCapabilitiesVerifiedFromMapSurfaces": (
                runtime_trace.get("mapSurfaceResponseCapabilities")
                if isinstance(runtime_trace, dict)
                else None
            ),
        },
        "regions": list(regions.values()),
        "places": [
            {
                "id": item.local_id,
                "title": item.title,
                "description": item.description,
                "regionId": place_regions[item.local_id],
            }
            for item in places.values()
        ],
        "roads": [
            {
                "id": item.local_id,
                "title": item.title,
                "kind": item.kind,
                "fromPlaceId": item.from_place.local_id,
                "toPlaceId": item.to_place.local_id,
                "startingPoint": item.starting_point,
                "ahaOpportunity": item.aha_opportunity,
                "resultingPossibility": item.resulting_possibility,
            }
            for item in pack.learning_map.roads
        ],
        "activities": activities,
        "runtimeTrace": runtime_trace,
        "responseContract": {
            "packDeclaredResponseCapabilities": declared_response_capabilities,
            "bailianRenderedResponseCapabilities": rendered_response_capabilities,
            "unsupportedDeclaredResponseCapabilities": sorted(
                set(declared_response_capabilities)
                - set(rendered_response_capabilities)
            ),
        },
        "taskFamilies": family_rows,
        "acceptanceNote": (
            "Pool candidates, Runtime admission, actual canonical Decision selection, Surface completion, and browser rendering "
            "are separate evidence layers. Runtime trace flags are true only for families observed in the attached 10-step trace."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="docs/evidence/math-u1-supply-matrix-final-0.3.3.json",
    )
    parser.add_argument(
        "--trace",
        default="docs/evidence/math-u1-10-activity-trace.json",
    )
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    trace_path = (ROOT / args.trace).resolve() if args.trace else None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(_build_matrix(trace_path), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output)


if __name__ == "__main__":
    if sys.version_info < (3, 12):
        raise SystemExit("Use Python 3.12 or later for the SDK runtime.")
    main()
