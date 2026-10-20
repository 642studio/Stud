import { useEffect, useState } from "react";
import { API_URL } from "./taskUtils";

function formatDateTime(value) {
  if (!value) return "Nunca";
  const d = new Date(value.replace(" ", "T") + "Z");
  return d.toLocaleString("es-MX", { dateStyle: "medium", timeStyle: "short" });
}

export default function Profile() {
  const [profile, setProfile] = useState(null);
  const [settings, setSettings] = useState(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savedAt, setSavedAt] = useState(null);
  const [error, setError] = useState(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [platform, setPlatform] = useState(null);
  const [platformPassword, setPlatformPassword] = useState("");
  const [savingPlatform, setSavingPlatform] = useState(false);
  const [platformSavedAt, setPlatformSavedAt] = useState(null);

  function loadProfile() {
    fetch(`${API_URL}/api/profile`)
      .then((res) => {
        if (!res.ok) throw new Error("No se pudo cargar el perfil");
        return res.json();
      })
      .then(setProfile)
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    loadProfile();

    fetch(`${API_URL}/api/settings`)
      .then((res) => res.json())
      .then(setSettings)
      .catch(() => {});

    fetch(`${API_URL}/api/settings/platform`)
      .then((res) => res.json())
      .then(setPlatform)
      .catch(() => {});
  }, []);

  async function savePlatform(e) {
    e.preventDefault();
    const usernameChanged = profile && platform.username !== profile.username;
    if (usernameChanged) {
      const wipe = window.confirm(
        "Vas a cambiar de cuenta de iVirtual. Las tareas que tienes ahora son de la cuenta anterior.\n\n¿Borrarlas antes de sincronizar con la cuenta nueva?"
      );
      if (wipe) {
        await fetch(`${API_URL}/api/tasks`, { method: "DELETE" });
      }
    }

    setSavingPlatform(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/settings/platform`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: platform.username,
          base_url: platform.base_url,
          password: platformPassword,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "No se pudo guardar la cuenta de iVirtual");
      }
      setPlatform(await res.json());
      setPlatformPassword("");
      setPlatformSavedAt(Date.now());
      loadProfile();
    } catch (e) {
      setError(e.message);
    } finally {
      setSavingPlatform(false);
    }
  }

  async function saveSettings(e) {
    e.preventDefault();
    setSavingSettings(true);
    setSavedAt(null);
    try {
      const res = await fetch(`${API_URL}/api/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error();
      setSettings(await res.json());
      setSavedAt(Date.now());
    } catch {
      setError("No se pudo guardar tus datos de portada");
    } finally {
      setSavingSettings(false);
    }
  }

  async function uploadLogo(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingLogo(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await fetch(`${API_URL}/api/settings/logo`, { method: "POST", body });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "No se pudo subir el logo");
      }
      setSettings(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setUploadingLogo(false);
      e.target.value = "";
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>Perfil</h1>
          <p className="subtitle">Tu cuenta y tus plataformas conectadas</p>
        </div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      {profile && (
        <>
          <section className="profile-card">
            <div className="profile-avatar">{profile.university.slice(0, 2)}</div>
            <div>
              <h2>{profile.university}</h2>
              <p className="profile-username">Matrícula: {profile.username}</p>
              <p className="profile-url">{profile.base_url}</p>
            </div>
          </section>

          <div className="stats-row">
            <div className="stat-card">
              <span className="stat-value">{profile.total_tasks}</span>
              <span className="stat-label">Tareas totales</span>
            </div>
            <div className="stat-card stat-completadas">
              <span className="stat-value">{profile.completed_tasks}</span>
              <span className="stat-label">Completadas</span>
            </div>
            <div className="stat-card">
              <span className="stat-value">{profile.courses.length}</span>
              <span className="stat-label">Materias</span>
            </div>
          </div>
        </>
      )}

      {platform && (
        <section className="task-section">
          <h2 className="section-title">Cuenta de iVirtual</h2>
          <p className="settings-hint">
            Esta es la cuenta que Estud usa para sincronizar. Cámbiala para usar Estud con otro
            usuario de ITSON.
          </p>
          <form className="settings-form" onSubmit={savePlatform}>
            <label>
              Usuario / matrícula
              <input
                type="text"
                value={platform.username}
                onChange={(e) => setPlatform({ ...platform, username: e.target.value })}
              />
            </label>
            <label>
              Contraseña
              <input
                type="password"
                value={platformPassword}
                onChange={(e) => setPlatformPassword(e.target.value)}
                placeholder={platform.password_set ? "•••••••• (sin cambios)" : "Ingresa una contraseña"}
                autoComplete="new-password"
              />
            </label>
            <label style={{ gridColumn: "1 / -1" }}>
              URL de la plataforma
              <input
                type="text"
                value={platform.base_url}
                onChange={(e) => setPlatform({ ...platform, base_url: e.target.value })}
              />
            </label>
            <div className="settings-actions">
              <button type="submit" className="sync-btn" disabled={savingPlatform}>
                {savingPlatform ? "Guardando…" : "Guardar cuenta"}
              </button>
              {platformSavedAt && <span className="settings-saved">Guardado ✓</span>}
            </div>
          </form>
        </section>
      )}

      {settings && (
        <section className="task-section">
          <h2 className="section-title">Datos para tu portada</h2>
          <p className="settings-hint">
            Se usan para autocompletar la portada de cada tarea (nombre, matrícula, universidad).
          </p>
          <div className="logo-upload-row" style={{ marginBottom: 16 }}>
            <img
              className="logo-upload-preview"
              src={settings.logo_url ? `${API_URL}${settings.logo_url}` : "/itson-logo.png"}
              alt="Logo de tu institución"
            />
            <div>
              <label className="sync-btn" style={{ display: "inline-block", cursor: "pointer" }}>
                {uploadingLogo ? "Subiendo…" : "Subir logo de tu institución"}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/svg+xml,image/webp"
                  onChange={uploadLogo}
                  disabled={uploadingLogo}
                  style={{ display: "none" }}
                />
              </label>
              <p className="settings-hint" style={{ margin: "6px 0 0" }}>
                PNG, JPG, SVG o WEBP. Se usa en la portada de tus tareas.
              </p>
            </div>
          </div>

          <form className="settings-form" onSubmit={saveSettings}>
            <label>
              Nombre completo
              <input
                type="text"
                value={settings.full_name}
                onChange={(e) => setSettings({ ...settings, full_name: e.target.value })}
                placeholder="Ej. Fernando Villalba"
              />
            </label>
            <label>
              Matrícula
              <input
                type="text"
                value={settings.student_id}
                onChange={(e) => setSettings({ ...settings, student_id: e.target.value })}
              />
            </label>
            <label>
              Universidad
              <input
                type="text"
                value={settings.university}
                onChange={(e) => setSettings({ ...settings, university: e.target.value })}
              />
            </label>
            <label>
              Carrera
              <input
                type="text"
                value={settings.career}
                onChange={(e) => setSettings({ ...settings, career: e.target.value })}
                placeholder="Ej. Ingeniería en Software"
              />
            </label>
            <div className="settings-actions">
              <button type="submit" className="sync-btn" disabled={savingSettings}>
                {savingSettings ? "Guardando…" : "Guardar"}
              </button>
              {savedAt && <span className="settings-saved">Guardado ✓</span>}
            </div>
          </form>
        </section>
      )}

      {profile && (
        <>
          <section className="task-section">
            <h2 className="section-title">Materias sincronizadas</h2>
            <ul className="profile-courses">
              {profile.courses.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </section>

          <p className="profile-last-sync">Última sincronización: {formatDateTime(profile.last_sync)}</p>
        </>
      )}
    </div>
  );
}
