import unittest

from api.policy import get_tool_risk, requires_confirmation


class PolicyTests(unittest.TestCase):
    def test_read_tools_are_safe(self) -> None:
        self.assertEqual(get_tool_risk("list_files"), "safe")
        self.assertEqual(get_tool_risk("read_file"), "safe")
        self.assertFalse(requires_confirmation("list_files"))
        self.assertFalse(requires_confirmation("read_file"))

    def test_write_and_shell_require_confirmation(self) -> None:
        self.assertTrue(requires_confirmation("write_file"))
        self.assertTrue(requires_confirmation("replace_text"))
        self.assertTrue(requires_confirmation("patch_file"))
        self.assertTrue(requires_confirmation("run_shell"))


if __name__ == "__main__":
    unittest.main()
