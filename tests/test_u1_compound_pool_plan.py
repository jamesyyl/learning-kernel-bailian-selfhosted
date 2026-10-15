"""U1-5 compound supply must be one Pack Activity with five independent observations."""

from __future__ import annotations

import unittest
from collections import defaultdict

from learning_kernel.knowledge_packs.math_u1_vnext.pack import U1_PACK

from api.seed_u1 import (
    COMPOUND_ACTIVITY_ID,
    COMPOUND_FAMILY_IDS,
    COMPOUND_PRIMARY_FAMILY,
    VARIANTS_PER_FAMILY,
    _pool_payloads,
)


class MathU1CompoundSupplyTests(unittest.TestCase):
    def test_all_five_observations_share_a_scenario_and_authored_activity(self) -> None:
        entries = _pool_payloads(U1_PACK.lifecycle.content_digest)
        family_count = len(U1_PACK.task_families.families)
        # One standalone primary is replaced by one compound primary; four
        # supporting Families each keep ordinary individual-practice supply.
        self.assertEqual(
            len(entries), (family_count + len(COMPOUND_FAMILY_IDS) - 1) * VARIANTS_PER_FAMILY
        )
        grouped = defaultdict(list)
        for entry in entries:
            artifact = entry["generatedActivityArtifact"]
            context_id = artifact["learner_payload"].get("compoundScenarioId")
            if context_id is None:
                self.assertNotEqual(
                    artifact["task_family"]["local_id"], COMPOUND_PRIMARY_FAMILY
                )
                continue
            self.assertEqual(entry["packActivityRef"]["localId"], COMPOUND_ACTIVITY_ID)
            self.assertIn(artifact["task_family"]["local_id"], COMPOUND_FAMILY_IDS)
            grouped[context_id].append(entry)

        self.assertEqual(len(grouped), VARIANTS_PER_FAMILY)
        for scenario_id, steps in grouped.items():
            self.assertEqual(len(steps), len(COMPOUND_FAMILY_IDS), scenario_id)
            self.assertEqual(
                {entry["generatedActivityArtifact"]["task_family"]["local_id"] for entry in steps},
                set(COMPOUND_FAMILY_IDS),
            )
            self.assertEqual(
                len({entry["observationPointId"] for entry in steps}),
                len(COMPOUND_FAMILY_IDS),
            )
            self.assertEqual(
                len({
                    tuple(entry["generatedActivityArtifact"]["learner_payload"]["operands"])
                    for entry in steps
                }),
                1,
            )
            self.assertEqual(
                len({
                    entry["generatedActivityArtifact"]["local_id"] for entry in steps
                }),
                len(COMPOUND_FAMILY_IDS),
            )
