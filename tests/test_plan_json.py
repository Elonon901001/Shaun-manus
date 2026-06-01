import unittest

from api.planner import build_plan, plan_from_json, plan_to_json


class PlanJsonTests(unittest.TestCase):
    def test_plan_round_trips_through_json(self) -> None:
        plan = build_plan("看看文件")
        restored = plan_from_json(plan_to_json(plan))

        self.assertEqual(restored.version, "planner.v1")
        self.assertEqual(restored.source, "rule")
        self.assertEqual(restored.steps[0].tool, "list_files")

    def test_external_plan_defaults_are_normalized(self) -> None:
        plan = plan_from_json('{"goal": "x", "steps": [{"id": "s1", "thought": "t", "tool": "list_files", "input": {"path": "."}}]}')

        self.assertEqual(plan.version, "planner.v1")
        self.assertEqual(plan.source, "external")
        self.assertEqual(plan.max_steps, 8)


if __name__ == "__main__":
    unittest.main()
