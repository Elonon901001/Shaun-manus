import { FormEvent, useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";

const API_BASE_URL = "http://localhost:8001";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type ToolEvent = {
  type: "status" | "tool";
  title: string;
  content: string;
};

type FileEntry = {
  name: string;
  type: "directory" | "file" | "symlink" | "other";
};

type FileListResult = {
  path: string;
  entries?: FileEntry[];
  error?: string;
};

type FileReadResult = {
  path: string;
  content: string;
  truncated: boolean;
  line_count?: number;
  error?: string;
};

function joinPath(basePath: string, name: string) {
  if (!basePath || basePath === ".") return name;
  return `${basePath.replace(/\/$/, "")}/${name}`;
}

function parentPath(path: string) {
  if (!path || path === ".") return ".";
  const normalized = path.replace(/\/$/, "");
  const separatorIndex = normalized.lastIndexOf("/");
  return separatorIndex === -1 ? "." : normalized.slice(0, separatorIndex) || ".";
}

function ChatWorkspace() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<ToolEvent[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [workspacePath, setWorkspacePath] = useState(".");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileReadResult | null>(null);
  const [workspaceError, setWorkspaceError] = useState("");
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [isLoadingFile, setIsLoadingFile] = useState(false);

  async function refreshFiles(path = workspacePath) {
    setIsLoadingFiles(true);
    setWorkspaceError("");

    try {
      const response = await fetch(`${API_BASE_URL}/workspace/list?path=${encodeURIComponent(path)}`);
      const result = (await response.json()) as FileListResult;

      if (result.error) {
        setEntries([]);
        setWorkspaceError(result.error);
        return;
      }

      setWorkspacePath(result.path);
      setEntries(result.entries ?? []);
    } catch (error) {
      setEntries([]);
      setWorkspaceError(error instanceof Error ? error.message : "Unable to load workspace");
    } finally {
      setIsLoadingFiles(false);
    }
  }

  async function openEntry(entry: FileEntry) {
    const nextPath = joinPath(workspacePath, entry.name);

    if (entry.type === "directory") {
      setSelectedFile(null);
      await refreshFiles(nextPath);
      return;
    }

    setIsLoadingFile(true);
    setWorkspaceError("");

    try {
      const response = await fetch(`${API_BASE_URL}/workspace/read?path=${encodeURIComponent(nextPath)}`);
      const result = (await response.json()) as FileReadResult;
      setSelectedFile(result);
      if (result.error) setWorkspaceError(result.error);
    } catch (error) {
      setSelectedFile(null);
      setWorkspaceError(error instanceof Error ? error.message : "Unable to read file");
    } finally {
      setIsLoadingFile(false);
    }
  }

  useEffect(() => {
    void refreshFiles(".");
  }, []);

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const content = input.trim();
    if (!content || isStreaming) return;

    const nextMessages: Message[] = [...messages, { role: "user", content }];
    setMessages([...nextMessages, { role: "assistant", content: "" }]);
    setEvents([]);
    setInput("");
    setIsStreaming(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: nextMessages }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const eventText of events) {
          const dataLine = eventText.split("\n").find((line) => line.startsWith("data: "));
          if (!dataLine) continue;

          const eventData = JSON.parse(dataLine.slice(6));

          if (eventData.type === "message_delta") {
            setMessages((current) => {
              const updated = [...current];
              const last = updated[updated.length - 1];
              updated[updated.length - 1] = { ...last, content: last.content + eventData.content };
              return updated;
            });
          }

          if (eventData.type === "task_status") {
            setEvents((current) => [
              ...current,
              { type: "status", title: eventData.status, content: eventData.message },
            ]);
          }

          if (eventData.type === "tool_start") {
            setEvents((current) => [
              ...current,
              {
                type: "tool",
                title: `开始执行 ${eventData.tool}`,
                content: JSON.stringify(eventData.input, null, 2),
              },
            ]);
          }

          if (eventData.type === "tool_end") {
            setEvents((current) => [
              ...current,
              {
                type: "tool",
                title: `${eventData.tool} 执行完成`,
                content: JSON.stringify(eventData.result, null, 2),
              },
            ]);
            void refreshFiles();
          }
        }
      }
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <main className="shell">
      <section className="panel">
        <header>
          <p className="eyebrow">Manus Clone</p>
          <h1>React + Docker 沙箱工具调用</h1>
          <p className="subtitle">自然语言会映射为沙箱任务；/run 开头会直接在 Docker 容器里执行命令。</p>
        </header>

        <div className="workspace-grid">
          <section className="chat-panel" aria-label="Chat">
            <div className="messages">
              {messages.length === 0 ? (
                <div className="empty">描述一个任务，或输入 /run pwd 直接执行沙箱命令。</div>
              ) : (
                messages.map((message, index) => (
                  <div className={`message ${message.role}`} key={index}>
                    <span>{message.role === "user" ? "你" : "Agent"}</span>
                    <p>{message.content}</p>
                  </div>
                ))
              )}
            </div>

            {events.length > 0 && (
              <aside className="timeline">
                {events.map((event, index) => (
                  <div className={`event ${event.type}`} key={index}>
                    <strong>{event.title}</strong>
                    <pre>{event.content}</pre>
                  </div>
                ))}
              </aside>
            )}

            <form onSubmit={sendMessage}>
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="描述一个任务，或输入 /run pwd 直接执行沙箱命令..."
                rows={3}
              />
              <button disabled={isStreaming}>{isStreaming ? "输出中" : "发送"}</button>
            </form>
          </section>

          <aside className="files-panel" aria-label="Workspace files">
            <div className="files-header">
              <div>
                <p className="eyebrow">Workspace</p>
                <h2>/workspace</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => void refreshFiles()} disabled={isLoadingFiles}>
                ↻
              </button>
            </div>

            <div className="pathbar">
              <button type="button" onClick={() => void refreshFiles(parentPath(workspacePath))} disabled={workspacePath === "."}>
                上级
              </button>
              <code>{workspacePath}</code>
            </div>

            {workspaceError && <div className="workspace-error">{workspaceError}</div>}

            <div className="file-list">
              {isLoadingFiles ? (
                <div className="file-placeholder">加载中...</div>
              ) : entries.length === 0 ? (
                <div className="file-placeholder">当前目录为空</div>
              ) : (
                entries.map((entry) => (
                  <button
                    className={`file-row ${entry.type}`}
                    type="button"
                    key={`${entry.type}-${entry.name}`}
                    onClick={() => void openEntry(entry)}
                  >
                    <span>{entry.type === "directory" ? "▸" : "•"}</span>
                    <strong>{entry.name}</strong>
                    <em>{entry.type}</em>
                  </button>
                ))
              )}
            </div>

            <div className="file-preview">
              <div className="preview-header">
                <strong>{selectedFile?.path ?? "未选择文件"}</strong>
                {isLoadingFile && <span>读取中...</span>}
                {selectedFile?.truncated && <span>前 200 行</span>}
              </div>
              <pre>{selectedFile?.content || "点击文件查看内容。"}</pre>
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ChatWorkspace />} />
    </Routes>
  );
}
