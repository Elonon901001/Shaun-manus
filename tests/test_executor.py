import unittest
from unittest.mock import AsyncMock, patch

from api.executor import execute_plan
from api import executor
from api.schemas import AgentPlan, AgentStep


class ExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_plan_stops_on_failed_step(self) -> None:
        plan = AgentPlan(
            goal="run bad command",
            steps=[
                AgentStep(id="step_1", thought="run", tool="run_shell", input={"command": "false"}),
                AgentStep(id="step_2", thought="list", tool="list_files", input={"path": "."}),
            ],
        )

        with patch(
            "api.executor.execute_tool",
            AsyncMock(return_value={"exit_code": 1, "stdout": "", "stderr": "failed"}),
        ) as execute_tool:
            result = await execute_plan(plan, assume_yes=True)

        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.step_results), 1)
        execute_tool.assert_awaited_once()

    async def test_execute_plan_can_cancel_confirmation(self) -> None:
        plan = AgentPlan(
            goal="write file",
            steps=[AgentStep(id="step_1", thought="write", tool="write_file", input={"path": "a.txt", "content": "a"})],
        )

        with patch("api.executor.execute_tool", AsyncMock()) as execute_tool:
            result = await execute_plan(plan, confirm=lambda _step: False)

        self.assertEqual(result.status, "cancelled")
        execute_tool.assert_not_awaited()

    async def test_execute_plan_resolves_step_result_references(self) -> None:
        plan = AgentPlan(
            goal="write then read generated path",
            steps=[
                AgentStep(id="step_1", thought="write", tool="write_file", input={"path": "a.txt", "content": "hello"}),
                AgentStep(id="step_2", thought="read", tool="read_file", input={"path": "${step_1.result.path}"}),
            ],
        )

        with patch(
            "api.executor.execute_tool",
            AsyncMock(
                side_effect=[
                    {"path": "a.txt", "bytes_written": 5, "created": True},
                    {"path": "a.txt", "content": "hello", "truncated": False},
                ]
            ),
        ) as execute_tool:
            result = await execute_plan(plan, assume_yes=True)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.step_results[1].step.input["path"], "a.txt")
        self.assertEqual(execute_tool.await_args_list[1].args[1], {"path": "a.txt"})

    async def test_execute_plan_stops_at_max_steps(self) -> None:
        plan = AgentPlan(
            goal="too many",
            max_steps=1,
            steps=[
                AgentStep(id="step_1", thought="one", tool="list_files", input={"path": "."}),
                AgentStep(id="step_2", thought="two", tool="list_files", input={"path": "."}),
            ],
        )

        with patch("api.executor.execute_tool", AsyncMock(return_value={"path": ".", "entries": []})):
            result = await execute_plan(plan, assume_yes=True)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.events[-1]["type"], "max_steps_reached")

    async def test_execute_plan_validates_before_running_tool(self) -> None:
        plan = AgentPlan(
            goal="bad write",
            steps=[
                AgentStep(
                    id="step_1",
                    thought="write without path",
                    tool="write_file",
                    input={"content": "hello"},
                )
            ],
        )

        with patch("api.executor.execute_tool", AsyncMock()) as execute_tool:
            result = await execute_plan(plan, assume_yes=True)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.step_results[0].result["error"], "Tool input validation failed")
        self.assertIn("requires input.path", result.step_results[0].result["message"])
        execute_tool.assert_not_awaited()

    async def test_execute_plan_blocks_unsafe_shell_before_running_tool(self) -> None:
        plan = AgentPlan(
            goal="dangerous command",
            steps=[
                AgentStep(
                    id="step_1",
                    thought="remove root",
                    tool="run_shell",
                    input={"command": "rm -rf /"},
                )
            ],
        )

        with patch("api.executor.execute_tool", AsyncMock()) as execute_tool:
            result = await execute_plan(plan, assume_yes=True)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.step_results[0].result["error"], "Tool safety check failed")
        self.assertEqual(result.step_results[0].result["rule"], "remove_root")
        self.assertEqual(result.events[-1]["reason"], "safety")
        execute_tool.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
