"""Convierte títulos crípticos de Moodle en resúmenes amigables y clasifica el tipo de tarea."""
import json
import os
import re
from html import unescape
from typing import Optional

from openai import OpenAI

from backend import db

MODEL = "gpt-4o-mini"
BATCH_SIZE = 15

TAGS = ["tarea", "examen", "proyecto", "cuaderno", "lectura", "foro", "practica", "otro"]

MODULE_TAG_OVERRIDE = {
    "forum": "foro",
    "quiz": "examen",
}

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


def _strip_html(html: Optional[str]) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def summarize_pending(batch_size: int = BATCH_SIZE) -> int:
    """Genera resúmenes y tag para las tareas que aún no lo tienen. Devuelve cuántas se procesaron."""
    pending = [t for t in db.list_tasks() if not t.get("summary") or not t.get("tag")]
    if not pending:
        return 0

    client = _get_client()
    total = 0

    for i in range(0, len(pending), batch_size):
        batch = pending[i : i + batch_size]

        items = [
            {
                "id": t["id"],
                "curso": t["course"],
                "titulo_crudo": t["title"],
                "contexto": _strip_html(t.get("raw_description"))[:600],
            }
            for t in batch
        ]
        prompt = (
            "Eres un asistente que ayuda a un estudiante universitario a entender sus tareas de Moodle.\n"
            "Te doy una lista de tareas en JSON. El 'titulo_crudo' suele ser genérico "
            "(ej. termina en 'está en fecha de entrega'); usa el 'contexto' (texto de la "
            "actividad) para describir en una frase corta, clara y en español qué debe "
            "hacer el alumno. Máximo 15 palabras, sin saludos ni relleno. Si el contexto "
            "no da información útil, limpia el titulo_crudo en vez de inventar contenido.\n\n"
            "Además clasifica cada tarea con un 'tipo', eligiendo EXACTAMENTE uno de esta lista: "
            f"{json.dumps(TAGS, ensure_ascii=False)}. Usa 'cuaderno' para trabajo de notas/apuntes, "
            "'examen' para exámenes o quizzes, 'proyecto' para trabajos grandes o de equipo, "
            "'lectura' para lecturas, 'practica' para ejercicios prácticos, 'foro' para discusiones, "
            "'tarea' para entregables genéricos, y 'otro' si no calza en ninguno.\n\n"
            'Responde SOLO con un objeto JSON {"items": [{"id": "...", "resumen": "...", "tipo": "..."}]}, '
            "mismo orden y mismos ids que te di.\n\n"
            f"Tareas:\n{json.dumps(items, ensure_ascii=False)}"
        )

        results = []
        for attempt in range(2):
            resp = client.chat.completions.create(
                model=MODEL,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content
            try:
                results = json.loads(raw).get("items", [])
                break
            except json.JSONDecodeError:
                if attempt == 1:
                    results = []

        by_id = {t["id"]: t for t in batch}
        for r in results:
            task = by_id.get(r.get("id"))
            if not task or not r.get("resumen"):
                continue
            tag = MODULE_TAG_OVERRIDE.get(task.get("modulename")) or r.get("tipo")
            if tag not in TAGS:
                tag = "otro"
            db.set_summary_and_tag(r["id"], r["resumen"], tag)
            total += 1

    return total
