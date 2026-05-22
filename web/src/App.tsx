import { FormEvent, useState } from "react";
import { Route, Routes } from "react-router-dom";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type ToolEvent = {
  type: "status" | "tool";
  title: string;
  content: string;
};

function ChatWorkspace() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<ToolEvent[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

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
      const response = await fetch("http://localhost:8001/chat/stream", {
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
