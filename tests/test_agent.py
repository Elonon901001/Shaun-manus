import unittest

from api.agent import plan_next_action


class AgentPlannerTests(unittest.TestCase):
    def test_write_command_plans_write_file(self) -> None:
        decision = plan_next_action("/write notes/hello.txt\nhello from agent")

        self.assertEqual(decision.tool, "write_file")
        self.assertEqual(decision.input["path"], "notes/hello.txt")
        self.assertEqual(decision.input["content"], "hello from agent")

    def test_natural_create_plans_write_file(self) -> None:
        decision = plan_next_action("创建 notes/hello.txt 内容 hello")

        self.assertEqual(decision.tool, "write_file")
        self.assertEqual(decision.input["path"], "notes/hello.txt")
        self.assertEqual(decision.input["content"], "hello")


if __name__ == "__main__":
    unittest.main()
