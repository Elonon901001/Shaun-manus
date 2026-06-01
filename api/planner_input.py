from typing import Any

from pydantic import BaseModel, Field

from api.tool_manifest import tool_manifest_payload


class PlannerInput(BaseModel):
    message: str
    tool_manifest: dict[str, Any]
    constraints: dict[str, Any] = Field(default_factory=dict)
    workspace: dict[str, Any] = Field(default_factory=dict)
    repair_context: dict[str, Any] | None = None


def build_planner_input(message: str) -> PlannerInput:
    return PlannerInput(
        message=message,
        tool_manifest=tool_manifest_payload(),
        constraints={
            "plan_version": "planner.v1",
            "max_steps": 8,
            "sandbox": "All tools run inside the Docker workspace.",
            "must_use_tools_from_manifest": True,
            "llm_must_not_execute_tools": True,
        },
    )