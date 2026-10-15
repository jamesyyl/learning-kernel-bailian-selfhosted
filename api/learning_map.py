"""Read-only view of the exact released Math U1 learning map."""

from __future__ import annotations

from learning_kernel.knowledge_packs.math_u1_vnext.pack import U1_PACK
from learning_kernel.knowledge_packs.vnext_task_family import TaskFamilyNavigationUse


def learning_map_payload() -> dict[str, object]:
    pack = U1_PACK
    region_by_place = {
        place.local_id: region
        for region in pack.learning_map.regions
        for place in region.places
    }
    place_by_id = {place.local_id: place for place in pack.learning_map.places}
    road_by_id = {road.local_id: road for road in pack.learning_map.roads}
    junction_by_id = {item.local_id: item for item in pack.learning_map.junctions}
    capability_by_id = {item.local_id: item for item in pack.capabilities.capabilities}
    # A multi-step authored Activity can be entered from any of its learning
    # Places. The Pack (not a browser hardcoded route) identifies its first
    # observable Family and starting Place.
    journeys_by_place: dict[str, tuple[int, str, str]] = {}
    for activity in pack.activities.activities:
        points = activity.observation_points
        if len(points) < 5:
            continue
        initial_capability = capability_by_id[points[0].capability.local_id]
        starting_places = [
            ref.local_id for ref in initial_capability.map_refs if ref.kind == "place"
        ]
        if len(starting_places) != 1:
            continue
        initial_family_id = points[0].task_family.local_id
        for point in points:
            capability = capability_by_id[point.capability.local_id]
            for ref in capability.map_refs:
                if ref.kind != "place":
                    continue
                previous = journeys_by_place.get(ref.local_id)
                if previous is None or len(points) > previous[0]:
                    journeys_by_place[ref.local_id] = (
                        len(points), initial_family_id, starting_places[0]
                    )

    # An explicit Place should first offer practice of its own observable
    # capability; alphabetic Family IDs are not a pedagogical priority.
    def focused_priority(family_id: str) -> tuple[int, str]:
        family = next(
            item for item in pack.task_families.families
            if item.local_id == family_id
        )
        uses = family.navigation_uses
        if TaskFamilyNavigationUse.FLUENCY_PRACTICE in uses:
            return (0, family_id)
        if (
            TaskFamilyNavigationUse.ALTERNATE_METHOD in uses
            or TaskFamilyNavigationUse.ALTERNATE_REPRESENTATION in uses
        ):
            return (1, family_id)
        return (2, family_id)

    task_families = []
    family_ids_by_place: dict[str, set[str]] = {
        place_id: set() for place_id in place_by_id
    }
    # Explicit exploration stays on the chosen Place. A capability merely touching
    # a Road or Junction must not silently turn into that Place's own activity.
    focused_family_ids_by_place: dict[str, set[str]] = {
        place_id: set() for place_id in place_by_id
    }
    for family in pack.task_families.families:
        capability = capability_by_id[family.primary_capability.local_id]
        for reference in capability.map_refs:
            if reference.kind == "place":
                focused_family_ids_by_place[reference.local_id].add(family.local_id)
        family_place_ids: set[str] = set()
        for reference in capability.map_refs:
            if reference.kind == "place":
                family_place_ids.add(reference.local_id)
            elif reference.kind == "road":
                road = road_by_id[reference.local_id]
                family_place_ids.update(
                    (road.from_place.local_id, road.to_place.local_id)
                )
            elif reference.kind == "junction":
                family_place_ids.add(
                    junction_by_id[reference.local_id].at_place.local_id
                )
        for place_id in family_place_ids:
            family_ids_by_place[place_id].add(family.local_id)
        task_families.append(
            {
                "id": family.local_id,
                "title": family.title,
                "observationPurpose": family.observation_purpose,
                "primaryCapabilityId": capability.local_id,
                "placeIds": sorted(family_place_ids),
            }
        )
    return {
        "schemaVersion": "learning-kernel.learning-map@1",
        "pack": {
            "id": pack.pack_id,
            "version": pack.identity.pack_version,
            "title": pack.identity.title,
            "contentDigest": pack.lifecycle.content_digest,
        },
        "entryPoints": [
            {"regionId": entry.region_id, "placeId": entry.place_local_id}
            for entry in pack.execution_contract.entry_points
        ],
        "regions": [
            {
                "id": region.local_id,
                "title": region.title,
                "placeIds": [place.local_id for place in region.places],
            }
            for region in pack.learning_map.regions
        ],
        "places": [
            {
                "id": place.local_id,
                "title": place.title,
                "description": place.description,
                "realWorldMeaning": place.real_world_meaning,
                "regionId": region_by_place[place.local_id].local_id,
                "taskFamilyIds": sorted(family_ids_by_place[place.local_id]),
                "focusedTaskFamilyIds": sorted(
                    focused_family_ids_by_place[place.local_id],
                    key=focused_priority,
                ),
                "journeyTaskFamilyId": (
                    journeys_by_place[place.local_id][1]
                    if place.local_id in journeys_by_place else None
                ),
                "journeyStartPlaceId": (
                    journeys_by_place[place.local_id][2]
                    if place.local_id in journeys_by_place else None
                ),
            }
            for place in pack.learning_map.places
        ],
        "taskFamilies": task_families,
        "roads": [
            {
                "id": road.local_id,
                "title": road.title,
                "description": road.description,
                "kind": road.kind,
                "fromPlaceId": road.from_place.local_id,
                "toPlaceId": road.to_place.local_id,
                "startingPoint": road.starting_point,
                "ahaOpportunity": road.aha_opportunity,
                "resultingPossibility": road.resulting_possibility,
                "fromPlaceTitle": place_by_id[road.from_place.local_id].title,
                "toPlaceTitle": place_by_id[road.to_place.local_id].title,
            }
            for road in pack.learning_map.roads
        ],
    }
