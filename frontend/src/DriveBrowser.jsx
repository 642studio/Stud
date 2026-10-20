import { useEffect, useState } from "react";
import { API_URL } from "./taskUtils";

function formatDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" });
}

function formatSize(bytes) {
  if (!bytes) return "";
  const n = Number(bytes);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DriveBrowser() {
  const [folderId, setFolderId] = useState(null);
  const [path, setPath] = useState([]);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);

  function load(id, query) {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    else if (id) params.set("folder_id", id);

    fetch(`${API_URL}/api/drive/files?${params.toString()}`)
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "No se pudo listar Drive");
        }
        return res.json();
      })
      .then((data) => {
        setFiles(data.files);
        if (!query) setPath(data.path);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load(folderId, null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [folderId]);

  function openFolder(folder) {
    setSearch("");
    setFolderId(folder.id);
  }

  function goToPath(index) {
    setSearch("");
    if (index === -1) {
      setFolderId(null);
    } else {
      setFolderId(path[index].id);
    }
  }

  function openFile(file) {
    window.open(file.webViewLink, "_blank", "noreferrer");
  }

  async function trash(file, e) {
    e.stopPropagation();
    if (!window.confirm(`¿Mover "${file.name}" a la papelera?`)) return;
    try {
      const res = await fetch(`${API_URL}/api/drive/files/${file.id}`, { method: "DELETE" });
      if (!res.ok) throw new Error();
      setFiles((prev) => prev.filter((f) => f.id !== file.id));
    } catch {
      setError("No se pudo borrar el archivo");
    }
  }

  async function newFolder() {
    const name = window.prompt("Nombre de la carpeta");
    if (!name) return;
    try {
      const res = await fetch(`${API_URL}/api/drive/folders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, parent_id: folderId }),
      });
      if (!res.ok) throw new Error();
      load(folderId, null);
    } catch {
      setError("No se pudo crear la carpeta");
    }
  }

  async function uploadHere(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const qs = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
      const res = await fetch(`${API_URL}/api/drive/files/upload${qs}`, {
        method: "POST",
        body,
      });
      if (!res.ok) throw new Error();
      load(folderId, null);
    } catch {
      setError("No se pudo subir el archivo");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  function runSearch(e) {
    e.preventDefault();
    if (search.trim()) load(null, search.trim());
    else load(folderId, null);
  }

  return (
    <div className="drive-browser">
      <div className="drive-toolbar">
        <form className="drive-search" onSubmit={runSearch}>
          <input
            type="text"
            placeholder="Buscar en Drive…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </form>
        <button className="reanalyze-link" onClick={newFolder}>
          + Nueva carpeta
        </button>
        <label className="sync-btn" style={{ display: "inline-block", cursor: "pointer" }}>
          {uploading ? "Subiendo…" : "Subir aquí"}
          <input type="file" onChange={uploadHere} disabled={uploading} style={{ display: "none" }} />
        </label>
      </div>

      <div className="drive-breadcrumb">
        <button onClick={() => goToPath(-1)}>Mi unidad</button>
        {path.map((p, i) => (
          <span key={p.id}>
            <span className="drive-breadcrumb-sep">/</span>
            <button onClick={() => goToPath(i)}>{p.name}</button>
          </span>
        ))}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && <p className="modal-loading">Cargando archivos…</p>}

      {!loading && files.length === 0 && (
        <p className="modal-empty">No hay archivos aquí.</p>
      )}

      {!loading && files.length > 0 && (
        <ul className="drive-file-list">
          {files.map((f) => (
            <li
              key={f.id}
              className="drive-file-row"
              onClick={() => (f.isFolder ? openFolder(f) : openFile(f))}
            >
              <span className="drive-file-icon">{f.isFolder ? "📁" : "📄"}</span>
              <span className="drive-file-name">{f.name}</span>
              <span className="drive-file-meta">{formatSize(f.size)}</span>
              <span className="drive-file-meta">{formatDate(f.modifiedTime)}</span>
              <button className="drive-file-trash" onClick={(e) => trash(f, e)} title="Mover a la papelera">
                🗑️
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
