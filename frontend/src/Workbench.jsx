import { useEffect, useMemo, useState } from "react";
import { API_URL, formatDue } from "./taskUtils";
import PortadaPanel from "./PortadaPanel";
import ChatPanel from "./ChatPanel";

function cleanMaterialText(text) {
  if (!text) return "";
  return text
    .replace(/\[Adjunto: [^\]]*\]/g, "")
    .replace(/\[Material enlazado\]/g, "")
    .replace(/﻿/g, "")
    .replace(/\r\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export default function Workbench({ tasks }) {
  const [taskId, setTaskId] = useState("");
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [checklist, setChecklist] = useState([]);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [review, setReview] = useState(null);
  const [reviewing, setReviewing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [driveResult, setDriveResult] = useState(null);
  const [error, setError] = useState(null);

  const pending = useMemo(
    () => tasks.filter((t) => !t.completed).sort((a, b) => (a.due || "9999").localeCompare(b.due || "9999")),
    [tasks]
  );
  const task = tasks.find((t) => t.id === taskId) || null;

  useEffect(() => {
    if (!taskId && pending.length > 0) setTaskId(pending[0].id);
  }, [pending, taskId]);

  useEffect(() => {
    if (!taskId) return;
    setReview(null);
    setDriveResult(null);
    setError(null);

    fetch(`${API_URL}/api/tasks/${encodeURIComponent(taskId)}/document`)
      .then((res) => res.json())
      .then((data) => {
        setContent(data.content || "");
        setSavedContent(data.content || "");
      })
      .catch(() => {});

    setDetailLoading(true);
    loadDetail(taskId).finally(() => setDetailLoading(false));
  }, [taskId]);

  function loadDetail(id) {
    return fetch(`${API_URL}/api/tasks/${encodeURIComponent(id)}/detail`)
      .then((res) => res.json())
      .then((data) => {
        setChecklist(data.checklist || []);
        setDetail(data);
        if (data.checklist === null || data.checklist === undefined) {
          runAnalysis(id);
        }
        return data;
      })
      .catch(() => {
        setChecklist([]);
        setDetail(null);
      });
  }

  function runAnalysis(id) {
    setAnalyzing(true);
    fetch(`${API_URL}/api/tasks/${encodeURIComponent(id)}/analyze`, { method: "POST" })
      .then(() => loadDetail(id))
      .catch(() => {})
      .finally(() => setAnalyzing(false));
  }

  async function toggleChecklistItem(item) {
    const next = !item.done;
    setChecklist((prev) => prev.map((i) => (i.id === item.id ? { ...i, done: next } : i)));
    try {
      const res = await fetch(
        `${API_URL}/api/tasks/${encodeURIComponent(taskId)}/checklist/toggle`,
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

  async function saveContent() {
    if (content === savedContent) return;
    setSaving(true);
    try {
      await fetch(`${API_URL}/api/tasks/${encodeURIComponent(taskId)}/document`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setSavedContent(content);
    } catch {
      setError("No se pudo guardar el documento");
    } finally {
      setSaving(false);
    }
  }

  function insertIntoDocument(text) {
    setContent((prev) => (prev.trim() ? `${prev}\n\n${text}` : text));
  }

  async function runReview() {
    setReviewing(true);
    setError(null);
    try {
      await saveContent();
      const res = await fetch(
        `${API_URL}/api/tasks/${encodeURIComponent(taskId)}/document/review`,
        { method: "POST" }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "No se pudo revisar el avance");
      }
      setReview(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setReviewing(false);
    }
  }

  async function uploadToDrive() {
    setUploading(true);
    setError(null);
    setDriveResult(null);
    try {
      await saveContent();
      const res = await fetch(
        `${API_URL}/api/tasks/${encodeURIComponent(taskId)}/document/upload-drive`,
        { method: "POST" }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "No se pudo subir a Drive");
      }
      setDriveResult(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  }

  const dirty = content !== savedContent;

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>Escritorio</h1>
          <p className="subtitle">
            Trabaja una tarea de principio a fin con el agente: portada, redacción asistida,
            revisión y PDF listo para subir
          </p>
        </div>
      </header>

      <div className="workbench-picker">
        <select className="filter-select" value={taskId} onChange={(e) => setTaskId(e.target.value)}>
          {pending.length === 0 && <option value="">No hay tareas pendientes</option>}
          {pending.map((t) => (
            <option key={t.id} value={t.id}>
              [{t.course}] {t.summary || t.title} · {formatDue(t.due)}
            </option>
          ))}
        </select>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {task && (
        <>
          <section className="workbench-summary">
            <h2 className="section-title">Resumen de la tarea</h2>
            <p className="workbench-summary-text">{task.summary || task.title}</p>

            {(detailLoading || analyzing) && (
              <p className="modal-loading">
                {analyzing ? "Leyendo el material de la tarea…" : "Cargando qué se pide…"}
              </p>
            )}

            {!detailLoading && !analyzing && (() => {
              const material = cleanMaterialText(detail?.material_text);
              if (material) {
                return <p className="workbench-material-text">{material}</p>;
              }
              if (detail?.description_html) {
                return (
                  <div
                    className="modal-description"
                    dangerouslySetInnerHTML={{ __html: detail.description_html }}
                  />
                );
              }
              return <p className="modal-empty">Esta tarea no tiene una descripción adicional.</p>;
            })()}

            {checklist.length > 0 && (
              <>
                <div className="workbench-points-header">
                  <h3 className="workbench-points-title">
                    Puntos a cubrir — {checklist.filter((i) => i.done).length} de {checklist.length}
                  </h3>
                  <button className="reanalyze-link" onClick={runReview} disabled={reviewing}>
                    {reviewing ? "Revisando…" : "Revisar mi avance"}
                  </button>
                </div>
                <ul className="checklist">
                  {checklist.map((item) => {
                    const suggestion = review?.items?.find((r) => r.id === item.id);
                    return (
                      <li key={item.id} className={item.done ? "done" : ""}>
                        <label>
                          <input
                            type="checkbox"
                            checked={item.done}
                            onChange={() => toggleChecklistItem(item)}
                          />
                          {item.text}
                        </label>
                        {suggestion && !item.done && (
                          <span className={`review-badge ${suggestion.covered ? "covered" : "missing"}`}>
                            {suggestion.covered ? "💡 parece cubierto" : `⚠️ ${suggestion.note || "falta"}`}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
                {review?.summary && <p className="review-summary">{review.summary}</p>}
              </>
            )}
          </section>

          <div className="workbench-grid">
          <div className="workbench-col">
            <h2 className="section-title">Portada</h2>
            <PortadaPanel taskId={task.id} />
          </div>

          <div className="workbench-col">
            <h2 className="section-title">Contenido</h2>
            <textarea
              className="workbench-editor"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onBlur={saveContent}
              placeholder="Escribe aquí el desarrollo de tu tarea, o pídele ayuda a la IA abajo…"
            />
            <div className="workbench-save-row">
              <button className="sync-btn" onClick={saveContent} disabled={saving || !dirty}>
                {saving ? "Guardando…" : dirty ? "Guardar" : "Guardado"}
              </button>
            </div>

            <h2 className="section-title" style={{ marginTop: 24 }}>
              Asistente
            </h2>
            <ChatPanel
              taskId={task.id}
              onInsert={insertIntoDocument}
              quickActions={[
                {
                  label: "Redactar lo que falta",
                  message:
                    "Redacta un primer borrador que cubra los puntos del checklist que el " +
                    "contenido actual todavía no cubre, en orden lógico.",
                },
              ]}
            />

            <h2 className="section-title" style={{ marginTop: 24 }}>
              Dejar listo para subir
            </h2>
            {review?.summary && <p className="review-summary">{review.summary}</p>}
            <div className="workbench-actions">
              <a
                className="reanalyze-link"
                href={`${API_URL}/api/tasks/${encodeURIComponent(task.id)}/document/pdf`}
                target="_blank"
                rel="noreferrer"
              >
                Ver / descargar PDF →
              </a>
              <button className="sync-btn" onClick={uploadToDrive} disabled={uploading}>
                {uploading ? "Subiendo…" : "Generar PDF y subir a Drive"}
              </button>
            </div>

            {driveResult && (
              <div className="notice-banner" style={{ marginTop: 12 }}>
                Subido a Drive:{" "}
                <a href={driveResult.url} target="_blank" rel="noreferrer">
                  {driveResult.name}
                </a>
              </div>
            )}
          </div>
          </div>
        </>
      )}
    </div>
  );
}
