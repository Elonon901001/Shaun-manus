import unittest

from api.planner import build_plan


class PlannerTests(unittest.TestCase):
    def test_write_then_run_python_plan(self) -> None:
        plan = build_plan("创建 hello.py 内容 print('hi') 然后运行")

        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].tool, "write_file")
        self.assertEqual(plan.steps[0].input["path"], "hello.py")
        self.assertEqual(plan.steps[0].input["content"], "print('hi')")
        self.assertEqual(plan.steps[1].tool, "run_shell")
        self.assertEqual(plan.steps[1].input["command"], "python hello.py")

    def test_single_step_fallback(self) -> None:
        plan = build_plan("看看文件")

        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].tool, "list_files")

    def test_run_then_read_uses_requested_path(self) -> None:
        plan = build_plan("/run false 然后读取 hello.py")

        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].tool, "run_shell")
        self.assertEqual(plan.steps[1].tool, "read_file")
        self.assertEqual(plan.steps[1].input["path"], "hello.py")


if __name__ == "__main__":
    unittest.main()
