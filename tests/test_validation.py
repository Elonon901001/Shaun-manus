import unittest

from api.schemas import AgentStep
from api.validation import validate_step


class ValidationTests(unittest.TestCase):
    def test_valid_write_file_step_passes(self) -> None:
        step = AgentStep(
            id="step_1",
            thought="write",
            tool="write_file",
            input={"path": "a.txt", "content": "hello"},
        )

        self.assertIsNone(validate_step(step))

    def test_valid_replace_text_step_passes(self) -> None:
        step = AgentStep(
            id="step_1",
            thought="replace",
            tool="replace_text",
            input={"path": "a.txt", "old_text": "hello", "new_text": "hi"},
        )

        self.assertIsNone(validate_step(step))

    def test_valid_patch_file_step_passes(self) -> None:
        step = AgentStep(
            id="step_1",
            thought="patch",
            tool="patch_file",
            input={
                "path": "a.txt",
                "edits": [{"old_text": "hello", "new_text": "hi"}],
            },
        )

        self.assertIsNone(validate_step(step))

    def test_missing_required_field_fails(self) -> None:
        step = AgentStep(id="step_1", thought="write", tool="write_file", input={"content": "hello"})

        result = validate_step(step)

        self.assertIsNotNone(result)
        self.assertEqual(result["error"], "Tool input validation failed")
        self.assertEqual(result["message"], "write_file requires input.path")

    def test_wrong_type_fails(self) -> None:
        step = AgentStep(id="step_1", thought="read", tool="read_file", input={"path": 123})

        result = validate_step(step)

        self.assertIsNotNone(result)
        self.assertEqual(result["message"], "read_file input.path must be str")

    def test_unknown_tool_fails(self) -> None:
        step = AgentStep(id="step_1", thought="unknown", tool="nope", input={})

        result = validate_step(step)

        self.assertIsNotNone(result)
        self.assertEqual(result["message"], "Unknown tool: nope")

    def test_unexpected_field_fails(self) -> None:
        step = AgentStep(id="step_1", thought="list", tool="list_files", input={"path": ".", "limit": 10})

        result = validate_step(step)

        self.assertIsNotNone(result)
        self.assertEqual(result["message"], "Unexpected input field(s): limit")


if __name__ == "__main__":
    unittest.main()
