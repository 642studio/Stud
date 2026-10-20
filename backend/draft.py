"""Redacción asistida por IA para el documento de una tarea (Escritorio)."""
import json
import os
import re

from openai import OpenAI

from backend import db

MODEL = "gpt-4o-mini"

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def _strip_html(html) -> str:
    if not html:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def draft_section(task_id: str, instruction: str, current_content: str) -> str:
    task = db.get_task(task_id)
    if not task:
        raise ValueError("Tarea no encontrada")

    detail = json.loads(task["detail_json"]) if task.get("detail_json") else {}
    checklist = json.loads(task["checklist_json"]) if task.get("checklist_json") else []
    material = _strip_html(detail.get("description_html"))[:3000]
    checklist_text = "\n".join(f"- {c['text']}" for c in checklist)

    client = _get_client()
    prompt = (
        "Eres un asistente que ayuda a un estudiante universitario a redactar el contenido de "
        f"su tarea \"{task['title']}\" del curso \"{task['course']}\".\n\n"
        f"Material de la tarea:\n{material or '(sin descripción disponible)'}\n\n"
        f"Lista de pendientes de la tarea:\n{checklist_text or '(sin checklist)'}\n\n"
        f"Lo que el alumno ya lleva escrito:\n{current_content[-3000:] or '(nada todavía)'}\n\n"
        f"Instrucción del alumno: {instruction}\n\n"
        "Redacta SOLO el texto nuevo que debe agregarse (no repitas lo que ya escribió ni "
        "agregues comentarios tipo 'aquí tienes'). Español, redacción clara y académica. "
        "Usa **negrita** para términos clave si aplica, y separa párrafos con una línea en blanco."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()
