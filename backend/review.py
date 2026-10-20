"""Revisa el avance del documento de una tarea contra su checklist (sugerencia, no gate)."""
import json
import os

from openai import OpenAI

from backend import db

MODEL = "gpt-4o-mini"


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def review_document(task_id: str) -> dict:
    task = db.get_task(task_id)
    if not task:
        raise ValueError("Tarea no encontrada")

    checklist = json.loads(task["checklist_json"]) if task.get("checklist_json") else []
    if not checklist:
        return {"items": [], "summary": "Esta tarea no tiene una checklist generada todavía."}

    content = (db.get_document(task_id) or "").strip()
    if not content:
        return {
            "items": [{"id": c["id"], "covered": False, "note": "sin contenido todavía"} for c in checklist],
            "summary": "Todavía no has escrito nada en el documento.",
        }

    material = (task.get("material_text") or "")[:3000]
    checklist_json = json.dumps(
        [{"id": c["id"], "text": c["text"]} for c in checklist], ensure_ascii=False
    )

    client = _get_client()
    prompt = (
        "Eres un asistente que ayuda a un estudiante a revisar si su documento ya cubre los "
        "puntos de la checklist de su tarea, ANTES de que él decida subirlo. Tú solo sugieres, "
        "el alumno decide qué marcar como hecho — nunca digas que algo está 'aprobado'.\n\n"
        f"Material real de la tarea:\n{material or '(sin material)'}\n\n"
        f"Checklist (JSON):\n{checklist_json}\n\n"
        f"Documento actual del alumno:\n{content[:6000]}\n\n"
        "Para cada punto de la checklist, evalúa si el documento ya lo cubre razonablemente. "
        'Responde SOLO con un objeto JSON: {"items": [{"id": <id>, "covered": true|false, '
        '"note": "..."}], "summary": "..."}. "note" es una frase muy corta (máx 12 palabras) '
        "de qué falta cuando covered=false, o cadena vacía cuando covered=true. \"summary\" es "
        "una frase breve y neutral sobre el avance general (ej. '4 de 6 puntos cubiertos; falta "
        "profundizar en X'), en español."
    )
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        result = json.loads(resp.choices[0].message.content)
    except json.JSONDecodeError:
        return {"items": [], "summary": "No se pudo revisar el avance, intenta de nuevo."}

    items = result.get("items", [])
    summary = result.get("summary", "")
    return {"items": items, "summary": summary}
