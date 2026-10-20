import { useMemo, useState } from "react";
import {
  SECTION_ORDER,
  SECTION_LABEL,
  TAG_META,
  courseColor,
  formatDue,
} from "./taskUtils";

export default function Dashboard({
  tasks,
  loading,
  syncing,
  error,
  onSync,
  onToggle,
  onOpenTask,
}) {
  const [showCompleted, setShowCompleted] = useState(false);
  const [courseFilter, setCourseFilter] = useState("todas");
  const [tagFilter, setTagFilter] = useState("todos");
  const [dateFilter, setDateFilter] = useState("todas");

  const courses = useMemo(
    () => [...new Set(tasks.map((t) => t.course).filter(Boolean))].sort(),
    [tasks]
  );

  const tagCounts = useMemo(() => {
    const counts = {};
    for (const t of tasks) {
      if (t.tag) counts[t.tag] = (counts[t.tag] || 0) + 1;
    }
    return counts;
  }, [tasks]);

  const stats = useMemo(() => {
    const pending = tasks.filter((t) => !t.completed);
    return {
      pendientes: pending.length,
      vencidas: pending.filter((t) => t.status === "vencida").length,
      estaSemana: pending.filter((t) => t.status === "esta_semana").length,
      completadas: tasks.filter((t) => t.completed).length,
    };
  }, [tasks]);

  const filtered = useMemo(() => {
    return tasks.filter((t) => {
      if (courseFilter !== "todas" && t.course !== courseFilter) return false;
      if (tagFilter !== "todos" && t.tag !== tagFilter) return false;
      if (dateFilter !== "todas" && !t.completed && t.status !== dateFilter) return false;
      return true;
    });
  }, [tasks, courseFilter, tagFilter, dateFilter]);

  const grouped = useMemo(() => {
    const groups = { vencida: [], esta_semana: [], proxima: [], sin_fecha: [] };
    const completed = [];
    for (const t of filtered) {
      if (t.completed) completed.push(t);
      else if (groups[t.status]) groups[t.status].push(t);
    }
    return { groups, completed };
  }, [filtered]);

  const hasFilters = courseFilter !== "todas" || tagFilter !== "todos" || dateFilter !== "todas";

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <h1>Dashboard</h1>
          <p className="subtitle">
            {loading ? "Cargando tus tareas…" : `${stats.pendientes} tareas pendientes`}
          </p>
        </div>
        <button className="sync-btn" onClick={onSync} disabled={syncing}>
          {syncing ? "Sincronizando…" : "Sincronizar iVirtual"}
        </button>
      </header>

      {error && <div className="error-banner">{error}</div>}

      {!loading && tasks.length > 0 && (
        <div className="stats-row">
          <div className="stat-card">
            <span className="stat-value">{stats.pendientes}</span>
            <span className="stat-label">Pendientes</span>
          </div>
          <div className="stat-card stat-vencida">
            <span className="stat-value">{stats.vencidas}</span>
            <span className="stat-label">Vencidas</span>
          </div>
          <div className="stat-card stat-semana">
            <span className="stat-value">{stats.estaSemana}</span>
            <span className="stat-label">Esta semana</span>
          </div>
          <div className="stat-card stat-completadas">
            <span className="stat-value">{stats.completadas}</span>
            <span className="stat-label">Completadas</span>
          </div>
        </div>
      )}

      {!loading && tasks.length > 0 && (
        <div className="filters-row">
          <select
            className="filter-select"
            value={courseFilter}
            onChange={(e) => setCourseFilter(e.target.value)}
          >
            <option value="todas">Todas las materias</option>
            {courses.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>

          <select
            className="filter-select"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
          >
            <option value="todas">Todas las fechas</option>
            {SECTION_ORDER.map((key) => (
              <option key={key} value={key}>
                {SECTION_LABEL[key]}
              </option>
            ))}
          </select>

          <div className="tag-filters">
            <button
              className={`tag-chip ${tagFilter === "todos" ? "active" : ""}`}
              onClick={() => setTagFilter("todos")}
            >
              Todos los tipos
            </button>
            {Object.entries(TAG_META)
              .filter(([key]) => tagCounts[key])
              .map(([key, meta]) => (
                <button
                  key={key}
                  className={`tag-chip ${tagFilter === key ? "active" : ""}`}
                  style={tagFilter === key ? { background: meta.color, borderColor: meta.color } : {}}
                  onClick={() => setTagFilter(key)}
                >
                  {meta.label} <span className="tag-chip-count">{tagCounts[key]}</span>
                </button>
              ))}
          </div>

          {hasFilters && (
            <button
              className="clear-filters"
              onClick={() => {
                setCourseFilter("todas");
                setTagFilter("todos");
                setDateFilter("todas");
              }}
            >
              Limpiar filtros
            </button>
          )}
        </div>
      )}

      {!loading && tasks.length === 0 && (
        <div className="empty-state">
          <p>Todavía no hay tareas. Presiona "Sincronizar iVirtual" para traerlas.</p>
        </div>
      )}

      {!loading && tasks.length > 0 && filtered.length === 0 && (
        <div className="empty-state">
          <p>Ninguna tarea coincide con estos filtros.</p>
        </div>
      )}

      {SECTION_ORDER.map((key) =>
        grouped.groups[key].length > 0 ? (
          <section key={key} className="task-section">
            <h2 className={`section-title ${key}`}>
              {SECTION_LABEL[key]} <span className="count">{grouped.groups[key].length}</span>
            </h2>
            <ul className="task-list">
              {grouped.groups[key].map((t) => (
                <TaskCard key={t.id} task={t} onToggle={onToggle} onOpen={onOpenTask} />
              ))}
            </ul>
          </section>
        ) : null
      )}

      {grouped.completed.length > 0 && (
        <section className="task-section">
          <h2 className="section-title completed-toggle" onClick={() => setShowCompleted((s) => !s)}>
            Completadas <span className="count">{grouped.completed.length}</span>
            <span className="chevron">{showCompleted ? "▾" : "▸"}</span>
          </h2>
          {showCompleted && (
            <ul className="task-list">
              {grouped.completed.map((t) => (
                <TaskCard key={t.id} task={t} onToggle={onToggle} onOpen={onOpenTask} />
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}

function TaskCard({ task, onToggle, onOpen }) {
  const tagMeta = TAG_META[task.tag];
  return (
    <li className={`task-card ${task.completed ? "done" : ""}`}>
      <input type="checkbox" checked={task.completed} onChange={() => onToggle(task)} className="checkbox" />
      <div className="task-body">
        <div className="task-top">
          <span className="course-badge" style={{ background: courseColor(task.course) }}>
            {task.course}
          </span>
          {tagMeta && (
            <span className="type-badge" style={{ color: tagMeta.color, borderColor: tagMeta.color }}>
              {tagMeta.label}
            </span>
          )}
          <span className="due">{formatDue(task.due)}</span>
        </div>
        <button className="task-title" onClick={() => onOpen(task.id)}>
          {task.summary || task.title}
        </button>
      </div>
    </li>
  );
}
