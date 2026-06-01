# Manus Clone Handoff

## 当前定位

这个项目是在本地复现一个 Manus-like / coding-agent runtime。

当前重点已经从前端 GUI 转到 **CLI-first 的 Agent Runtime 骨架**。前端仍然保留，但现在不是主要开发方向。

当前还没有接入 LLM。现在做的是：在不接 LLM 的情况下，用规则版 Planner 跑通完整链路，验证 Agent runtime 的核心结构是否稳定。

当前核心链路：

```text
自然语言 / plan.json / saved run
  -> planner.v1 AgentPlan
  -> Executor
  -> input validation
  -> shell safety guard
  -> human confirmation
  -> Tool Registry
  -> Docker sandbox
  -> run logs
```

未来接 LLM 时，目标是只替换 Planner：

```text
Rule Planner -> LLM Planner
```

下面这条链路尽量不变：

```text
planner.v1 -> validation -> safety -> confirmation -> executor -> tools -> Docker -> run logs
```

## 当前技术栈

### CLI / Agent Runtime

- Python 3.12
- Pydantic
- Docker Desktop / Docker Compose
- unittest

入口：

```text
cli.py
api/cli.py
```

### 后端 API

- FastAPI
- SSE streaming
- CORS

入口：

```text
api/main.py
```

### 前端

- React
- React Router
- Vite
- TypeScript

入口：

```text
web/index.html
web/src/main.tsx
web/src/App.tsx
web/src/styles.css
```

### 沙箱

- Docker Desktop
- Docker Compose
- 容器名：`manus-sandbox`
- 沙箱工作目录：`/workspace`

配置：

```text
docker-compose.yml
sandbox/Dockerfile
```

容器包含：

```text
Python 3.12
Node.js
npm
bash
curl
git
```

## 如何启动和验证

确保 Docker Desktop 已启动。

启动沙箱：

```powershell
docker compose up -d --build
docker compose ps
```

运行 CLI：

```powershell
.\.venv\Scripts\python.exe cli.py "看看文件"
```

运行完整测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m py_compile cli.py api/main.py api/agent.py api/tools.py api/sandbox.py api/schemas.py api/policy.py api/cli.py api/planner.py api/executor.py api/validation.py api/safety.py api/runlog.py
npm.cmd run typecheck
```

注意：在 Windows PowerShell 里直接运行 `npm run typecheck` 可能被执行策略拦截，使用：

```powershell
npm.cmd run typecheck
```

前后端开发服务仍可启动：

```powershell
npm run dev
```

地址：

```text
前端：http://localhost:3000
后端：http://localhost:8001
```

## 当前架构图

```text
User / CLI
  |
  |-- 自然语言 ---------------------> Rule Planner
  |                                   api/planner.py
  |
  |-- --plan-file plan.json --------> Plan File Loader
  |
  |-- --rerun runs/run_xxx ---------> runs/run_xxx/plan.json
                                      |
                                      v
                             planner.v1 AgentPlan
                                      |
                                      v
                                  Executor
                              api/executor.py
                                      |
             ------------------------------------------------
             |                      |                       |
             v                      v                       v
      Input Validation        Shell Safety Guard       Human Confirmation
      api/validation.py       api/safety.py            api/policy.py
             |                      |                       |
             -----------------------|-----------------------
                                    v
                              Tool Registry
                              api/tools.py
                                    |
                                    v
                              Docker Sandbox
                              api/sandbox.py
                              manus-sandbox:/workspace
                                    |
                                    v
                              ExecutionResult
                                    |
                                    v
                              Run Logs
                              api/runlog.py
                              plan.json/events.jsonl/result.json
```

## 核心数据结构

文件：

```text
api/schemas.py
```

核心模型：

```python
class AgentStep(BaseModel):
    id: str
    thought: str
    tool: str
    input: dict[str, Any]


class AgentPlan(BaseModel):
    version: str = "planner.v1"
    source: str = "rule"
    goal: str
    max_steps: int = 8
    context: dict[str, Any] = {}
    steps: list[AgentStep]


class StepResult(BaseModel):
    step: AgentStep
    status: str
    result: dict[str, Any]


class ExecutionResult(BaseModel):
    plan: AgentPlan
    step_results: list[StepResult]
    events: list[dict[str, Any]] = []
    status: str
```

`planner.v1` 是未来 LLM 需要输出的计划格式。

## 已实现能力

### 1. CLI-first Agent Runtime

入口：

```text
cli.py
api/cli.py
```

常用命令：

```powershell
.\.venv\Scripts\python.exe cli.py "看看文件"
.\.venv\Scripts\python.exe cli.py --yes "创建 hello.py 内容 print('hi') 然后运行"
.\.venv\Scripts\python.exe cli.py --interactive
```

CLI 现在支持：

```text
--yes           自动确认 write/run_shell 风险工具
--json          输出 JSONL 事件
--plan-only     只生成 planner.v1 JSON，不执行
--plan-file     从 JSON plan 执行
--rerun         从 runs/run_xxx/plan.json 重放
--inspect-run   查看历史 run 摘要
--save-run      保存 plan/events/result
--runs-dir      指定 run log 目录
```

### 2. 规则版 Planner

文件：

```text
api/planner.py
api/agent.py
```

当前还没有 LLM。规则版支持：

```text
/run <command>                       -> run_shell
/write <path> <content>              -> write_file
创建/写入/保存 <path> 内容 <content>   -> write_file
创建 <file.py> 内容 ... 然后运行       -> write_file -> run_shell
/run <command> 然后读取 <path>        -> run_shell -> read_file
看看文件 然后读取 <path>              -> list_files -> read_file
读取/打开/read <path>                 -> read_file
文件/目录/list/看看/有什么            -> list_files
环境/版本/runtime                     -> run_shell
```

核心函数：

```python
build_plan(message: str) -> AgentPlan
plan_to_json(plan: AgentPlan) -> str
plan_from_json(plan_json: str) -> AgentPlan
normalize_plan(data: dict[str, Any]) -> AgentPlan
```

### 3. 多步 Executor

文件：

```text
api/executor.py
```

职责：

- 执行 `AgentPlan.steps`
- 支持 `max_steps`
- 支持 `${step_1.result.path}` 这种上一步结果引用
- 每步执行前做 validation / safety / confirmation
- 收集 `StepResult`
- 失败即停止
- 记录执行事件

执行顺序：

```text
resolve references
  -> validate_step
  -> check_step_safety
  -> requires_confirmation
  -> execute_tool
  -> collect result
```

这是整个 runtime 的核心。

### 4. Tool Input Validation

文件：

```text
api/validation.py
```

作用：检查工具输入结构是否正确，防止错误 plan 直接进入工具层。

当前规则：

```python
TOOL_INPUT_RULES = {
    "run_shell": ToolInputRule(required={"command": str}),
    "list_files": ToolInputRule(required={}, optional={"path": str}),
    "read_file": ToolInputRule(required={"path": str}),
    "write_file": ToolInputRule(required={"path": str, "content": str}),
}
```

示例失败：

```json
{
  "tool": "write_file",
  "input": {
    "content": "hello"
  }
}
```

会在 Executor 前失败：

```text
Tool input validation failed: write_file requires input.path
```

### 5. Shell Safety Guard

文件：

```text
api/safety.py
```

作用：对 `run_shell` 做危险命令硬拦截。它位于 validation 之后、confirmation 之前。

当前拦截：

```text
rm -rf /
mkfs
shutdown/reboot/poweroff/halt
fork bomb
dd if=
docker.sock / /var/run/docker.sock
chmod -R 777 /
chown -R
```

示例：

```powershell
.\.venv\Scripts\python.exe cli.py --plan-file examples\unsafe-shell-plan.json --yes
```

会输出：

```text
Tool safety check failed
rule: remove_root
```

### 6. Human Confirmation / Risk Policy

文件：

```text
api/policy.py
```

当前风险：

```text
list_files  safe
read_file   safe
write_file  write
run_shell   command
```

`write_file` 和 `run_shell` 默认需要确认；CLI 可用 `--yes` 自动确认。

### 7. Tool Registry

文件：

```text
api/tools.py
```

当前工具：

```text
run_shell
list_files
read_file
write_file
```

工具统一入口：

```python
execute_tool(name: str, tool_input: dict) -> dict
```

`list_files` 返回结构化结果：

```json
{
  "path": ".",
  "entries": [
    {"name": "README.md", "type": "file"},
    {"name": "src", "type": "directory"}
  ]
}
```

`read_file` 返回：

```json
{
  "path": "README.md",
  "content": "...",
  "truncated": false,
  "line_count": 1
}
```

`write_file` 返回：

```json
{
  "path": "hello.py",
  "bytes_written": 11,
  "created": true
}
```

### 8. Docker Sandbox

文件：

```text
api/sandbox.py
```

核心函数：

```python
run_shell(command: str, timeout: float = 20)
```

底层执行：

```bash
docker exec manus-sandbox sh -lc <command>
```

返回：

```json
{
  "exit_code": 0,
  "stdout": "...",
  "stderr": "..."
}
```

### 9. Run Logs / Rerun / Inspect

文件：

```text
api/runlog.py
api/cli.py
```

保存命令：

```powershell
.\.venv\Scripts\python.exe cli.py --yes --save-run "创建 log_demo.py 内容 print('logged') 然后运行"
```

生成：

```text
runs/run_YYYYMMDD_HHMMSS/
  plan.json
  events.jsonl
  result.json
```

重放：

```powershell
.\.venv\Scripts\python.exe cli.py --rerun runs\run_20260527_104943 --yes
```

查看摘要：

```powershell
.\.venv\Scripts\python.exe cli.py --inspect-run runs\run_20260527_104943
```

示例输出：

```text
run: runs\run_20260527_104943
goal: 创建 log_demo.py 内容 print('logged') 然后运行
status: completed
steps: 2/2
events: 6

step results:
  step_1 write_file completed
    path=log_demo.py, bytes=15
  step_2 run_shell completed
    stdout=logged
```

### 10. Plan File

示例：

```text
examples/plan-file-demo.json
examples/invalid-write-plan.json
examples/unsafe-shell-plan.json
```

执行：

```powershell
.\.venv\Scripts\python.exe cli.py --plan-file examples\plan-file-demo.json --yes
```

`--plan-file` 跳过自然语言 Planner，直接执行 JSON plan。

### 11. FastAPI + 前端

前端/后端仍保留。

后端接口：

```text
GET  /health
POST /chat/stream
GET  /workspace/list?path=.
GET  /workspace/read?path=README.md
```

前端已有右侧 Workspace 面板：

- 自动加载 `/workspace`
- 点击目录进入
- 点击文件预览
- 工具执行后刷新文件列表

但当前项目方向已经转为 CLI-first，前端不是主要路线。

## 示例命令

生成 plan 但不执行：

```powershell
.\.venv\Scripts\python.exe cli.py --plan-only "创建 stable.py 内容 print('stable') 然后运行"
```

执行多步任务：

```powershell
.\.venv\Scripts\python.exe cli.py --yes "创建 stable.py 内容 print('stable') 然后运行"
```

JSON 事件输出：

```powershell
.\.venv\Scripts\python.exe cli.py --json --yes "创建 stable.py 内容 print('stable') 然后运行"
```

从 plan 文件执行：

```powershell
.\.venv\Scripts\python.exe cli.py --plan-file examples\plan-file-demo.json --yes
```

保存 run：

```powershell
.\.venv\Scripts\python.exe cli.py --yes --save-run "创建 log_demo.py 内容 print('logged') 然后运行"
```

重放 run：

```powershell
.\.venv\Scripts\python.exe cli.py --rerun runs\run_20260527_104943 --yes
```

查看 run：

```powershell
.\.venv\Scripts\python.exe cli.py --inspect-run runs\run_20260527_104943
```

验证 validation：

```powershell
.\.venv\Scripts\python.exe cli.py --plan-file examples\invalid-write-plan.json --yes
```

验证 safety：

```powershell
.\.venv\Scripts\python.exe cli.py --plan-file examples\unsafe-shell-plan.json --yes
```

## 测试

测试目录：

```text
tests/
```

当前覆盖：

```text
test_agent.py
test_cli.py
test_executor.py
test_plan_json.py
test_planner.py
test_policy.py
test_safety.py
test_tools.py
test_validation.py
test_workspace_api.py
```

最近验证结果：

```text
python -m unittest discover -s tests -v
43 tests OK
```

同时通过：

```text
python -m py_compile ...
npm.cmd run typecheck
```

## 当前项目状态

可以认为：

```text
Agent Runtime v0：基本完成
LLM Planner：尚未接入
编程工具能力：基础工具完成，还缺 patch/edit 能力
Repair Loop：尚未实现，但 run logs / inspect / rerun 已准备好
前端：可用但不是当前重点
```

已完成的 runtime 能力：

```text
planner.v1
multi-step executor
tool registry
Docker sandbox
structured file tools
write_file
validation
safety
confirmation
plan-file
plan-only
run logs
rerun
inspect-run
CLI JSON events
```

## 目前限制

### 1. 还没有 LLM Planner

现在是规则版 Planner。复杂任务无法真正智能规划。

未来应新增：

```text
Planner Interface
RulePlanner
LLMPlannerStub
LLMPlanner
```

### 2. 工具还少

当前只有：

```text
run_shell
list_files
read_file
write_file
```

真实 coding agent 还需要：

```text
search_files
replace_text
patch_file
run_tests
maybe install_package
```

### 3. `write_file` 是整文件写入

还没有安全的增量编辑工具。下一阶段很可能需要：

```text
replace_text
patch_file
```

### 4. 还没有 Repair Loop

目前支持：

```text
inspect-run
rerun
```

但还不支持：

```text
failed run -> explain context -> LLM repair plan -> execute repaired plan
```

### 5. Safety Guard 还是启发式

`api/safety.py` 不是完整 shell parser，只是第一版危险模式拦截。

## 推荐下一步

当前最推荐的下一步是：

```text
Repair Context Builder
```

也就是新增：

```powershell
.\.venv\Scripts\python.exe cli.py --explain-run runs\failed_run
```

它不调用 LLM，只把失败 run 整理成未来 LLM 可读上下文：

```text
Goal
Plan
Completed Steps
Failed Step
Failure Message
stdout/stderr
Repair Hint
```

为什么推荐：

1. 已经有 `plan.json/events.jsonl/result.json`。
2. 已经有 `inspect-run`。
3. 下一步做 `explain-run` 可以为未来 `repair-run` 打基础。
4. 这比马上接 LLM 更稳。

之后建议顺序：

```text
Repair Context Builder
-> Tool Manifest
-> Planner Interface
-> LLMPlannerStub
-> Real LLM Planner
-> patch_file / replace_text
-> Repair Loop
```

如果用户更想先理解抽象，也可以优先做：

```text
Planner Interface
```

## 重要文件地图

```text
cli.py                         CLI 入口
api/cli.py                     CLI 编排、参数、plan-file/rerun/inspect

api/schemas.py                 AgentPlan/AgentStep/ExecutionResult 核心模型
api/planner.py                 规则版多步 Planner + plan JSON normalize
api/agent.py                   老的单步规则 Planner fallback
api/executor.py                多步执行器，runtime 核心

api/validation.py              工具输入结构校验
api/safety.py                  shell 危险命令硬拦截
api/policy.py                  工具风险分级和确认策略

api/tools.py                   Tool Registry，run/list/read/write
api/sandbox.py                 Docker exec 执行层
api/runlog.py                  run log 保存/读取

api/main.py                    FastAPI + SSE + workspace API

examples/plan-file-demo.json   正常 plan-file 示例
examples/invalid-write-plan.json validation 失败示例
examples/unsafe-shell-plan.json  safety 失败示例

runs/                          保存的历史 run

tests/                         unittest 测试

web/src/App.tsx                前端聊天 + Workspace 面板
web/src/styles.css             前端样式
```

## 协作偏好

用户偏好不是完全由 Agent 直接代改所有代码。

当前协作模式建议：

1. 对架构核心部分，先解释设计意义，再给代码。
2. 用户希望理解关键抽象，而不是只复制粘贴。
3. 胶水代码、测试、验证可以由 Agent 直接实现。
4. 每次提出下一步选择时，文末必须提醒：

```text
你需要重点理解的核心部分
```

提醒内容包括：

- 哪些模块是架构核心
- 哪些代码建议用户亲自读或手写一小段
- 哪些只是胶水，Agent 可以直接做
- 为什么这部分对后续 LLM / Agent runtime 重要

最近明确过的核心理解点：

```text
validation 管结构
safety 管风险
confirmation 管授权
Planner 负责生成计划
Executor 负责执行计划
Tools 负责具体动作
LLM 未来只输出 planner.v1，不直接执行工具
```

