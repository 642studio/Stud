import { useEffect, useState } from "react";
import "./App.css";
import { API_URL } from "./taskUtils";
import Sidebar from "./Sidebar";
import Dashboard from "./Dashboard";
import Profile from "./Profile";
import Drive from "./Drive";
import Workbench from "./Workbench";
import TaskDetail from "./TaskDetail";

function initialPage() {
  const params = new URLSearchParams(window.location.search);
  const requested = params.get("page");
  return ["dashboard", "drive", "perfil", "escritorio"].includes(requested) ? requested : "dashboard";
}

export default function App() {
  const [page, setPage] = useState(initialPage);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [selectedTaskId, setSelectedTaskId] = useState(null);

  async function loadTasks() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/tasks`);
      if (!res.ok) throw new Error("No se pudo cargar tus tareas");
      setTasks(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSync() {
    setSyncing(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/sync`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "No se pudo sincronizar con iVirtual");
      }
      await loadTasks();

      const sumRes = await fetch(`${API_URL}/api/summarize`, { method: "POST" });
      if (sumRes.ok) {
        await loadTasks();
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setSyncing(false);
    }
  }

  async function toggleComplete(task) {
    const next = !task.completed;
    setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, completed: next } : t)));
    try {
      const res = await fetch(`${API_URL}/api/tasks/${encodeURIComponent(task.id)}/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ completed: next }),
      });
      if (!res.ok) throw new Error();
    } catch {
      setTasks((prev) => prev.map((t) => (t.id === task.id ? { ...t, completed: !next } : t)));
    }
  }

  useEffect(() => {
    loadTasks();
  }, []);

  const selectedTask = tasks.find((t) => t.id === selectedTaskId) || null;

  return (
    <div className="shell">
      <Sidebar page={page} onNavigate={setPage} />

      <main className="main-content">
        {page === "dashboard" && (
          <Dashboard
            tasks={tasks}
            loading={loading}
            syncing={syncing}
            error={error}
            onSync={handleSync}
            onToggle={toggleComplete}
            onOpenTask={setSelectedTaskId}
          />
        )}
        {page === "escritorio" && <Workbench tasks={tasks} />}
        {page === "drive" && <Drive />}
        {page === "perfil" && <Profile />}
      </main>

      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          onClose={() => setSelectedTaskId(null)}
          onToggle={toggleComplete}
        />
      )}
    </div>
  );
}
