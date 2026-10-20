import { useEffect, useState } from "react";
import { API_URL } from "./taskUtils";
import DriveBrowser from "./DriveBrowser";

export default function Drive() {
  const [status, setStatus] = useState(null);
  const [form, setForm] = useState({ client_id: "", client_secret: "", allowed_domain: "" });
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  function loadStatus() {
    fetch(`${API_URL}/api/drive/status`)
      .then((res) => res.json())
      .then((data) => {
        setStatus(data);
        setForm((f) => ({ ...f, allowed_domain: data.allowed_domain || "" }));
      })
      .catch(() => {});
  }

  useEffect(() => {
    loadStatus();

    const params = new URLSearchParams(window.location.search);
    if (params.get("drive_connected")) {
      setNotice("Google Drive conectado correctamente.");
    } else if (params.get("drive_error")) {
      setError(decodeURIComponent(params.get("drive_error")));
    }
    if (params.get("drive_connected") || params.get("drive_error")) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  async function saveCredentials(e) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/settings/google`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error();
      loadStatus();
    } catch {
      setError("No se pudo guardar la configuración de Google");
    } finally {
      setSaving(false);
    }
  }

  async function connect() {
    setConnecting(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/drive/auth/start`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "No se pudo iniciar la conexión");
      }
      const { url } = await res.json();
      window.location.href = url;
    } catch (e) {
      setError(e.message);
      setConnecting(false);
    }
  }

  async function disconnect() {
    await fetch(`${API_URL}/api/drive/disconnect`, { method: "POST" });
    loadStatus();
  }

  if (!status) return <div className="page" />;

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>Drive</h1>
          <p className="subtitle">Sube archivos de tus tareas a Google Drive y comparte el enlace</p>
        </div>
      </header>

      {notice && <div className="notice-banner">{notice}</div>}
      {error && <div className="error-banner">{error}</div>}

      {status.connected ? (
        <>
          <section className="profile-card">
            <div className="profile-avatar">📁</div>
            <div style={{ flex: 1 }}>
              <h2>Conectado</h2>
              <p className="profile-username">{status.email}</p>
            </div>
            <button className="reanalyze-link" onClick={disconnect}>
              Desconectar
            </button>
          </section>
          <DriveBrowser />
        </>
      ) : status.configured ? (
        <section className="task-section">
          <h2 className="section-title">Conectar Google Drive</h2>
          <p className="settings-hint">
            {status.allowed_domain
              ? `Debes usar una cuenta de Google del dominio ${status.allowed_domain}.`
              : "Conecta la cuenta de Google que usarás para subir archivos."}
          </p>
          <button className="sync-btn" onClick={connect} disabled={connecting}>
            {connecting ? "Abriendo Google…" : "Conectar con Google"}
          </button>
        </section>
      ) : (
        <section className="task-section">
          <h2 className="section-title">Configurar Google Drive</h2>
          <p className="settings-hint">
            Pega aquí el Client ID y Client Secret que generaste en Google Cloud Console (API de
            Google Drive habilitada, credencial OAuth tipo "Aplicación web", con
            <code> http://localhost:8000/api/drive/callback </code>
            como URI de redirección autorizada).
          </p>
          <form className="settings-form" onSubmit={saveCredentials}>
            <label style={{ gridColumn: "1 / -1" }}>
              Client ID
              <input
                type="text"
                value={form.client_id}
                onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                placeholder="xxxxx.apps.googleusercontent.com"
              />
            </label>
            <label style={{ gridColumn: "1 / -1" }}>
              Client Secret
              <input
                type="password"
                value={form.client_secret}
                onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
                autoComplete="new-password"
              />
            </label>
            <label>
              Dominio institucional (opcional)
              <input
                type="text"
                value={form.allowed_domain}
                onChange={(e) => setForm({ ...form, allowed_domain: e.target.value })}
                placeholder="itson.edu.mx"
              />
            </label>
            <div className="settings-actions">
              <button type="submit" className="sync-btn" disabled={saving}>
                {saving ? "Guardando…" : "Guardar configuración"}
              </button>
            </div>
          </form>
        </section>
      )}
    </div>
  );
}
