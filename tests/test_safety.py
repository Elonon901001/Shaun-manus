import unittest

from api.safety import check_step_safety
from api.schemas import AgentStep


class SafetyTests(unittest.TestCase):
    def test_safe_non_shell_step_passes(self) -> None:
        step = AgentStep(id="step_1", thought="list", tool="list_files", input={"path": "."})

        self.assertIsNone(check_step_safety(step))

    def test_safe_shell_step_passes(self) -> None:
        step = AgentStep(id="step_1", thought="pwd", tool="run_shell", input={"command": "pwd && ls -la"})

        self.assertIsNone(check_step_safety(step))

    def test_rm_root_is_blocked(self) -> None:
        step = AgentStep(id="step_1", thought="remove", tool="run_shell", input={"command": "rm -rf /"})

        result = check_step_safety(step)

        self.assertIsNotNone(result)
        self.assertEqual(result["error"], "Tool safety check failed")
        self.assertEqual(result["rule"], "remove_root")

    def test_docker_socket_is_blocked(self) -> None:
        step = AgentStep(
            id="step_1",
            thought="socket",
            tool="run_shell",
            input={"command": "cat /var/run/docker.sock"},
        )

        result = check_step_safety(step)

        self.assertIsNotNone(result)
        self.assertEqual(result["rule"], "docker_socket")


if __name__ == "__main__":
    unittest.main()
