from typing import Any

from api.runlog import read_events, read_plan, read_result
from api.schemas import AgentPlan, AgentStep, ExecutionResult, StepResult
from api.repair import find_failed_step


def explain_run(run_dir: str) -> str:
    """Build a repair-oriented context summary for a saved run."""
    plan = read_plan(run_dir)
    result = read_result(run_dir)
    events = read_events(run_dir)

    lines = [
        f"run: {run_dir}",
        "repair context",
        "",
        "goal:",
        f"  {plan.goal}",
        "",
        "status:",
        f"  {result.status}",
        "",
        "plan:",
    ]
    lines.extend(format_plan_steps(plan))

    completed_steps = [step_result for step_result in result.step_results if step_result.status == "completed"]
    failed_step = find_failed_step(result)
    remaining_steps = plan.steps[len(result.step_results) :]

    lines.append("")
    lines.append("completed steps:")
    lines.extend(format_completed_steps(completed_steps))

    lines.append("")
    lines.append("failed step:")
    lines.extend(format_failed_step(failed_step, result))

    lines.append("")
    lines.append("remaining steps:")
    lines.extend(format_remaining_steps(remaining_steps))

    lines.append("")
    lines.append("events:")
    lines.append(f"  count: {len(events)}")

    lines.append("")
    lines.append("repair hint:")
    lines.extend(format_repair_hint(failed_step, result))

    return "\n".join(lines)


def format_plan_steps(plan: AgentPlan) -> list[str]:
    if not plan.steps:
        return ["  none"]

    lines: list[str] = []
    for step in plan.steps:
        lines.append(f"  {step.id}: {step.tool}")
        lines.append(f"    thought: {step.thought}")
        lines.append(f"    input: {format_mapping(step.input)}")
    return lines


def format_completed_steps(step_results: list[StepResult]) -> list[str]:
    if not step_results:
        return ["  none"]

    lines: list[str] = []
    for step_result in step_results:
        lines.append(f"  {step_result.step.id}: {step_result.step.tool}")
        detail = summarize_result(step_result.result)
        if detail:
            lines.append(f"    {detail}")
    return lines


def format_failed_step(step_result: StepResult | None, result: ExecutionResult) -> list[str]:
    if step_result is None:
        if result.status == "completed":
            return ["  none"]
        return ["  unknown: no failed step result was recorded"]

    lines = [
        f"  id: {step_result.step.id}",
        f"  tool: {step_result.step.tool}",
        f"  status: {step_result.status}",
        f"  thought: {step_result.step.thought}",
        f"  input: {format_mapping(step_result.step.input)}",
    ]
    lines.extend(format_failure_details(step_result.result))
    return lines


def format_failure_details(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in ["error", "message", "rule", "exit_code", "stdout", "stderr"]:
        if key not in result:
            continue
        value = result.get(key)
        if value in (None, ""):
            continue
        lines.append(f"  {key}: {format_value(value)}")
    return lines


def format_remaining_steps(steps: list[AgentStep]) -> list[str]:
    if not steps:
        return ["  none"]

    return [f"  {step.id}: {step.tool}" for step in steps]


def format_repair_hint(step_result: StepResult | None, result: ExecutionResult) -> list[str]:
    if result.status == "completed":
        return ["  run completed; no repair needed"]

    if step_result is None:
        return ["  inspect result.json and events.jsonl; no failed step was recorded"]

    payload = step_result.result
    if payload.get("error") == "Tool input validation failed":
        return ["  fix the plan input schema before rerunning"]
    if payload.get("error") == "Tool safety check failed":
        return ["  replace the blocked shell command with a safer equivalent"]
    if step_result.status == "cancelled":
        return ["  rerun with confirmation or adjust the plan to avoid risky tools"]
    if "exit_code" in payload:
        return ["  inspect stdout/stderr, then change the command or prior file-writing steps"]
    if payload.get("error"):
        return ["  inspect the failed tool input and error message, then generate a corrected plan"]
    return ["  inspect the failed step result, then generate a corrected plan"]


def summarize_result(result: dict[str, Any]) -> str:
    if "bytes_written" in result:
        return f"path={result.get('path', '')}, bytes={result.get('bytes_written', 0)}"
    if "stdout" in result:
        stdout = str(result.get("stdout", "")).strip()
        return f"stdout={stdout[:120]}" if stdout else f"exit_code={result.get('exit_code', 0)}"
    if "content" in result:
        content = str(result.get("content", "")).strip()
        return f"content={content[:120]}" if content else f"path={result.get('path', '')}"
    if "entries" in result:
        return f"entries={len(result.get('entries') or [])}"
    return ""


def format_mapping(value: dict[str, Any]) -> str:
    if not value:
        return "{}"
    parts = [f"{key}={format_value(item)}" for key, item in value.items()]
    return ", ".join(parts)


def format_value(value: Any) -> str:
    text = str(value).strip()
    if "\n" in text:
        return repr(text)
    return text
