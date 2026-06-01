from dataclasses import dataclass
from typing import Any

from api.schemas import AgentStep
from api.tool_manifest import get_tool_manifest, optional_input_fields, required_input_fields


@dataclass(frozen=True)
class ToolInputRule:
    required: dict[str, type]
    optional: dict[str, type] | None = None


def validate_step(step: AgentStep) -> dict[str, Any] | None:
    manifest = get_tool_manifest(step.tool)
    if manifest is None:
        return validation_error(step, f"Unknown tool: {step.tool}")

    rule = ToolInputRule(
        required=required_input_fields(manifest),
        optional=optional_input_fields(manifest),
    )
    allowed_fields = set(rule.required)
    if rule.optional:
        allowed_fields.update(rule.optional)

    extra_fields = sorted(set(step.input) - allowed_fields)
    if extra_fields:
        return validation_error(step, f"Unexpected input field(s): {', '.join(extra_fields)}")

    for field_name, expected_type in rule.required.items():
        if field_name not in step.input:
            return validation_error(step, f"{step.tool} requires input.{field_name}")
        if not isinstance(step.input[field_name], expected_type):
            return validation_error(
                step,
                f"{step.tool} input.{field_name} must be {expected_type.__name__}",
            )
        if expected_type is str and not step.input[field_name].strip():
            return validation_error(step, f"{step.tool} input.{field_name} cannot be empty")

    for field_name, expected_type in (rule.optional or {}).items():
        if field_name in step.input and not isinstance(step.input[field_name], expected_type):
            return validation_error(
                step,
                f"{step.tool} input.{field_name} must be {expected_type.__name__}",
            )

    return None


def validation_error(step: AgentStep, message: str) -> dict[str, Any]:
    return {
        "error": "Tool input validation failed",
        "message": message,
        "tool": step.tool,
        "input": step.input,
    }
