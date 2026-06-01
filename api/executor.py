from collections.abc import Callable
import re
from typing import Any

from api.policy import requires_confirmation
from api.safety import check_step_safety
from api.schemas import AgentPlan, AgentStep, ExecutionResult, StepResult
from api.tools import execute_tool
from api.validation import validate_step

ConfirmCallback = Callable[[AgentStep], bool]
ToolResult = dict[str, Any]


async def execute_plan(
    plan: AgentPlan,
    *,
    assume_yes: bool = False,
    confirm: ConfirmCallback | None = None,
) -> ExecutionResult:
    step_results: list[StepResult] = []
    events: list[dict[str, Any]] = [{"type": "execution_started", "max_steps": plan.max_steps}]
    context: dict[str, Any] = {"plan": plan.context.copy(), "steps": {}}

    for index, step in enumerate(plan.steps):
        if index >= plan.max_steps:
            events.append({"type": "max_steps_reached", "max_steps": plan.max_steps})
            return ExecutionResult(plan=plan, step_results=step_results, events=events, status="failed")

        resolved_step = resolve_step_inputs(step, context)
        events.append({"type": "step_started", "step_id": resolved_step.id, "tool": resolved_step.tool})

        validation_result = validate_step(resolved_step)
        if validation_result is not None:
            step_results.append(StepResult(step=resolved_step, status="failed", result=validation_result))
            events.append(
                {
                    "type": "step_finished",
                    "step_id": resolved_step.id,
                    "status": "failed",
                    "reason": "validation",
                }
            )
            return ExecutionResult(plan=plan, step_results=step_results, events=events, status="failed")

        safety_result = check_step_safety(resolved_step)
        if safety_result is not None:
            step_results.append(StepResult(step=resolved_step, status="failed", result=safety_result))
            events.append(
                {
                    "type": "step_finished",
                    "step_id": resolved_step.id,
                    "status": "failed",
                    "reason": "safety",
                }
            )
            return ExecutionResult(plan=plan, step_results=step_results, events=events, status="failed")

        if requires_confirmation(resolved_step.tool) and not assume_yes:
            if confirm is None or not confirm(resolved_step):
                step_results.append(StepResult(step=resolved_step, status="cancelled", result={}))
                events.append({"type": "step_cancelled", "step_id": resolved_step.id})
                return ExecutionResult(plan=plan, step_results=step_results, events=events, status="cancelled")

        result = await execute_tool(resolved_step.tool, resolved_step.input)
        status = "failed" if is_failed_result(result) else "completed"
        step_results.append(StepResult(step=resolved_step, status=status, result=result))
        context["steps"][resolved_step.id] = {"status": status, "result": result}
        events.append({"type": "step_finished", "step_id": resolved_step.id, "status": status})

        if status == "failed":
            return ExecutionResult(plan=plan, step_results=step_results, events=events, status="failed")

    events.append({"type": "execution_finished", "status": "completed"})
    return ExecutionResult(plan=plan, step_results=step_results, events=events, status="completed")


def is_failed_result(result: ToolResult) -> bool:
    if result.get("error"):
        return True
    if "exit_code" in result:
        return int(result.get("exit_code") or 0) != 0
    return False


def resolve_step_inputs(step: AgentStep, context: dict[str, Any]) -> AgentStep:
    return AgentStep(
        id=step.id,
        thought=step.thought,
        tool=step.tool,
        input=resolve_value(step.input, context),
    )


def resolve_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return resolve_references(value, context)
    if isinstance(value, list):
        return [resolve_value(item, context) for item in value]
    if isinstance(value, dict):
        return {key: resolve_value(item, context) for key, item in value.items()}
    return value


def resolve_references(text: str, context: dict[str, Any]) -> str:
    pattern = re.compile(r"\$\{([A-Za-z0-9_-]+)\.result\.([A-Za-z0-9_.-]+)\}")

    def replace(match: re.Match[str]) -> str:
        step_id = match.group(1)
        path = match.group(2).split(".")
        value: Any = context.get("steps", {}).get(step_id, {}).get("result", {})
        for part in path:
            if not isinstance(value, dict) or part not in value:
                return match.group(0)
            value = value[part]
        return str(value)

    return pattern.sub(replace, text)
