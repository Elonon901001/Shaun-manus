from pathlib import Path
import json
from typing import Any

from api.schemas import AgentPlan, ExecutionResult


def write_saved_run(
    run_dir: Path,
    plan: AgentPlan,
    result: ExecutionResult,
    events: list[dict[str, Any]] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    write_events(run_dir, events if events is not None else result.events)
    (run_dir / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")


def write_events(run_dir: Path, events: list[dict[str, Any]]) -> None:
    lines = [json.dumps(event, ensure_ascii=False) + "\n" for event in events]
    (run_dir / "events.jsonl").write_text("".join(lines), encoding="utf-8")
