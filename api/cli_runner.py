import json
from collections.abc import Callable

from api.cli_format import format_result, print_plan
from api.executor import execute_plan
from api.planner import build_plan, plan_to_json
from api.policy import get_risk_message
from api.runlog import save_run
from api.schemas import AgentPlan, AgentStep
from api.llm_planner import build_llm_plan

ConfirmCallback = Callable[[AgentStep], bool]


def prompt_confirmation(step: AgentStep) -> bool:
    print(f"risk: {get_risk_message(step.tool)}")
    answer = input("Execute this tool? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


async def run_task(
    message: str,
    *,
    assume_yes: bool = False,
    output_json: bool = False,
    plan_only: bool = False,
    save_run_log: bool = False,
    runs_dir: str = "runs",
    confirm: ConfirmCallback | None = None,
    planner_name: str = "rule",
    llm_model: str | None = None,
) -> int:
    if planner_name == "rule":
        plan = build_plan(message)
    elif planner_name == "llm":
        plan = build_llm_plan(message, model=llm_model)
    else:
        raise ValueError(f"unknown planner: {planner_name}")

    if plan_only:
        print(plan_to_json(plan))
        return 0

    return await run_plan(
        plan,
        assume_yes=assume_yes,
        output_json=output_json,
        save_run_log=save_run_log,
        runs_dir=runs_dir,
        confirm=confirm,
    )


async def run_plan(
    plan: AgentPlan,
    *,
    assume_yes: bool = False,
    output_json: bool = False,
    save_run_log: bool = False,
    runs_dir: str = "runs",
    confirm: ConfirmCallback | None = None,
) -> int:
    if output_json:
        print(json.dumps({"type": "plan", "plan": plan.model_dump()}, ensure_ascii=False))
    else:
        print_plan(plan)

    execution = await execute_plan(plan, assume_yes=assume_yes, confirm=confirm or prompt_confirmation)

    run_dir = save_run(plan, execution, runs_dir) if save_run_log else None

    for step_result in execution.step_results:
        if output_json:
            print(json.dumps({"type": "step_result", **step_result.model_dump()}, ensure_ascii=False))
            continue

        print(f"\n[{step_result.status}] {step_result.step.id}: {step_result.step.tool}")
        if step_result.status == "cancelled":
            print("cancelled")
        else:
            print(format_result(step_result.result))

    if output_json:
        print(
            json.dumps(
                {
                    "type": "done",
                    "status": execution.status,
                    "events": execution.events,
                    "run_dir": str(run_dir) if run_dir is not None else None,
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"\nstatus: {execution.status}")
        if run_dir is not None:
            print(f"saved: {run_dir}")

    if execution.status == "completed":
        return 0
    if execution.status == "cancelled":
        return 130
    return 1


async def run_repl(
    *,
    assume_yes: bool = False,
    output_json: bool = False,
    planner_name: str = "rule",
    llm_model: str | None = None,
) -> int:
    print("Manus CLI. Type a task, /run <command>, /write <path> <content>, or exit.")
    while True:
        try:
            message = input("manus> ").strip()
        except EOFError:
            print()
            return 0

        if not message:
            continue
        if message.lower() in {"exit", "quit"}:
            return 0

        await run_task(
            message,
            assume_yes=assume_yes,
            output_json=output_json,
            planner_name=planner_name,
            llm_model=llm_model,
        )