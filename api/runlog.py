import json
from datetime import datetime
from pathlib import Path
from typing import Any

from api.schemas import AgentPlan, ExecutionResult


def create_run_dir(root: str = "runs") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(root) / f"run_{timestamp}"
    suffix = 1

    while run_dir.exists():
        run_dir = Path(root) / f"run_{timestamp}_{suffix}"
        suffix += 1

    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_plan(run_dir: Path, plan: AgentPlan) -> None:
    path = run_dir / "plan.json"
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")


def write_events(run_dir: Path, events: list[dict[str, Any]]) -> None:
    path = run_dir / "events.jsonl"
    lines = [json.dumps(event, ensure_ascii=False) for event in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_result(run_dir: Path, result: ExecutionResult) -> None:
    path = run_dir / "result.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def save_run(plan: AgentPlan, result: ExecutionResult, root: str = "runs") -> Path:
    run_dir = create_run_dir(root)
    write_plan(run_dir, plan)
    write_events(run_dir, result.events)
    write_result(run_dir, result)
    return run_dir


def read_plan(run_dir: str | Path) -> AgentPlan:
    path = Path(run_dir) / "plan.json"
    return AgentPlan.model_validate_json(path.read_text(encoding="utf-8"))


def read_events(run_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "events.jsonl"
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def read_result(run_dir: str | Path) -> ExecutionResult:
    path = Path(run_dir) / "result.json"
    return ExecutionResult.model_validate_json(path.read_text(encoding="utf-8"))
