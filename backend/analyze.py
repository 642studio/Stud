"""Analiza los materiales de una tarea (PDFs, Docs, adjuntos) y genera una checklist accionable."""
import json
import os

from openai import OpenAI

from backend import db
from backend.doc_extract import extract_links, fetch_text_from_url
from backend.moodle_client import get_itson_client

MODEL = "gpt-4o-mini"
MAX_TOTAL_CHARS = 10000

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def _gather_material_text(detail: dict) -> str:
    moodle = get_itson_client()
    chunks = []

    for att in detail.get("attachments", []) or []:
        text = fetch_text_from_url(att["url"], session=moodle.session)
        if text:
            chunks.append(f"[Adjunto: {att['name']}]\n{text}")

    for link in extract_links(detail.get("description_html")):
        if "pluginfile.php" in link:
            continue
        text = fetch_text_from_url(link)
        if text:
            chunks.append(f"[Material enlazado]\n{text}")

    return "\n\n---\n\n".join(chunks)[:MAX_TOTAL_CHARS]


def analyze_task(task_id: str, force: bool = False) -> list:
    task = db.get_task(task_id)
    if not task:
        raise ValueError("Tarea no encontrada")

    if task.get("checklist_json") and not force:
        return json.loads(task["checklist_json"])

    detail = json.loads(task["detail_json"]) if task.get("detail_json") else {}
    material = _gather_material_text(detail)
    db.set_material_text(task_id, material)

    if not material.strip():
        db.set_checklist(task_id, [])
        return []

    client = _get_client()
    prompt = (
        "Eres un asistente que ayuda a un estudiante universitario a entender qué debe hacer "
        "en una tarea, a partir del material real de la actividad (adjuntos, documentos).\n"
        f"Curso: {task.get('course')}\nTítulo: {task.get('title')}\n\n"
        f"Material:\n{material}\n\n"
        "Genera una lista de pasos concretos y accionables (checklist) que el alumno debe "
        "seguir para completar y entregar esta tarea, en español, en orden lógico. "
        "Entre 3 y 8 pasos, cada uno una frase corta imperativa (ej. 'Resuelve el ejercicio 3 "
        "del documento'). Básate solo en lo que dice el material, no inventes requisitos.\n"
        'Responde SOLO con un objeto JSON {"pasos": ["...", "..."]}'
    )
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        pasos = json.loads(resp.choices[0].message.content).get("pasos", [])
    except json.JSONDecodeError:
        pasos = []

    items = [{"id": i, "text": p, "done": False} for i, p in enumerate(pasos)]
    db.set_checklist(task_id, items)
    return items
