import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from api.cli_format import inspect_run
from api.cli_runner import run_plan, run_repl, run_task
from api.planner import build_plan, plan_from_json, plan_to_json
from api.repair import build_repair_plan
from api.repair_explain import explain_run
from api.schemas import AgentPlan, AgentStep
from api.tool_manifest import tool_manifest_json

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_plan_file(path: str) -> AgentPlan:
    return plan_from_json(Path(path).read_text(encoding="utf-8"))


def load_run_plan(run_dir: str) -> AgentPlan:
    return load_plan_file(str(Path(run_dir) / "plan.json"))


def load_local_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Manus-like sandbox tasks from the command line.")
    parser.add_argument("message", nargs="*", help="Task text to send to the rule-based Agent planner.")
    parser.add_argument("-i", "--interactive", action="store_true", help="Start an interactive REPL.")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-confirm write and shell tools.")
    parser.add_argument("--json", action="store_true", help="Emit newline-delimited JSON events.")
    parser.add_argument("--plan-only", action="store_true", help="Print the normalized plan JSON without executing it.")
    parser.add_argument("--plan-file", help="Read a planner.v1 JSON plan from a file and execute it.")
    parser.add_argument("--rerun", help="Rerun a saved run directory by loading its plan.json.")
    parser.add_argument("--inspect-run", help="Print a summary of a saved run directory.")
    parser.add_argument("--explain-run", help="Print repair context for a saved run directory.")
    parser.add_argument("--repair-run", help="Build and execute a repair plan for a saved failed run directory.")
    parser.add_argument("--tool-manifest", action="store_true", help="Print available tools as a JSON manifest.")
    parser.add_argument("--save-run", action="store_true", help="Save plan, events, and result under runs/.")
    parser.add_argument("--runs-dir", default="runs", help="Directory used by --save-run.")
    parser.add_argument("--planner", choices=["rule", "llm"], default="rule", help="Planner backend to use for task messages.")
    parser.add_argument("--llm-model", help="OpenAI model to use with --planner llm.")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    load_local_env()

    parser = build_parser()
    args = parser.parse_args(argv)
    message = " ".join(args.message).strip()

    selected_run_modes = [
        bool(args.plan_file),
        bool(args.rerun),
        bool(args.inspect_run),
        bool(args.explain_run),
        bool(args.repair_run),
        bool(args.tool_manifest),
    ]
    if sum(selected_run_modes) > 1:
        parser.error(
            "--plan-file, --rerun, --inspect-run, --explain-run, --repair-run, and --tool-manifest are mutually exclusive"
        )

    if args.llm_model and args.planner != "llm":
        parser.error("--llm-model requires --planner llm")

    if any(selected_run_modes):
        if args.planner != "rule":
            parser.error("--planner can only be used with a task message or --interactive")
        if args.llm_model:
            parser.error("--llm-model can only be used with --planner llm")

    if args.tool_manifest:
        if args.plan_only:
            parser.error("--plan-only cannot be used with --tool-manifest")
        if args.json:
            parser.error("--json cannot be used with --tool-manifest")
        if message:
            parser.error("message cannot be used with --tool-manifest")
        print(tool_manifest_json())
        return 0

    if args.explain_run:
        if args.plan_only:
            parser.error("--plan-only cannot be used with --explain-run")
        if args.json:
            parser.error("--json cannot be used with --explain-run")
        if message:
            parser.error("message cannot be used with --explain-run")
        print(explain_run(args.explain_run))
        return 0

    if args.repair_run:
        if message:
            parser.error("message cannot be used with --repair-run")
        repair = build_repair_plan(args.repair_run)
        if repair.status != "ready" or repair.plan is None:
            if args.json:
                print(
                    json.dumps(
                        {"type": "repair_unsupported", "run_dir": args.repair_run, "reason": repair.reason},
                        ensure_ascii=False,
                    )
                )
            else:
                print(f"repair unsupported: {repair.reason}")
            return 1
        if args.plan_only:
            print(plan_to_json(repair.plan))
            return 0
        return asyncio.run(
            run_plan(
                repair.plan,
                assume_yes=args.yes,
                output_json=args.json,
                save_run_log=args.save_run,
                runs_dir=args.runs_dir,
            )
        )

    if args.inspect_run:
        if args.plan_only:
            parser.error("--plan-only cannot be used with --inspect-run")
        if args.json:
            parser.error("--json cannot be used with --inspect-run")
        if message:
            parser.error("message cannot be used with --inspect-run")
        print(inspect_run(args.inspect_run))
        return 0

    if args.rerun:
        if args.plan_only:
            parser.error("--plan-only cannot be used with --rerun")
        if message:
            parser.error("message cannot be used with --rerun")
        plan = load_run_plan(args.rerun)
        return asyncio.run(
            run_plan(
                plan,
                assume_yes=args.yes,
                output_json=args.json,
                save_run_log=args.save_run,
                runs_dir=args.runs_dir,
            )
        )

    if args.plan_file:
        if args.plan_only:
            parser.error("--plan-only cannot be used with --plan-file")
        if message:
            parser.error("message cannot be used with --plan-file")
        plan = load_plan_file(args.plan_file)
        return asyncio.run(
            run_plan(
                plan,
                assume_yes=args.yes,
                output_json=args.json,
                save_run_log=args.save_run,
                runs_dir=args.runs_dir,
            )
        )

    if args.interactive or not message:
        return asyncio.run(
            run_repl(
                assume_yes=args.yes,
                output_json=args.json,
                planner_name=args.planner,
                llm_model=args.llm_model,
            )
        )

    return asyncio.run(
        run_task(
            message,
            assume_yes=args.yes,
            output_json=args.json,
            plan_only=args.plan_only,
            save_run_log=args.save_run,
            runs_dir=args.runs_dir,
            planner_name=args.planner,
            llm_model=args.llm_model,
        )
    )
