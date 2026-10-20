import { useEffect, useState } from "react";
import { API_URL } from "./taskUtils";

const DEFAULT_LOGO = "/itson-logo.png";

function Field({ label, value, editable, onSave, placeholder }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || "");

  useEffect(() => {
    setDraft(value || "");
  }, [value]);

  if (editable && (editing || !value)) {
    return (
      <div className="portada-field">
        <div className="portada-label">{label}—</div>
        <div className="portada-edit-row">
          <input
            className="portada-edit-input"
            value={draft}
            placeholder={placeholder}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft.trim()) {
                onSave(draft.trim());
                setEditing(false);
              }
            }}
            autoFocus={editing}
          />
          <button
            className="portada-save-btn"
            onClick={() => {
              if (draft.trim()) {
                onSave(draft.trim());
                setEditing(false);
              }
            }}
          >
            Guardar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="portada-field" onClick={editable ? () => setEditing(true) : undefined}>
      <div className="portada-label">{label}—</div>
      <div className={`portada-value ${editable ? "editable" : ""}`}>{value}</div>
    </div>
  );
}

export default function PortadaPanel({ taskId }) {
  const [portada, setPortada] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setCopied(false);
    fetch(`${API_URL}/api/tasks/${encodeURIComponent(taskId)}/portada`)
      .then(async (res) => {
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || "No se pudo generar la portada");
        }
        return res.json();
      })
      .then(setPortada)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [taskId]);

  async function saveProfessor(professor) {
    setPortada((prev) => ({ ...prev, professor }));
    try {
      await fetch(`${API_URL}/api/tasks/${encodeURIComponent(taskId)}/portada/professor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ professor }),
      });
    } catch {
      setError("No se pudo guardar el profesor");
    }
  }

  const text = portada
    ? [
        portada.university,
        portada.career,
        "",
        `Alumno: ${portada.full_name || "(configura tu nombre en Perfil)"}`,
        `ID: ${portada.student_id}`,
        `Asignación: ${portada.title}`,
        `Fecha: ${portada.date}`,
        `Materia: ${portada.course}`,
        `Profesor: ${portada.professor || "(sin definir)"}`,
      ].join("\n")
    : "";

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("No se pudo copiar al portapapeles");
    }
  }

  if (loading) return <p className="modal-loading">Generando portada…</p>;
  if (error && !portada) return <div className="modal-error">{error}</div>;
  if (!portada) return null;

  return (
    <div className="portada-panel">
      {!portada.full_name && (
        <p className="portada-warning">
          No tienes nombre configurado — complétalo en Perfil para que aparezca aquí.
        </p>
      )}

      <div className="portada-sheet">
        <img
          className="portada-logo"
          src={portada.logo_url ? `${API_URL}${portada.logo_url}` : DEFAULT_LOGO}
          alt="Logo institución"
        />

        <Field label="Alumno" value={portada.full_name || "(configura tu nombre en Perfil)"} />
        <Field label="ID" value={portada.student_id} />
        <Field label="Asignación" value={portada.title} />
        <Field label="Fecha" value={portada.date} />
        <Field label="Materia" value={portada.course} />
        <Field
          label="Profesor"
          value={portada.professor}
          editable
          placeholder="Nombre del profesor"
          onSave={saveProfessor}
        />

        <p className="portada-footer">{portada.university}</p>
      </div>

      <button className="sync-btn" onClick={copy}>
        {copied ? "Copiado ✓" : "Copiar portada como texto"}
      </button>
    </div>
  );
}
