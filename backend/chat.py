"""Asistente de investigación por tarea: chat con búsqueda web vía la Responses API de OpenAI."""
import json
import os
import re

from openai import OpenAI

from backend import db

MODEL = "gpt-4o-mini"
MAX_HISTORY = 20

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


def _material_text(task: dict) -> str:
    material = (task.get("material_text") or "").strip()
    if material:
        return material[:4000]
    detail = json.loads(task["detail_json"]) if task.get("detail_json") else {}
    return _strip_html(detail.get("description_html"))[:3000]


def _system_prompt(task: dict) -> str:
    checklist = json.loads(task["checklist_json"]) if task.get("checklist_json") else []
    material = _material_text(task)
    checklist_text = "\n".join(f"- {c['text']}" for c in checklist) or "(sin checklist generada aún)"
    document = (db.get_document(task["id"]) or "").strip()

    return (
        "Eres un asistente de investigación que ayuda a un estudiante universitario a trabajar "
        f"en la tarea \"{task['title']}\" del curso \"{task['course']}\", y a redactar el "
        "contenido de su entrega cuando te lo pida.\n"
        "Ayúdalo a investigar el tema, explicar conceptos, redactar secciones y resumir en "
        "puntos claros lo que va necesitando, en español. Busca en internet cuando haga falta "
        "información que no esté en el material de la tarea. Sé conciso, usa viñetas cuando "
        "resumas, cita de dónde sacaste la información cuando busques en la web, y usa bloques "
        "de código con ``` cuando el contenido sea código. Cuando te pidan redactar, escribe "
        "SOLO el texto nuevo a agregar (no repitas lo ya escrito, no agregues comentarios tipo "
        "'aquí tienes').\n\n"
        f"Material real de la tarea:\n{material or '(sin material disponible)'}\n\n"
        f"Lista de pendientes de la tarea:\n{checklist_text}\n\n"
        f"Lo que el alumno ya lleva escrito en su documento:\n{document[-3000:] or '(nada todavía)'}"
    )


def send_chat_message(task_id: str, user_message: str) -> dict:
    task = db.get_task(task_id)
    if not task:
        raise ValueError("Tarea no encontrada")

    client = _get_client()
    history = db.list_chat_messages(task_id)[-MAX_HISTORY:]

    input_messages = [{"role": "system", "content": _system_prompt(task)}]
    for m in history:
        input_messages.append({"role": m["role"], "content": m["content"]})
    input_messages.append({"role": "user", "content": user_message})

    db.add_chat_message(task_id, "user", user_message)

    resp = client.responses.create(
        model=MODEL,
        input=input_messages,
        tools=[{"type": "web_search_preview"}],
    )
    reply = resp.output_text or "No pude generar una respuesta."

    db.add_chat_message(task_id, "assistant", reply)
    return {"role": "assistant", "content": reply}
