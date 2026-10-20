import { useEffect, useRef, useState } from "react";
import { API_URL } from "./taskUtils";

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderMarkdownLite(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/^- (.+)$/gm, "• $1");
}

export default function ChatPanel({ taskId }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/tasks/${encodeURIComponent(taskId)}/chat`)
      .then((res) => res.json())
      .then(setMessages)
      .catch(() => setMessages([]))
      .finally(() => setLoading(false));
  }, [taskId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function send(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const res = await fetch(`${API_URL}/api/tasks/${encodeURIComponent(taskId)}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "No se pudo consultar al asistente");
      }
      const reply = await res.json();
      setMessages((prev) => [...prev, reply]);
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {loading && <p className="modal-loading">Cargando conversación…</p>}
        {!loading && messages.length === 0 && (
          <p className="modal-empty">
            Pregúntale al asistente sobre el tema de esta tarea — puede investigar en internet y
            resumirte lo importante.
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`chat-bubble ${m.role}`}
            dangerouslySetInnerHTML={{ __html: renderMarkdownLite(m.content) }}
          />
        ))}
        {sending && <div className="chat-bubble assistant pending">Investigando…</div>}
        <div ref={bottomRef} />
      </div>

      {error && <div className="modal-error">{error}</div>}

      <form className="chat-input-row" onSubmit={send}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pregunta algo sobre el tema de esta tarea…"
          disabled={sending}
        />
        <button type="submit" className="sync-btn" disabled={sending || !input.trim()}>
          Enviar
        </button>
      </form>
    </div>
  );
}
