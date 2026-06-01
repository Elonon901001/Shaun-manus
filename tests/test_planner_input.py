import unittest

from api.planner_input import build_planner_input


class PlannerInputTests(unittest.TestCase):
    def test_build_planner_input_includes_tool_manifest_and_constraints(self) -> None:
        planner_input = build_planner_input("创建 hello.py 内容 print('hi') 然后运行")

        self.assertEqual(planner_input.message, "创建 hello.py 内容 print('hi') 然后运行")
        self.assertEqual(planner_input.constraints["plan_version"], "planner.v1")
        self.assertTrue(planner_input.constraints["must_use_tools_from_manifest"])
        self.assertTrue(planner_input.constraints["llm_must_not_execute_tools"])

        tool_names = {tool["name"] for tool in planner_input.tool_manifest["tools"]}
        self.assertIn("write_file", tool_names)
        self.assertIn("run_shell", tool_names)
        self.assertIn("patch_file", tool_names)


if __name__ == "__main__":
    unittest.main()
