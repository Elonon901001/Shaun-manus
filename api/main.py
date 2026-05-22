import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from api.sandbox import run_shell
from api.schemas import ChatRequest

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


def select_command(user_message: str) -> tuple[str, str]:
    text = user_message.strip()
    lower_text = text.lower()

    if lower_text.startswith("/run "):
        command = text[5:].strip()
        return "direct_command", command or "pwd"

    if any(keyword in lower_text for keyword in ["environment", "version", "runtime", "环境", "版本", "运行环境"]):
        return "natural_task", "pwd && python --version && node --version && npm --version"

    if any(keyword in lower_text for keyword in ["file", "directory", "list", "文件", "目录", "看看", "有什么"]):
        return "natural_task", "pwd && ls -la"

    return (
        "natural_task",
        'echo "I can run sandbox commands now. Try /run pwd or ask me to inspect the environment."',
    )


async def stream_reply(request: ChatRequest) -> AsyncIterator[bytes]:
    user_message = request.messages[-1].content if request.messages else ""
    mode, command = select_command(user_message)
    mode_message = "直接执行 /run 命令" if mode == "direct_command" else "根据自然语言选择沙箱命令"

    yield sse_event({"type": "task_status", "status": mode, "message": mode_message})
    await asyncio.sleep(0.2)

    intro = f"收到你的输入：{user_message}\n{mode_message}：{command}\n"
    for char in intro:
        yield sse_event({"type": "message_delta", "content": char})
        await asyncio.sleep(0.02)

    yield sse_event({"type": "tool_start", "tool": "run_shell", "input": {"mode": mode, "command": command}})
    result = await run_shell(command)
    yield sse_event({"type": "tool_end", "tool": "run_shell", "result": result})

    summary = "\n沙箱命令执行完成。所有命令都只在 Docker 容器 manus-sandbox 内运行。"
    for char in summary:
        yield sse_event({"type": "message_delta", "content": char})
        await asyncio.sleep(0.02)

    yield sse_event({"type": "message_done"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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
