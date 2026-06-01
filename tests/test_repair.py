import tempfile
import unittest
from pathlib import Path

from api.repair import build_repair_plan
from api.schemas import ExecutionResult, StepResult
from api.planner import build_plan
from tests.helpers import write_saved_run


class RepairTests(unittest.TestCase):
    def test_build_repair_plan_for_python_unclosed_parenthesis(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            plan = build_plan("创建 broken.py 内容 print('x' 然后运行")
            result = ExecutionResult(
                plan=plan,
                step_results=[
                    StepResult(
                        step=plan.steps[0],
                        status="completed",
                        result={"path": "broken.py", "bytes_written": 9, "created": True},
                    ),
                    StepResult(
                        step=plan.steps[1],
                        status="failed",
                        result={
                            "exit_code": 1,
                            "stdout": "",
                            "stderr": "SyntaxError: '(' was never closed",
                        },
                    ),
                ],
                status="failed",
            )
            write_saved_run(run_dir, plan, result)

            repair = build_repair_plan(str(run_dir))

        self.assertEqual(repair.status, "ready")
        self.assertIsNotNone(repair.plan)
        assert repair.plan is not None
        self.assertEqual(repair.plan.source, "repair-rule")
        self.assertEqual(repair.plan.context["repair_rule"], "python_unclosed_delimiter")
        self.assertEqual(repair.plan.steps[0].tool, "patch_file")
        self.assertEqual(repair.plan.steps[0].input["path"], "broken.py")
        self.assertEqual(
            repair.plan.steps[0].input["edits"],
            [{"old_text": "print('x'", "new_text": "print('x')"}],
        )
        self.assertEqual(repair.plan.steps[1].tool, "run_shell")
        self.assertEqual(repair.plan.steps[1].input["command"], "python broken.py")

    def test_build_repair_plan_for_python_unclosed_list(self) -> None:
        repair = build_repair_for_content("values.py", "items = [1, 2, 3", "SyntaxError: '[' was never closed")

        self.assertEqual(repair.status, "ready")
        self.assertIsNotNone(repair.plan)
        assert repair.plan is not None
        self.assertEqual(
            repair.plan.steps[0].input["edits"],
            [{"old_text": "items = [1, 2, 3", "new_text": "items = [1, 2, 3]"}],
        )

    def test_build_repair_plan_for_python_unclosed_dict(self) -> None:
        repair = build_repair_for_content("config.py", "config = {'a': 1", "SyntaxError: '{' was never closed")

        self.assertEqual(repair.status, "ready")
        self.assertIsNotNone(repair.plan)
        assert repair.plan is not None
        self.assertEqual(
            repair.plan.steps[0].input["edits"],
            [{"old_text": "config = {'a': 1", "new_text": "config = {'a': 1}"}],
        )

    def test_build_repair_plan_rejects_completed_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            plan = build_plan("看看文件")
            result = ExecutionResult(plan=plan, step_results=[], status="completed")
            write_saved_run(run_dir, plan, result)

            repair = build_repair_plan(str(run_dir))

        self.assertEqual(repair.status, "unsupported")
        self.assertEqual(repair.reason, "run already completed")

    def test_build_repair_plan_rejects_unknown_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            plan = build_plan("/run false")
            result = ExecutionResult(
                plan=plan,
                step_results=[
                    StepResult(
                        step=plan.steps[0],
                        status="failed",
                        result={"exit_code": 1, "stdout": "", "stderr": ""},
                    )
                ],
                status="failed",
            )
            write_saved_run(run_dir, plan, result)

            repair = build_repair_plan(str(run_dir))

        self.assertEqual(repair.status, "unsupported")
        self.assertEqual(repair.reason, "no matching repair rule")

    def test_build_repair_plan_classifies_name_error(self) -> None:
        repair = build_repair_for_content(
            "name_error.py",
            "print(missing_value)",
            "NameError: name 'missing_value' is not defined",
        )

        self.assertEqual(repair.status, "unsupported")
        self.assertEqual(repair.reason, "NameError repair requires semantic planner")

    def test_build_repair_plan_classifies_missing_module(self) -> None:
        repair = build_repair_for_content(
            "missing_module.py",
            "import not_installed_package",
            "ModuleNotFoundError: No module named 'not_installed_package'",
        )

        self.assertEqual(repair.status, "unsupported")
        self.assertEqual(repair.reason, "ModuleNotFoundError repair requires dependency policy")


def build_repair_for_content(path: str, content: str, stderr: str):
    with tempfile.TemporaryDirectory() as temp_dir:
        run_dir = Path(temp_dir) / "run_001"
        run_dir.mkdir()
        plan = build_plan(f"创建 {path} 内容 {content} 然后运行")
        result = ExecutionResult(
            plan=plan,
            step_results=[
                StepResult(
                    step=plan.steps[0],
                    status="completed",
                    result={"path": path, "bytes_written": len(content.encode("utf-8")), "created": True},
                ),
                StepResult(
                    step=plan.steps[1],
                    status="failed",
                    result={"exit_code": 1, "stdout": "", "stderr": stderr},
                ),
            ],
            status="failed",
        )
        write_saved_run(run_dir, plan, result)
        return build_repair_plan(str(run_dir))


if __name__ == "__main__":
    unittest.main()
