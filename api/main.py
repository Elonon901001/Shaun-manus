import asyncio
import json
from collections.abc import AsyncIterator

from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.executor import execute_plan
from api.planner import build_plan
from api.schemas import ChatRequest
from api.tools import execute_tool

app = FastAPI(title="Manus Clone API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse_event(payload: dict) -> bytes:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


async def stream_reply(request: ChatRequest) -> AsyncIterator[bytes]:
    user_message = request.messages[-1].content if request.messages else ""
    plan = build_plan(user_message)

    yield sse_event({"type": "plan", "plan": plan.model_dump()})
    yield sse_event(
        {
            "type": "task_status",
            "status": "planned",
            "message": f"生成 planner.v1 计划，共 {len(plan.steps)} 步。",
        }
    )
    await asyncio.sleep(0.2)

    intro = f"收到你的输入：{user_message}\n已生成 planner.v1 计划，准备交给 Executor 执行。\n"
    for char in intro:
        yield sse_event({"type": "message_delta", "content": char})
        await asyncio.sleep(0.02)

    execution = await execute_plan(plan, assume_yes=True)
    for step_result in execution.step_results:
        yield sse_event({"type": "tool_start", "tool": step_result.step.tool, "input": step_result.step.input})
        yield sse_event(
            {
                "type": "tool_end",
                "tool": step_result.step.tool,
                "status": step_result.status,
                "result": step_result.result,
            }
        )

    summary = f"\nExecutor 执行完成，状态：{execution.status}。所有命令都只在 Docker 容器 manus-sandbox 内运行。"
    for char in summary:
        yield sse_event({"type": "message_delta", "content": char})
        await asyncio.sleep(0.02)

    yield sse_event({"type": "done", "status": execution.status, "events": execution.events})
    yield sse_event({"type": "message_done"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/workspace/list")
async def workspace_list(path: str = ".") -> dict[str, Any]:
    return await execute_tool("list_files", {"path": path})


@app.get("/workspace/read")
async def workspace_read(path: str = Query(..., min_length=1)) -> dict[str, Any]:
    return await execute_tool("read_file", {"path": path})


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_reply(request),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Content-Type-Options": "nosniff",
        },
    )
