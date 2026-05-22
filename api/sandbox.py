import asyncio


async def run_shell(command: str, timeout: float = 20) -> dict[str, int | str]:
    process = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        "manus-sandbox",
        "sh",
        "-lc",
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        return {"exit_code": 124, "stdout": "", "stderr": "Command timed out"}

    return {
        "exit_code": process.returncode or 0,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
    }
