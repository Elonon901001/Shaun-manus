import json
import unittest
from unittest.mock import patch

from api.llm_planner import (
    agent_plan_json_schema,
    build_llm_plan,
    build_openai_payload,
    build_system_prompt,
    extract_response_text,
)
from api.planner_input import build_planner_input


class LlmPlannerTests(unittest.TestCase):
    def test_system_prompt_preserves_planner_boundary(self) -> None:
        prompt = build_system_prompt()

        self.assertIn("Planner", prompt)
        self.assertIn("planner.v1", prompt)
        self.assertIn("Do not execute tools", prompt)
        self.assertIn("Never invent tools", prompt)

    def test_agent_plan_json_schema_requires_goal_and_steps(self) -> None:
        schema = agent_plan_json_schema()

        self.assertEqual(schema["type"], "object")
        self.assertEqual(schema["required"], ["goal", "steps"])

        step_schema = schema["properties"]["steps"]["items"]
        self.assertEqual(step_schema["required"], ["id", "thought", "tool", "input"])

    def test_build_openai_payload_includes_planner_input_and_schema(self) -> None:
        planner_input = build_planner_input("inspect files")

        payload = build_openai_payload(planner_input, "test-model")

        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["input"][0]["role"], "system")
        self.assertIn("Do not execute tools", payload["input"][0]["content"])
        self.assertEqual(payload["input"][1]["role"], "user")

        user_payload = json.loads(payload["input"][1]["content"])
        self.assertEqual(user_payload["message"], "inspect files")
        self.assertTrue(user_payload["constraints"]["llm_must_not_execute_tools"])
        self.assertIn("tools", user_payload["tool_manifest"])

        text_format = payload["text"]["format"]
        self.assertEqual(text_format["type"], "json_schema")
        self.assertEqual(text_format["name"], "agent_plan")
        self.assertEqual(text_format["schema"]["required"], ["goal", "steps"])

    def test_extract_response_text_from_output_text(self) -> None:
        text = extract_response_text({"output_text": '{"goal": "x", "steps": []}'})

        self.assertEqual(text, '{"goal": "x", "steps": []}')

    def test_extract_response_text_from_message_content(self) -> None:
        text = extract_response_text(
            {
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"goal": "x", "steps": []}',
                            }
                        ],
                    }
                ]
            }
        )

        self.assertEqual(text, '{"goal": "x", "steps": []}')

    def test_extract_response_text_fails_when_missing(self) -> None:
        with self.assertRaises(ValueError):
            extract_response_text({"output": []})

    def test_build_llm_plan_requires_api_key_before_network_call(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with patch("api.llm_planner.call_openai_responses") as call_openai_responses:
                with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY"):
                    build_llm_plan("inspect files")

        call_openai_responses.assert_not_called()

    def test_build_llm_plan_normalizes_mock_response(self) -> None:
        response_text = json.dumps(
            {
                "goal": "inspect files",
                "steps": [
                    {
                        "id": "step_1",
                        "thought": "list workspace files",
                        "tool": "list_files",
                        "input": {"path": "."},
                    }
                ],
            }
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
            with patch(
                "api.llm_planner.call_openai_responses",
                return_value={"output_text": response_text},
            ) as call_openai_responses:
                plan = build_llm_plan("inspect files", model="test-model")

        self.assertEqual(plan.version, "planner.v1")
        self.assertEqual(plan.source, "llm")
        self.assertEqual(plan.goal, "inspect files")
        self.assertEqual(plan.steps[0].tool, "list_files")
        self.assertEqual(plan.steps[0].input, {"path": "."})

        call_openai_responses.assert_called_once()
        payload, api_key = call_openai_responses.call_args.args
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(api_key, "test-key")


if __name__ == "__main__":
    unittest.main()
