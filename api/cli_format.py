import json
from typing import Any

from api.policy import get_tool_risk
from api.runlog import read_events, read_plan, read_result
from api.schemas import AgentPlan

ToolResult = dict[str, Any]


def format_result(result: ToolResult) -> str:
    if "entries" in result:
        entries = result.get("entries") or []
        if not entries:
            return f"{result.get('path', '.')}: empty"
        lines = [f"{result.get('path', '.')}:"] 
        lines.extend(f"  {entry['type']:<9} {entry['name']}" for entry in entries)
        return "\n".join(lines)

    if "content" in result:
        header = f"{result.get('path', '')}:"
        suffix = "\n[truncated after 200 lines]" if result.get("truncated") else ""
        return f"{header}\n{result.get('content', '')}{suffix}"

    if "bytes_written" in result:
        return f"wrote {result.get('bytes_written', 0)} bytes to {result.get('path', '')}"

    if "stdout" in result or "stderr" in result:
        parts = []
        stdout = str(result.get("stdout", "")).rstrip()
        stderr = str(result.get("stderr", "")).rstrip()
        if stdout:
            parts.append(stdout)
        if stderr:
            parts.append(f"[stderr]\n{stderr}")
        if not parts:
            parts.append(f"exit_code={result.get('exit_code', 0)}")
        return "\n".join(parts)

    return json.dumps(result, ensure_ascii=False, indent=2)


def print_plan(plan: AgentPlan) -> None:
    print(f"goal: {plan.goal}")
    print("plan:")
    for step in plan.steps:
        print(f"  {step.id}: {step.tool} ({get_tool_risk(step.tool)})")
        print(f"    thought: {step.thought}")
        print(f"    input: {json.dumps(step.input, ensure_ascii=False)}")


def inspect_run(run_dir: str) -> str:
    plan = read_plan(run_dir)
    result = read_result(run_dir)
    events = read_events(run_dir)

    lines = [
        f"run: {run_dir}",
        f"goal: {plan.goal}",
        f"status: {result.status}",
        f"steps: {len(result.step_results)}/{len(plan.steps)}",
    ]

    if events:
        lines.append(f"events: {len(events)}")

    lines.append("")
    lines.append("step results:")
    for step_result in result.step_results:
        step = step_result.step
        lines.append(f"  {step.id} {step.tool} {step_result.status}")
        detail = summarize_step_result(step_result.result)
        if detail:
            lines.append(f"    {detail}")

    missing_steps = plan.steps[len(result.step_results) :]
    for step in missing_steps:
        lines.append(f"  {step.id} {step.tool} not_run")

    return "\n".join(lines)


def summarize_step_result(result: ToolResult) -> str:
    if result.get("error"):
        message = result.get("message") or result.get("stderr") or result.get("error")
        return f"error: {message}"
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
