export const API_URL = "http://127.0.0.1:8000";

export const SECTION_ORDER = ["vencida", "esta_semana", "proxima", "sin_fecha"];
export const SECTION_LABEL = {
  vencida: "Vencidas",
  esta_semana: "Esta semana",
  proxima: "Próximas",
  sin_fecha: "Sin fecha",
};

export const TAG_META = {
  tarea: { label: "Tarea", color: "#6366f1" },
  examen: { label: "Examen", color: "#ef4444" },
  proyecto: { label: "Proyecto", color: "#8b5cf6" },
  cuaderno: { label: "Cuaderno", color: "#10b981" },
  lectura: { label: "Lectura", color: "#0ea5e9" },
  foro: { label: "Foro", color: "#f59e0b" },
  practica: { label: "Práctica", color: "#14b8a6" },
  otro: { label: "Otro", color: "#9ca3af" },
};

export function courseColor(course) {
  const colors = ["#6366f1", "#06b6d4", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6", "#ec4899"];
  let hash = 0;
  for (const ch of course || "") hash = (hash * 31 + ch.charCodeAt(0)) % colors.length;
  return colors[Math.abs(hash) % colors.length];
}

export function formatDue(due) {
  if (!due) return "Sin fecha";
  const d = new Date(due);
  return (
    d.toLocaleDateString("es-MX", { weekday: "short", day: "numeric", month: "short" }) +
    " · " +
    d.toLocaleTimeString("es-MX", { hour: "2-digit", minute: "2-digit" })
  );
}
