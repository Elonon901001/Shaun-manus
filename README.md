# Manus Clone

本地 Manus-like coding-agent runtime。当前主线是 CLI-first：自然语言或 plan file 会生成 `planner.v1` `AgentPlan`，再交给 Executor 执行。

## 安装依赖

```bash
npm install
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

## 启动

```bash
npm run dev
```

打开 http://localhost:3000，输入一句话后可以看到后端通过同一套 AgentPlan runtime 执行任务。

## 沙箱输入示例

```text
/run pwd
/run ls -la
帮我看看沙箱里有什么
检查运行环境
```

## CLI 示例

```powershell
.\.venv\Scripts\python.exe cli.py --plan-only "创建 hello.py 内容 print('hi') 然后运行"
.\.venv\Scripts\python.exe cli.py --yes "创建 hello.py 内容 print('hi') 然后运行"
.\.venv\Scripts\python.exe cli.py --plan-file examples\patch-file-demo.json --yes
.\.venv\Scripts\python.exe cli.py --tool-manifest
```

## Repair Run 示例

先保存一个失败 run：

```powershell
.\.venv\Scripts\python.exe cli.py --plan-file examples\repair-run-demo-broken.json --yes --save-run
```

然后对保存的 run 执行修复：

```powershell
.\.venv\Scripts\python.exe cli.py --repair-run runs\run_YYYYMMDD_HHMMSS --yes
```

`repair-run` 不直接改文件；它会生成新的修复 `AgentPlan`，再交给 Executor 执行。

## 当前结构

```text
api/
  main.py          FastAPI 应用和 SSE 接口
  schemas.py       AgentPlan / ExecutionResult 等核心结构
  executor.py      多步计划执行器
  tools.py         Tool Registry
  repair.py        explain-run / repair-run
web/
  src/
    App.tsx        聊天和 Workspace 页面
```


