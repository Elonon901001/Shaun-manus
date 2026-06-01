import unittest
from unittest.mock import AsyncMock, patch

from api import tools


class ToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_files_returns_structured_entries(self) -> None:
        result_payload = '{"path": ".", "entries": [{"name": "README.md", "type": "file"}]}'

        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 0, "stdout": result_payload, "stderr": ""}),
        ):
            result = await tools.list_files_tool({"path": "."})

        self.assertEqual(result["path"], ".")
        self.assertEqual(result["entries"], [{"name": "README.md", "type": "file"}])

    async def test_read_file_returns_structured_content(self) -> None:
        result_payload = '{"path": "README.md", "content": "hello\\n", "truncated": false, "line_count": 1}'

        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 0, "stdout": result_payload, "stderr": ""}),
        ):
            result = await tools.read_file_tool({"path": "README.md"})

        self.assertEqual(result["path"], "README.md")
        self.assertEqual(result["content"], "hello\n")
        self.assertFalse(result["truncated"])
        self.assertEqual(result["line_count"], 1)

    async def test_read_file_missing_path_returns_structured_error(self) -> None:
        result = await tools.read_file_tool({"path": ""})

        self.assertEqual(result["path"], "")
        self.assertEqual(result["content"], "")
        self.assertFalse(result["truncated"])
        self.assertEqual(result["error"], "Missing path")

    async def test_write_file_returns_structured_result(self) -> None:
        result_payload = '{"path": "notes/hello.txt", "bytes_written": 6, "created": true}'

        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 0, "stdout": result_payload, "stderr": ""}),
        ) as run_shell:
            result = await tools.write_file_tool({"path": "notes/hello.txt", "content": "hello\n"})

        self.assertEqual(result["path"], "notes/hello.txt")
        self.assertEqual(result["bytes_written"], 6)
        self.assertTrue(result["created"])
        self.assertIn("aGVsbG8K", run_shell.await_args.args[0])

    async def test_write_file_missing_path_returns_structured_error(self) -> None:
        result = await tools.write_file_tool({"path": "", "content": "hello"})

        self.assertEqual(result["path"], "")
        self.assertEqual(result["bytes_written"], 0)
        self.assertEqual(result["error"], "Missing path")

    async def test_replace_text_returns_structured_result(self) -> None:
        result_payload = '{"path": "hello.py", "replacements": 1, "bytes_written": 14}'

        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 0, "stdout": result_payload, "stderr": ""}),
        ) as run_shell:
            result = await tools.replace_text_tool(
                {"path": "hello.py", "old_text": "print('hi')", "new_text": "print('hello')"}
            )

        self.assertEqual(result["path"], "hello.py")
        self.assertEqual(result["replacements"], 1)
        self.assertEqual(result["bytes_written"], 14)
        self.assertIn("cHJpbnQoJ2hpJyk=", run_shell.await_args.args[0])
        self.assertIn("cHJpbnQoJ2hlbGxvJyk=", run_shell.await_args.args[0])

    async def test_replace_text_missing_old_text_returns_structured_error(self) -> None:
        result = await tools.replace_text_tool({"path": "hello.py", "old_text": "", "new_text": "x"})

        self.assertEqual(result["path"], "hello.py")
        self.assertEqual(result["replacements"], 0)
        self.assertEqual(result["bytes_written"], 0)
        self.assertEqual(result["error"], "Missing old_text")

    async def test_replace_text_surfaces_non_unique_match_error(self) -> None:
        result_payload = (
            '{"path": "hello.py", "replacements": 0, "bytes_written": 0, '
            '"error": "old_text is not unique", "matches": 2}'
        )

        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 1, "stdout": result_payload, "stderr": ""}),
        ):
            result = await tools.replace_text_tool(
                {"path": "hello.py", "old_text": "print", "new_text": "console.log"}
            )

        self.assertEqual(result["error"], "old_text is not unique")
        self.assertEqual(result["matches"], 2)

    async def test_patch_file_returns_structured_result(self) -> None:
        result_payload = '{"path": "settings.py", "applied_edits": 2, "bytes_written": 28}'

        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 0, "stdout": result_payload, "stderr": ""}),
        ) as run_shell:
            result = await tools.patch_file_tool(
                {
                    "path": "settings.py",
                    "edits": [
                        {"old_text": "timeout = 20", "new_text": "timeout = 30"},
                        {"old_text": "retries = 1", "new_text": "retries = 3"},
                    ],
                }
            )

        self.assertEqual(result["path"], "settings.py")
        self.assertEqual(result["applied_edits"], 2)
        self.assertEqual(result["bytes_written"], 28)
        self.assertIn("settings.py", run_shell.await_args.args[0])

    async def test_patch_file_missing_edits_returns_structured_error(self) -> None:
        result = await tools.patch_file_tool({"path": "settings.py", "edits": []})

        self.assertEqual(result["path"], "settings.py")
        self.assertEqual(result["applied_edits"], 0)
        self.assertEqual(result["bytes_written"], 0)
        self.assertEqual(result["error"], "Missing edits")

    async def test_patch_file_surfaces_failed_edit_index(self) -> None:
        result_payload = (
            '{"path": "settings.py", "applied_edits": 0, "bytes_written": 0, '
            '"error": "old_text not found", "edit_index": 1}'
        )

        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 1, "stdout": result_payload, "stderr": ""}),
        ):
            result = await tools.patch_file_tool(
                {
                    "path": "settings.py",
                    "edits": [
                        {"old_text": "timeout = 20", "new_text": "timeout = 30"},
                        {"old_text": "missing", "new_text": "value"},
                    ],
                }
            )

        self.assertEqual(result["error"], "old_text not found")
        self.assertEqual(result["edit_index"], 1)

    async def test_invalid_json_returns_structured_error(self) -> None:
        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 0, "stdout": "not-json", "stderr": ""}),
        ):
            result = await tools.run_structured_python("print('not-json')", ".")

        self.assertEqual(result["error"], "Tool returned invalid JSON")
        self.assertEqual(result["raw_stdout"], "not-json")

    async def test_empty_stdout_includes_stderr(self) -> None:
        with patch.object(
            tools,
            "run_shell",
            AsyncMock(return_value={"exit_code": 1, "stdout": "", "stderr": "Docker unavailable"}),
        ):
            result = await tools.run_structured_python("print('hello')", ".")

        self.assertEqual(result["error"], "Tool returned no JSON")
        self.assertEqual(result["stderr"], "Docker unavailable")


if __name__ == "__main__":
    unittest.main()
