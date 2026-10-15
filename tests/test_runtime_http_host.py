from __future__ import annotations

import unittest

from api.app import _learner_route_allowed


class RuntimeHttpHostTests(unittest.TestCase):
    def test_allows_surface_and_raw_observation_only(self) -> None:
        prefix = "/api/learners/learner-1/environments/home/packs/math-u1"

        self.assertTrue(_learner_route_allowed("POST", f"{prefix}/surface"))
        self.assertTrue(_learner_route_allowed("OPTIONS", f"{prefix}/surface"))
        self.assertTrue(_learner_route_allowed("POST", f"{prefix}/observations"))
        self.assertTrue(_learner_route_allowed("OPTIONS", f"{prefix}/observations"))
        self.assertTrue(_learner_route_allowed("GET", "/api/ready"))
        self.assertTrue(_learner_route_allowed("GET", "/api/learning-map"))
        self.assertFalse(_learner_route_allowed("POST", "/api/learning-map"))
        self.assertFalse(_learner_route_allowed("GET", "/api/health"))

    def test_blocks_privileged_and_unimplemented_routes(self) -> None:
        prefix = "/api/learners/learner-1/environments/home/packs/math-u1"

        self.assertFalse(_learner_route_allowed("GET", f"{prefix}/surface"))
        self.assertFalse(_learner_route_allowed("POST", f"{prefix}/returns"))
        self.assertFalse(_learner_route_allowed("GET", f"{prefix}/home-projection"))
        self.assertFalse(_learner_route_allowed("POST", "/api/packs/install"))
        self.assertFalse(_learner_route_allowed("POST", "/api/packs/math-u1/disable"))


if __name__ == "__main__":
    unittest.main()
