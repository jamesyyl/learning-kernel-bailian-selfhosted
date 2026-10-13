from __future__ import annotations

import unittest

from api.learning_map import learning_map_payload
from learning_kernel.knowledge_packs.math_u1_vnext.scope import PACK_VERSION


class LearningMapPayloadTests(unittest.TestCase):
    def test_payload_exposes_every_pack_place_and_road_by_exact_release(self) -> None:
        payload = learning_map_payload()
        pack = payload["pack"]
        places = payload["places"]
        roads = payload["roads"]
        regions = payload["regions"]
        families = payload["taskFamilies"]

        self.assertEqual(payload["schemaVersion"], "learning-kernel.learning-map@1")
        self.assertEqual(pack["version"], PACK_VERSION)
        self.assertEqual(len(regions), 5)
        self.assertEqual(len(places), 17)
        self.assertEqual(len(roads), 37)
        self.assertEqual(len(families), 26)
        self.assertEqual(len({place["id"] for place in places}), 17)
        self.assertEqual(len({road["id"] for road in roads}), 37)
        family_ids = {family["id"] for family in families}
        self.assertTrue(all(family["placeIds"] for family in families))
        self.assertEqual(
            {family_id for place in places for family_id in place["taskFamilyIds"]},
            family_ids,
        )

        place_ids = {place["id"] for place in places}
        for road in roads:
            self.assertIn(road["fromPlaceId"], place_ids)
            self.assertIn(road["toPlaceId"], place_ids)
            self.assertIn(road["kind"], {"learning", "remediation", "return"})

        self.assertEqual(
            {entry["regionId"] for entry in payload["entryPoints"]},
            {region["id"] for region in regions},
        )


if __name__ == "__main__":
    unittest.main()
