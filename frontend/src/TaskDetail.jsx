import { useEffect, useState } from "react";
import PortadaPanel from "./PortadaPanel";
import ChatPanel from "./ChatPanel";
import TaskDrivePanel from "./TaskDrivePanel";

const API_URL = "http://127.0.0.1:8000";

const STATUS_LABELS = {
  "Estado de la entrega": "Entrega",
  "Estado de la calificación": "Calificación",
  "Tiempo restante": "Tiempo restante",
};

export default function TaskDetail({ task, onClose, onToggle }) {
  const [tab, setTab] = useState("detalle");
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [checklist, setChecklist] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setTab("detalle");
    setDetail(null);
    setChecklist(null);
    setError(null);
    setLoading(true);

    fetch(`${API_URL}/api/tasks/${encodeURIComponent(task.id)}/detail`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "No se pudo cargar el detalle");
        }
        return res.json();
      })
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [task.id]);

  function runAnalysis(force) {
    setAnalyzing(true);
    fetch(`${API_URL}/api/tasks/${encodeURIComponent(task.id)}/analyze${force ? "?force=true" : ""}`, {
      method: "POST",
    })
      .then((res) => res.json())
      .then((data) => setChecklist(data.checklist || []))
      .catch(() => setChecklist((prev) => prev || []))
      .finally(() => setAnalyzing(false));
  }

  useEffect(() => {
    if (!detail) return;
    if (detail.checklist !== null && detail.checklist !== undefined) {
      setChecklist(detail.checklist);
      return;
    }
    runAnalysis(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail]);

  async function toggleChecklistItem(item) {
    const next = !item.done;
    setChecklist((prev) => prev.map((i) => (i.id === item.id ? { ...i, done: next } : i)));
    try {
      const res = await fetch(
        `${API_URL}/api/tasks/${encodeURIComponent(task.id)}/checklist/toggle`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ item_id: item.id, done: next }),
        }
      );
      if (!res.ok) throw new Error();
    } catch {
      setChecklist((prev) => prev.map((i) => (i.id === item.id ? { ...i, done: !next } : i)));
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-course">{task.course}</span>
          <button className="modal-close" onClick={onClose} aria-label="Cerrar">
            ×
          </button>
        </div>

        <h2 className="modal-title">{task.summary || task.title}</h2>
        {task.summary && task.summary !== task.title && (
          <p className="modal-raw-title">Título original: {task.title}</p>
        )}

        <label className="modal-complete">
          <input type="checkbox" checked={task.completed} onChange={() => onToggle(task)} />
          Marcar como completada
        </label>

        <div className="modal-tabs">
          {[
            ["detalle", "Detalle"],
            ["portada", "Portada"],
            ["asistente", "Asistente IA"],
          ].map(([key, label]) => (
            <button
              key={key}
              className={`modal-tab ${tab === key ? "active" : ""}`}
              onClick={() => setTab(key)}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "portada" && <PortadaPanel taskId={task.id} />}
        {tab === "asistente" && <ChatPanel taskId={task.id} />}

        {tab === "detalle" && loading && <p className="modal-loading">Cargando detalle desde iVirtual…</p>}
        {tab === "detalle" && error && (
          <div className="modal-error">
            <p>{error}</p>
            <a href={task.url} target="_blank" rel="noreferrer">
              Abrir en iVirtual →
            </a>
          </div>
        )}

        {tab === "detalle" && detail && (
          <>
            {(analyzing || (checklist && checklist.length > 0)) && (
              <div className="checklist-section">
                <h3>Qué debes hacer</h3>
                {analyzing && (
                  <p className="modal-loading">Analizando materiales de la tarea con IA…</p>
                )}
                {!analyzing && checklist && checklist.length > 0 && (
                  <ul className="checklist">
                    {checklist.map((item) => (
                      <li key={item.id} className={item.done ? "done" : ""}>
                        <label>
                          <input
                            type="checkbox"
                            checked={item.done}
                            onChange={() => toggleChecklistItem(item)}
                          />
                          {item.text}
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {Object.keys(detail.status || {}).length > 0 && (
              <div className="status-grid">
                {Object.entries(detail.status).map(([key, val]) => (
                  <div className="status-item" key={key}>
                    <span className="status-key">{STATUS_LABELS[key] || key}</span>
                    <span className="status-val">{val}</span>
                  </div>
                ))}
              </div>
            )}

            {detail.description_html ? (
              <div
                className="modal-description"
                dangerouslySetInnerHTML={{ __html: detail.description_html }}
              />
            ) : (
              <p className="modal-empty">Esta actividad no tiene una descripción adicional.</p>
            )}

            {detail.attachments && detail.attachments.length > 0 && (
              <div className="attachments">
                <h3>Archivos adjuntos</h3>
                <ul>
                  {detail.attachments.map((a) => (
                    <li key={a.url}>
                      <a href={a.url} target="_blank" rel="noreferrer">
                        📎 {a.name}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!analyzing && (
              <button className="reanalyze-link" onClick={() => runAnalysis(true)}>
                Volver a analizar la tarea con IA
              </button>
            )}
          </>
        )}

        <a className="modal-fallback-link" href={task.url} target="_blank" rel="noreferrer">
          Ver en iVirtual →
        </a>
      </div>
    </div>
  );
}
