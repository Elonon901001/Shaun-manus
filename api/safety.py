import re
from dataclasses import dataclass
from typing import Any

from api.schemas import AgentStep


@dataclass(frozen=True)
class ShellSafetyRule:
    name: str
    pattern: re.Pattern[str]
    message: str


DANGEROUS_SHELL_PATTERNS: list[ShellSafetyRule] = [
    ShellSafetyRule(
        name="remove_root",
        pattern=re.compile(r"\brm\s+-[^\n]*r[^\n]*f[^\n]*(?:/|\*)", re.IGNORECASE),
        message="Recursive force remove against root-like paths is blocked.",
    ),
    ShellSafetyRule(
        name="format_disk",
        pattern=re.compile(r"\bmkfs(?:\.\w+)?\b", re.IGNORECASE),
        message="Filesystem formatting commands are blocked.",
    ),
    ShellSafetyRule(
        name="power_control",
        pattern=re.compile(r"\b(shutdown|reboot|poweroff|halt)\b", re.IGNORECASE),
        message="Power control commands are blocked.",
    ),
    ShellSafetyRule(
        name="fork_bomb",
        pattern=re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", re.IGNORECASE),
        message="Fork bomb patterns are blocked.",
    ),
    ShellSafetyRule(
        name="raw_disk_write",
        pattern=re.compile(r"\bdd\s+[^;\n]*\bif=", re.IGNORECASE),
        message="Raw disk copy commands are blocked.",
    ),
    ShellSafetyRule(
        name="docker_socket",
        pattern=re.compile(r"(docker\.sock|/var/run/docker\.sock)", re.IGNORECASE),
        message="Docker socket access is blocked.",
    ),
    ShellSafetyRule(
        name="wide_open_permissions",
        pattern=re.compile(r"\bchmod\s+-R\s+777\s+/", re.IGNORECASE),
        message="Recursive chmod 777 against root-like paths is blocked.",
    ),
    ShellSafetyRule(
        name="recursive_chown",
        pattern=re.compile(r"\bchown\s+-R\b", re.IGNORECASE),
        message="Recursive chown commands are blocked.",
    ),
]


def check_step_safety(step: AgentStep) -> dict[str, Any] | None:
    if step.tool != "run_shell":
        return None

    command = str(step.input.get("command", ""))

    for rule in DANGEROUS_SHELL_PATTERNS:
        if rule.pattern.search(command):
            return safety_error(step, rule, command)

    return None


def safety_error(step: AgentStep, rule: ShellSafetyRule, command: str) -> dict[str, Any]:
    return {
        "error": "Tool safety check failed",
        "message": rule.message,
        "rule": rule.name,
        "tool": step.tool,
        "input": step.input,
        "command": command,
    }