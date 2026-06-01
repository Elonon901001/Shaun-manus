import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import AsyncMock, patch

from api import cli
from api import cli_runner
from api.repair import RepairPlanBuildResult
from api.schemas import AgentPlan, AgentStep, ExecutionResult, StepResult
from tests.helpers import write_saved_run


class CliTests(unittest.IsolatedAsyncioTestCase):
    async def test_safe_task_executes_without_confirmation(self) -> None:
        with patch.object(
            cli_runner,
            "execute_plan",
            AsyncMock(
                return_value=ExecutionResult(
                    plan=cli.build_plan("看看文件"),
                    step_results=[],
                    status="completed",
                )
            ),
        ) as execute_plan:
            with redirect_stdout(io.StringIO()):
                exit_code = await cli.run_task("看看文件")

        self.assertEqual(exit_code, 0)
        execute_plan.assert_awaited_once()

    async def test_write_task_can_be_cancelled(self) -> None:
        with redirect_stdout(io.StringIO()):
            exit_code = await cli.run_task("/write notes/a.txt hello", confirm=lambda _step: False)

        self.assertEqual(exit_code, 130)

    async def test_write_task_executes_with_yes(self) -> None:
        with patch.object(
            cli_runner,
            "execute_plan",
            AsyncMock(
                return_value=ExecutionResult(
                    plan=cli.build_plan("/write notes/a.txt hello"),
                    step_results=[],
                    status="completed",
                )
            ),
        ) as execute_plan:
            with redirect_stdout(io.StringIO()):
                exit_code = await cli.run_task("/write notes/a.txt hello", assume_yes=True)

        self.assertEqual(exit_code, 0)
        execute_plan.assert_awaited_once()

    async def test_plan_only_does_not_execute(self) -> None:
        with patch.object(cli_runner, "execute_plan", AsyncMock()) as execute_plan:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = await cli.run_task("看看文件", plan_only=True)

        self.assertEqual(exit_code, 0)
        self.assertIn('"version":"planner.v1"', output.getvalue())
        execute_plan.assert_not_awaited()

    async def test_llm_planner_plan_only_does_not_execute(self) -> None:
        plan = AgentPlan(
            source="llm",
            goal="inspect files",
            steps=[AgentStep(id="step_1", thought="list", tool="list_files", input={"path": "."})],
        )

        with patch.object(cli_runner, "build_llm_plan", return_value=plan) as build_llm_plan:
            with patch.object(cli_runner, "execute_plan", AsyncMock()) as execute_plan:
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = await cli.run_task(
                        "inspect files",
                        plan_only=True,
                        planner_name="llm",
                        llm_model="test-model",
                    )

        self.assertEqual(exit_code, 0)
        self.assertIn('"source":"llm"', output.getvalue())
        build_llm_plan.assert_called_once_with("inspect files", model="test-model")
        execute_plan.assert_not_awaited()

    def test_load_plan_file_normalizes_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = Path(temp_dir) / "plan.json"
            plan_path.write_text(
                '{"goal": "manual", "steps": [{"id": "step_1", "thought": "list", "tool": "list_files", "input": {"path": "."}}]}',
                encoding="utf-8",
            )

            plan = cli.load_plan_file(str(plan_path))

        self.assertEqual(plan.source, "external")
        self.assertEqual(plan.steps[0].tool, "list_files")

    def test_load_run_plan_reads_plan_json_from_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            (run_dir / "plan.json").write_text(
                '{"goal": "manual", "steps": [{"id": "step_1", "thought": "list", "tool": "list_files", "input": {"path": "."}}]}',
                encoding="utf-8",
            )

            plan = cli.load_run_plan(str(run_dir))

        self.assertEqual(plan.source, "external")
        self.assertEqual(plan.steps[0].tool, "list_files")

    def test_load_local_env_reads_dotenv_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# local development settings",
                        "OPENAI_API_KEY=test-key",
                        'OPENAI_MODEL="test-model"',
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                cli.load_local_env(env_path)

                self.assertEqual(os.environ["OPENAI_API_KEY"], "test-key")
                self.assertEqual(os.environ["OPENAI_MODEL"], "test-model")

    def test_load_local_env_does_not_override_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("OPENAI_API_KEY=file-key", encoding="utf-8")

            with patch.dict(os.environ, {"OPENAI_API_KEY": "shell-key"}, clear=True):
                cli.load_local_env(env_path)

                self.assertEqual(os.environ["OPENAI_API_KEY"], "shell-key")

    def test_main_plan_file_skips_build_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = Path(temp_dir) / "plan.json"
            plan_path.write_text(
                '{"goal": "manual", "steps": [{"id": "step_1", "thought": "list", "tool": "list_files", "input": {"path": "."}}]}',
                encoding="utf-8",
            )

            with patch.object(cli, "build_plan") as build_plan:
                with patch.object(cli_runner, "execute_plan", AsyncMock(return_value=ExecutionResult(plan=cli.load_plan_file(str(plan_path)), step_results=[], status="completed"))):
                    with redirect_stdout(io.StringIO()):
                        exit_code = cli.main(["--plan-file", str(plan_path)])

        self.assertEqual(exit_code, 0)
        build_plan.assert_not_called()

    def test_main_rerun_skips_build_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            (run_dir / "plan.json").write_text(
                '{"goal": "manual", "steps": [{"id": "step_1", "thought": "list", "tool": "list_files", "input": {"path": "."}}]}',
                encoding="utf-8",
            )

            with patch.object(cli, "build_plan") as build_plan:
                with patch.object(
                    cli_runner,
                    "execute_plan",
                    AsyncMock(
                        return_value=ExecutionResult(
                            plan=cli.load_run_plan(str(run_dir)),
                            step_results=[],
                            status="completed",
                        )
                    ),
                ):
                    with redirect_stdout(io.StringIO()):
                        exit_code = cli.main(["--rerun", str(run_dir)])

        self.assertEqual(exit_code, 0)
        build_plan.assert_not_called()

    def test_inspect_run_prints_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            plan = cli.build_plan("创建 a.py 内容 print('x') 然后运行")
            result = ExecutionResult(
                plan=plan,
                step_results=[],
                events=[{"type": "execution_started", "max_steps": 8}],
                status="completed",
            )
            write_saved_run(run_dir, plan, result, events=[{"type": "execution_started", "max_steps": 8}])

            output = cli.inspect_run(str(run_dir))

        self.assertIn("status: completed", output)
        self.assertIn("steps: 0/2", output)
        self.assertIn("step_1 write_file not_run", output)

    def test_main_inspect_run_does_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            plan = cli.build_plan("看看文件")
            result = ExecutionResult(plan=plan, step_results=[], status="completed")
            write_saved_run(run_dir, plan, result)

            with patch.object(cli_runner, "execute_plan", AsyncMock()) as execute_plan:
                with redirect_stdout(io.StringIO()) as output:
                    exit_code = cli.main(["--inspect-run", str(run_dir)])

        self.assertEqual(exit_code, 0)
        self.assertIn("goal: 看看文件", output.getvalue())
        execute_plan.assert_not_awaited()

    def test_explain_run_prints_repair_context_for_failed_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            plan = cli.build_plan("创建 broken.py 内容 print( 然后运行")
            result = ExecutionResult(
                plan=plan,
                step_results=[
                    StepResult(
                        step=plan.steps[0],
                        status="completed",
                        result={"path": "broken.py", "bytes_written": 6, "created": True},
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
                events=[
                    {"type": "execution_started", "max_steps": 8},
                    {"type": "step_finished", "step_id": "step_2", "status": "failed"},
                ],
                status="failed",
            )
            write_saved_run(
                run_dir,
                plan,
                result,
                events=[
                    {"type": "execution_started", "max_steps": 8},
                    {"type": "step_finished", "step_id": "step_2", "status": "failed"},
                ],
            )

            output = cli.explain_run(str(run_dir))

        self.assertIn("repair context", output)
        self.assertIn("completed steps:", output)
        self.assertIn("step_1: write_file", output)
        self.assertIn("failed step:", output)
        self.assertIn("tool: run_shell", output)
        self.assertIn("stderr: SyntaxError: '(' was never closed", output)
        self.assertIn("repair hint:", output)
        self.assertIn("inspect stdout/stderr", output)

    def test_main_explain_run_does_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "run_001"
            run_dir.mkdir()
            plan = cli.build_plan("看看文件")
            result = ExecutionResult(
                plan=plan,
                step_results=[
                    StepResult(
                        step=plan.steps[0],
                        status="failed",
                        result={
                            "error": "Tool input validation failed",
                            "message": "list_files input.path must be str",
                        },
                    )
                ],
                events=[{"type": "step_finished", "step_id": "step_1", "status": "failed"}],
                status="failed",
            )
            write_saved_run(
                run_dir,
                plan,
                result,
                events=[{"type": "step_finished", "step_id": "step_1", "status": "failed"}],
            )

            with patch.object(cli_runner, "execute_plan", AsyncMock()) as execute_plan:
                with redirect_stdout(io.StringIO()) as output:
                    exit_code = cli.main(["--explain-run", str(run_dir)])

        self.assertEqual(exit_code, 0)
        self.assertIn("repair context", output.getvalue())
        self.assertIn("fix the plan input schema", output.getvalue())
        execute_plan.assert_not_awaited()

    def test_main_tool_manifest_prints_json_without_executing(self) -> None:
        with patch.object(cli_runner, "execute_plan", AsyncMock()) as execute_plan:
            with redirect_stdout(io.StringIO()) as output:
                exit_code = cli.main(["--tool-manifest"])

        payload = json.loads(output.getvalue())
        tool_names = {tool["name"] for tool in payload["tools"]}
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["version"], "tool_manifest.v1")
        self.assertIn("run_shell", tool_names)
        self.assertIn("write_file", tool_names)
        execute_plan.assert_not_awaited()

    def test_main_repair_run_plan_only_prints_repair_plan(self) -> None:
        repair_plan = AgentPlan(
            source="repair-rule",
            goal="repair",
            steps=[
                AgentStep(
                    id="repair_1",
                    thought="patch",
                    tool="patch_file",
                    input={"path": "a.py", "edits": [{"old_text": "print(", "new_text": "print()"}]},
                )
            ],
        )

        with patch.object(
            cli,
            "build_repair_plan",
            return_value=RepairPlanBuildResult(status="ready", plan=repair_plan),
        ):
            with patch.object(cli_runner, "execute_plan", AsyncMock()) as execute_plan:
                with redirect_stdout(io.StringIO()) as output:
                    exit_code = cli.main(["--repair-run", "runs/run_001", "--plan-only"])

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["source"], "repair-rule")
        self.assertEqual(payload["steps"][0]["tool"], "patch_file")
        execute_plan.assert_not_awaited()

    def test_main_repair_run_executes_repair_plan(self) -> None:
        repair_plan = AgentPlan(
            source="repair-rule",
            goal="repair",
            steps=[AgentStep(id="repair_1", thought="list", tool="list_files", input={"path": "."})],
        )
        execution = ExecutionResult(plan=repair_plan, step_results=[], status="completed")

        with patch.object(
            cli,
            "build_repair_plan",
            return_value=RepairPlanBuildResult(status="ready", plan=repair_plan),
        ):
            with patch.object(cli_runner, "execute_plan", AsyncMock(return_value=execution)) as execute_plan:
                with redirect_stdout(io.StringIO()):
                    exit_code = cli.main(["--repair-run", "runs/run_001"])

        self.assertEqual(exit_code, 0)
        execute_plan.assert_awaited_once()

    def test_main_repair_run_reports_unsupported(self) -> None:
        with patch.object(
            cli,
            "build_repair_plan",
            return_value=RepairPlanBuildResult(status="unsupported", reason="no matching repair rule"),
        ):
            with redirect_stdout(io.StringIO()) as output:
                exit_code = cli.main(["--repair-run", "runs/run_001"])

        self.assertEqual(exit_code, 1)
        self.assertIn("repair unsupported: no matching repair rule", output.getvalue())

    def test_main_passes_llm_planner_options_to_task_runner(self) -> None:
        with patch.object(cli, "run_task", AsyncMock(return_value=0)) as run_task:
            exit_code = cli.main(["--planner", "llm", "--llm-model", "test-model", "inspect", "files"])

        self.assertEqual(exit_code, 0)
        run_task.assert_awaited_once_with(
            "inspect files",
            assume_yes=False,
            output_json=False,
            plan_only=False,
            save_run_log=False,
            runs_dir="runs",
            planner_name="llm",
            llm_model="test-model",
        )


if __name__ == "__main__":
    unittest.main()
