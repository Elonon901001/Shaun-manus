import unittest

from api.tool_manifest import (
    get_tool_manifest,
    optional_input_fields,
    required_input_fields,
    tool_manifest_payload,
)


class ToolManifestTests(unittest.TestCase):
    def test_manifest_lists_current_tools(self) -> None:
        payload = tool_manifest_payload()
        tool_names = {tool["name"] for tool in payload["tools"]}

        self.assertEqual(payload["version"], "tool_manifest.v1")
        self.assertEqual(tool_names, {"run_shell", "list_files", "read_file", "write_file", "replace_text", "patch_file"})

    def test_write_file_manifest_declares_inputs_and_risk(self) -> None:
        manifest = get_tool_manifest("write_file")

        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.risk, "write")
        self.assertEqual(required_input_fields(manifest), {"path": str, "content": str})
        self.assertEqual(optional_input_fields(manifest), {})

    def test_list_files_path_is_optional(self) -> None:
        manifest = get_tool_manifest("list_files")

        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(required_input_fields(manifest), {})
        self.assertEqual(optional_input_fields(manifest), {"path": str})

    def test_payload_is_planner_readable(self) -> None:
        payload = tool_manifest_payload()
        write_file = next(tool for tool in payload["tools"] if tool["name"] == "write_file")

        self.assertEqual(write_file["input_schema"]["path"]["type"], "str")
        self.assertTrue(write_file["input_schema"]["path"]["required"])
        self.assertEqual(write_file["risk"], "write")
        self.assertTrue(write_file["examples"])

    def test_replace_text_manifest_declares_precise_edit_inputs(self) -> None:
        manifest = get_tool_manifest("replace_text")

        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.risk, "write")
        self.assertEqual(
            required_input_fields(manifest),
            {"path": str, "old_text": str, "new_text": str},
        )
        self.assertEqual(optional_input_fields(manifest), {})

    def test_patch_file_manifest_declares_structured_patch_inputs(self) -> None:
        manifest = get_tool_manifest("patch_file")

        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest.risk, "write")
        self.assertEqual(required_input_fields(manifest), {"path": str, "edits": list})
        self.assertEqual(optional_input_fields(manifest), {})


if __name__ == "__main__":
    unittest.main()
