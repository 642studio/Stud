"""Almacenamiento SQLite de tareas sincronizadas desde las plataformas escolares."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "estud.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    course TEXT,
    title TEXT NOT NULL,
    due TEXT,
    url TEXT,
    modulename TEXT,
    raw_description TEXT,
    summary TEXT,
    tag TEXT,
    detail_json TEXT,
    detail_fetched_at TEXT,
    checklist_json TEXT,
    material_text TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    full_name TEXT,
    student_id TEXT,
    university TEXT,
    career TEXT,
    logo_url TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS course_professors (
    course TEXT PRIMARY KEY,
    professor TEXT
);

CREATE TABLE IF NOT EXISTS platform_credentials (
    platform TEXT PRIMARY KEY,
    base_url TEXT,
    username TEXT,
    password TEXT
);

CREATE TABLE IF NOT EXISTS google_oauth (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    client_id TEXT,
    client_secret TEXT,
    allowed_domain TEXT,
    refresh_token TEXT,
    email TEXT
);

CREATE TABLE IF NOT EXISTS drive_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS task_documents (
    task_id TEXT PRIMARY KEY,
    content TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "raw_description" not in existing_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN raw_description TEXT")
        if "detail_json" not in existing_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN detail_json TEXT")
            conn.execute("ALTER TABLE tasks ADD COLUMN detail_fetched_at TEXT")
        if "checklist_json" not in existing_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN checklist_json TEXT")
        if "tag" not in existing_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN tag TEXT")
        if "material_text" not in existing_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN material_text TEXT")
        existing_settings_cols = {row["name"] for row in conn.execute("PRAGMA table_info(settings)")}
        if "logo_url" not in existing_settings_cols:
            conn.execute("ALTER TABLE settings ADD COLUMN logo_url TEXT")


def upsert_tasks(source: str, tasks: list[dict]):
    """Inserta tareas nuevas y actualiza las existentes sin pisar el estado 'completed'."""
    with get_conn() as conn:
        for t in tasks:
            task_id = f"{source}:{t['id']}"
            conn.execute(
                """
                INSERT INTO tasks (id, source, course, title, due, url, modulename, raw_description, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    course = excluded.course,
                    title = excluded.title,
                    due = excluded.due,
                    url = excluded.url,
                    modulename = excluded.modulename,
                    raw_description = excluded.raw_description,
                    updated_at = datetime('now')
                """,
                (
                    task_id,
                    source,
                    t.get("course"),
                    t.get("title"),
                    t.get("due"),
                    t.get("url"),
                    t.get("modulename"),
                    t.get("description_html"),
                ),
            )


def list_tasks():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY (due IS NULL), due ASC").fetchall()
        return [dict(r) for r in rows]


def set_completed(task_id: str, completed: bool):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE tasks SET completed = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if completed else 0, task_id),
        )
        return cur.rowcount > 0


def set_summary(task_id: str, summary: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET summary = ?, updated_at = datetime('now') WHERE id = ?",
            (summary, task_id),
        )


def set_summary_and_tag(task_id: str, summary: str, tag: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET summary = ?, tag = ?, updated_at = datetime('now') WHERE id = ?",
            (summary, tag, task_id),
        )


def set_tag(task_id: str, tag: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET tag = ?, updated_at = datetime('now') WHERE id = ?",
            (tag, task_id),
        )


def get_task(task_id: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def set_detail(task_id: str, detail: dict):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET detail_json = ?, detail_fetched_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
            (json.dumps(detail, ensure_ascii=False), task_id),
        )


def set_checklist(task_id: str, items: list[dict]):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET checklist_json = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(items, ensure_ascii=False), task_id),
        )


def set_material_text(task_id: str, text: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET material_text = ?, updated_at = datetime('now') WHERE id = ?",
            (text, task_id),
        )


def toggle_checklist_item(task_id: str, item_id: int, done: bool):
    with get_conn() as conn:
        row = conn.execute("SELECT checklist_json FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row or not row["checklist_json"]:
            return []
        items = json.loads(row["checklist_json"])
        for item in items:
            if item["id"] == item_id:
                item["done"] = done
        conn.execute(
            "UPDATE tasks SET checklist_json = ?, updated_at = datetime('now') WHERE id = ?",
            (json.dumps(items, ensure_ascii=False), task_id),
        )
        return items


def get_settings():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        if not row:
            return {"full_name": "", "student_id": "", "university": "", "career": "", "logo_url": None}
        return dict(row)


def set_logo_url(logo_url: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings (id, logo_url) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET logo_url = excluded.logo_url
            """,
            (logo_url,),
        )
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        return dict(row)


def get_professor(course: str) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT professor FROM course_professors WHERE course = ?", (course,)).fetchone()
        return row["professor"] if row else ""


def set_professor(course: str, professor: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO course_professors (course, professor) VALUES (?, ?)
            ON CONFLICT(course) DO UPDATE SET professor = excluded.professor
            """,
            (course, professor),
        )


def update_settings(data: dict):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings (id, full_name, student_id, university, career)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                full_name = excluded.full_name,
                student_id = excluded.student_id,
                university = excluded.university,
                career = excluded.career
            """,
            (data.get("full_name", ""), data.get("student_id", ""), data.get("university", ""), data.get("career", "")),
        )
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        return dict(row)


def list_chat_messages(task_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE task_id = ? ORDER BY id ASC", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def add_chat_message(task_id: str, role: str, content: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_messages (task_id, role, content) VALUES (?, ?, ?)",
            (task_id, role, content),
        )


def get_platform_credentials(platform: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM platform_credentials WHERE platform = ?", (platform,)
        ).fetchone()
        return dict(row) if row else None


def set_platform_credentials(platform: str, base_url: str, username: str, password: str = None):
    """password=None deja la contraseña guardada sin cambios."""
    with get_conn() as conn:
        if password is None:
            existing = conn.execute(
                "SELECT password FROM platform_credentials WHERE platform = ?", (platform,)
            ).fetchone()
            password = existing["password"] if existing else ""
        conn.execute(
            """
            INSERT INTO platform_credentials (platform, base_url, username, password)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(platform) DO UPDATE SET
                base_url = excluded.base_url,
                username = excluded.username,
                password = excluded.password
            """,
            (platform, base_url, username, password),
        )
        row = conn.execute(
            "SELECT * FROM platform_credentials WHERE platform = ?", (platform,)
        ).fetchone()
        return dict(row)


def clear_tasks():
    with get_conn() as conn:
        conn.execute("DELETE FROM chat_messages")
        conn.execute("DELETE FROM tasks")


def get_google_oauth():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM google_oauth WHERE id = 1").fetchone()
        return dict(row) if row else None


def set_google_app_credentials(client_id: str, client_secret: str, allowed_domain: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO google_oauth (id, client_id, client_secret, allowed_domain)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                client_id = excluded.client_id,
                client_secret = excluded.client_secret,
                allowed_domain = excluded.allowed_domain
            """,
            (client_id, client_secret, allowed_domain),
        )


def set_google_tokens(refresh_token: str, email: str):
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE google_oauth SET refresh_token = ?, email = ? WHERE id = 1
            """,
            (refresh_token, email),
        )


def disconnect_google():
    with get_conn() as conn:
        conn.execute("UPDATE google_oauth SET refresh_token = NULL, email = NULL WHERE id = 1")


def add_drive_link(task_id: str, name: str, url: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO drive_links (task_id, name, url) VALUES (?, ?, ?)",
            (task_id, name, url),
        )


def list_drive_links(task_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM drive_links WHERE task_id = ? ORDER BY id DESC", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_document(task_id: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content FROM task_documents WHERE task_id = ?", (task_id,)
        ).fetchone()
        return row["content"] if row else ""


def set_document(task_id: str, content: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO task_documents (task_id, content, updated_at) VALUES (?, ?, datetime('now'))
            ON CONFLICT(task_id) DO UPDATE SET content = excluded.content, updated_at = datetime('now')
            """,
            (task_id, content),
        )
