from dataclasses import dataclass
import re

from api.runlog import read_plan, read_result
from api.schemas import AgentPlan, AgentStep, ExecutionResult, StepResult


@dataclass(frozen=True)
class RepairPlanBuildResult:
    status: str
    plan: AgentPlan | None = None
    reason: str = ""


OPEN_TO_CLOSE = {
    "(": ")",
    "[": "]",
    "{": "}",
}

CLOSE_TO_OPEN = {close: open_char for open_char, close in OPEN_TO_CLOSE.items()}


def build_repair_plan(run_dir: str) -> RepairPlanBuildResult:
    """Build a deterministic repair plan for supported failed runs."""
    original_plan = read_plan(run_dir)
    result = read_result(run_dir)

    if result.status == "completed":
        return RepairPlanBuildResult(status="unsupported", reason="run already completed")

    failed_step = find_failed_step(result)
    if failed_step is None:
        return RepairPlanBuildResult(status="unsupported", reason="no failed step was recorded")

    if failed_step.step.tool != "run_shell":
        return RepairPlanBuildResult(status="unsupported", reason=f"unsupported failed tool: {failed_step.step.tool}")

    repaired_plan = repair_python_unclosed_delimiter(run_dir, original_plan, result, failed_step)
    if repaired_plan is None:
        return RepairPlanBuildResult(status="unsupported", reason=classify_unsupported_failure(failed_step))

    return RepairPlanBuildResult(status="ready", plan=repaired_plan)


def classify_unsupported_failure(failed_step: StepResult) -> str:
    stderr = str(failed_step.result.get("stderr", ""))
    if "NameError:" in stderr:
        return "NameError repair requires semantic planner"
    if "ModuleNotFoundError:" in stderr or "No module named" in stderr:
        return "ModuleNotFoundError repair requires dependency policy"
    if "SyntaxError:" in stderr:
        return "unsupported Python SyntaxError"
    return "no matching repair rule"


def repair_python_unclosed_delimiter(
    run_dir: str,
    original_plan: AgentPlan,
    result: ExecutionResult,
    failed_step: StepResult,
) -> AgentPlan | None:
    """Repair simple Python files whose generated content is missing closing delimiters."""
    stderr = str(failed_step.result.get("stderr", ""))
    if "SyntaxError" not in stderr or "was never closed" not in stderr:
        return None

    command = str(failed_step.step.input.get("command", ""))
    path = extract_python_command_path(command)
    if path is None:
        return None

    write_step = find_completed_write_for_path(result, path)
    if write_step is None:
        return None

    original_content = str(write_step.step.input.get("content", ""))
    repaired_content = close_missing_delimiters(original_content)
    if repaired_content == original_content:
        return None

    repair_steps = [
        AgentStep(
            id="repair_1",
            thought=f"Patch {path} by adding missing closing delimiter(s).",
            tool="patch_file",
            input={
                "path": path,
                "edits": [{"old_text": original_content, "new_text": repaired_content}],
            },
        ),
        AgentStep(
            id="repair_2",
            thought=f"Rerun the failed command from {failed_step.step.id}.",
            tool=failed_step.step.tool,
            input=failed_step.step.input,
        ),
    ]
    repair_steps.extend(copy_remaining_steps(original_plan, result, start_index=3))

    return AgentPlan(
        version=original_plan.version,
        source="repair-rule",
        goal=f"Repair failed run: {original_plan.goal}",
        max_steps=max(original_plan.max_steps, len(repair_steps)),
        context={
            **original_plan.context,
            "repair_of": run_dir,
            "failed_step_id": failed_step.step.id,
            "repair_rule": "python_unclosed_delimiter",
        },
        steps=repair_steps,
    )


def extract_python_command_path(command: str) -> str | None:
    match = re.search(r"(?:^|&&|\|\||;)\s*python(?:\d(?:\.\d+)?)?\s+([^\s;&|]+\.py)\b", command)
    return match.group(1) if match else None


def find_completed_write_for_path(result: ExecutionResult, path: str) -> StepResult | None:
    for step_result in result.step_results:
        if step_result.status != "completed":
            continue
        if step_result.step.tool != "write_file":
            continue
        if step_result.step.input.get("path") == path:
            return step_result
    return None


def close_missing_delimiters(content: str) -> str:
    stack: list[str] = []

    for char in content:
        if char in OPEN_TO_CLOSE:
            stack.append(char)
            continue

        if char in CLOSE_TO_OPEN and stack and stack[-1] == CLOSE_TO_OPEN[char]:
            stack.pop()

    if not stack:
        return content

    missing_closers = "".join(OPEN_TO_CLOSE[char] for char in reversed(stack))
    return content + missing_closers


def copy_remaining_steps(original_plan: AgentPlan, result: ExecutionResult, start_index: int) -> list[AgentStep]:
    remaining_steps = original_plan.steps[len(result.step_results) :]
    copied_steps: list[AgentStep] = []
    for offset, step in enumerate(remaining_steps):
        copied_steps.append(
            AgentStep(
                id=f"repair_{start_index + offset}",
                thought=f"Continue original remaining step {step.id}: {step.thought}",
                tool=step.tool,
                input=step.input,
            )
        )
    return copied_steps


def find_failed_step(result: ExecutionResult) -> StepResult | None:
    """Return the first non-completed step result."""
    for step_result in result.step_results:
        if step_result.status != "completed":
            return step_result
    return None
