"""Orquesta la sincronización: conecta con una plataforma escolar y guarda sus tareas."""
from backend import db
from backend.moodle_client import get_itson_client

SOURCE_ITSON = "itson_moodle"


def sync_itson():
    client = get_itson_client()
    tasks = client.get_upcoming_events()
    tasks = [t for t in tasks if t.get("id") is not None]
    db.upsert_tasks(SOURCE_ITSON, tasks)
    return len(tasks)
