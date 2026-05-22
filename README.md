# Manus Clone

第一阶段目标：跑通 Next.js 前端到 FastAPI 后端的 SSE 流式输出。

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

打开 http://localhost:3000，输入一句话后可以看到后端逐字流式返回。

## 沙箱输入示例

```text
/run pwd
/run ls -la
帮我看看沙箱里有什么
检查运行环境
```

## 当前结构

```text
api/
  main.py          FastAPI 应用和 SSE 接口
  schemas.py       请求结构
web/
  app/
    page.tsx       聊天页面
    globals.css    页面样式
```



