const LINKS = [
  { id: "dashboard", label: "Dashboard", icon: "🏠" },
  { id: "escritorio", label: "Escritorio", icon: "🛠️" },
  { id: "drive", label: "Drive", icon: "📁" },
  { id: "perfil", label: "Perfil", icon: "👤" },
];

export default function Sidebar({ page, onNavigate }) {
  return (
    <nav className="sidebar">
      <div className="sidebar-logo">Estud</div>
      <div className="sidebar-links">
        {LINKS.map((link) => (
          <button
            key={link.id}
            className={`sidebar-link ${page === link.id ? "active" : ""}`}
            onClick={() => onNavigate(link.id)}
          >
            <span className="sidebar-icon">{link.icon}</span>
            {link.label}
          </button>
        ))}
      </div>
    </nav>
  );
}
