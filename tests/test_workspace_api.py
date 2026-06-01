import unittest
from unittest.mock import AsyncMock, patch

from api import main
from api.schemas import AgentPlan, AgentStep, ChatRequest, ExecutionResult, Message, StepResult


class WorkspaceApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_workspace_list_delegates_to_list_files_tool(self) -> None:
        payload = {"path": ".", "entries": [{"name": "README.md", "type": "file"}]}

        with patch.object(main, "execute_tool", AsyncMock(return_value=payload)) as execute_tool:
            response = await main.workspace_list(".")

        self.assertEqual(response, payload)
        execute_tool.assert_awaited_once_with("list_files", {"path": "."})

    async def test_workspace_read_delegates_to_read_file_tool(self) -> None:
        payload = {"path": "README.md", "content": "hello\n", "truncated": False, "line_count": 1}

        with patch.object(main, "execute_tool", AsyncMock(return_value=payload)) as execute_tool:
            response = await main.workspace_read("README.md")

        self.assertEqual(response, payload)
        execute_tool.assert_awaited_once_with("read_file", {"path": "README.md"})

    async def test_chat_stream_uses_agent_plan_executor(self) -> None:
        plan = AgentPlan(
            goal="看看文件",
            steps=[AgentStep(id="step_1", thought="list", tool="list_files", input={"path": "."})],
        )
        execution = ExecutionResult(
            plan=plan,
            step_results=[
                StepResult(
                    step=plan.steps[0],
                    status="completed",
                    result={"path": ".", "entries": []},
                )
            ],
            events=[{"type": "execution_finished", "status": "completed"}],
            status="completed",
        )
        request = ChatRequest(messages=[Message(role="user", content="看看文件")])

        with patch.object(main, "build_plan", return_value=plan) as build_plan:
            with patch.object(main, "execute_plan", AsyncMock(return_value=execution)) as execute_plan:
                chunks = [chunk async for chunk in main.stream_reply(request)]

        payload = b"".join(chunks).decode("utf-8")
        self.assertIn('"type": "plan"', payload)
        self.assertIn('"type": "tool_end"', payload)
        self.assertIn('"type": "done"', payload)
        build_plan.assert_called_once_with("看看文件")
        execute_plan.assert_awaited_once_with(plan, assume_yes=True)


if __name__ == "__main__":
    unittest.main()
