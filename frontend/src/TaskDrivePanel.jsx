import { useEffect, useState } from "react";
import { API_URL } from "./taskUtils";

export default function TaskDrivePanel({ taskId }) {
  const [status, setStatus] = useState(null);
  const [links, setLinks] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [copiedUrl, setCopiedUrl] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/api/drive/status`)
      .then((res) => res.json())
      .then(setStatus)
      .catch(() => {});

    fetch(`${API_URL}/api/tasks/${encodeURIComponent(taskId)}/drive`)
      .then((res) => res.json())
      .then(setLinks)
      .catch(() => {});
  }, [taskId]);

  async function upload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(`${API_URL}/api/tasks/${encodeURIComponent(taskId)}/drive`, {
        method: "POST",
        body,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "No se pudo subir el archivo");
      }
      const link = await res.json();
      setLinks((prev) => [link, ...prev]);
    } catch (e) {
      setError(e.message);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function copyLink(url) {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedUrl(url);
      setTimeout(() => setCopiedUrl(null), 2000);
    } catch {
      setError("No se pudo copiar el enlace");
    }
  }

  if (!status) return <p className="modal-loading">Cargando…</p>;

  if (!status.connected) {
    return (
      <div className="modal-empty">
        Google Drive no está conectado todavía. Ve al menú <strong>Drive</strong> para conectarlo
        {status.allowed_domain ? ` con tu correo institucional (${status.allowed_domain})` : ""}.
      </div>
    );
  }

  return (
    <div className="drive-panel">
      <label className="sync-btn" style={{ display: "inline-block", cursor: "pointer" }}>
        {uploading ? "Subiendo…" : "Subir archivo a Drive"}
        <input type="file" onChange={upload} disabled={uploading} style={{ display: "none" }} />
      </label>

      {error && <div className="modal-error">{error}</div>}

      {links.length > 0 ? (
        <ul className="drive-links">
          {links.map((l) => (
            <li key={l.url}>
              <a href={l.url} target="_blank" rel="noreferrer">
                📄 {l.name}
              </a>
              <button className="reanalyze-link" onClick={() => copyLink(l.url)}>
                {copiedUrl === l.url ? "Copiado ✓" : "Copiar enlace"}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="modal-empty">Todavía no has subido archivos de esta tarea a Drive.</p>
      )}
    </div>
  );
}
