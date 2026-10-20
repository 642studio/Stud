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


def _system_prompt(task: dict) -> str:
    detail = json.loads(task["detail_json"]) if task.get("detail_json") else {}
    checklist = json.loads(task["checklist_json"]) if task.get("checklist_json") else []
    material = _strip_html(detail.get("description_html"))[:3000]
    checklist_text = "\n".join(f"- {c['text']}" for c in checklist) or "(sin checklist generada aún)"

    return (
        "Eres un asistente de investigación que ayuda a un estudiante universitario a trabajar "
        f"en la tarea \"{task['title']}\" del curso \"{task['course']}\".\n"
        "Ayúdalo a investigar el tema, explicar conceptos y resumir en puntos claros lo que va "
        "necesitando, en español. Busca en internet cuando haga falta información que no esté "
        "en el material de la tarea. Sé conciso, usa viñetas cuando resumas, y cita de dónde "
        "sacaste la información cuando busques en la web.\n\n"
        f"Material de la tarea:\n{material or '(sin descripción disponible)'}\n\n"
        f"Lista de pendientes de la tarea:\n{checklist_text}"
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
