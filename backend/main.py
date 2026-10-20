"""API de Estud: expone las tareas sincronizadas y permite marcarlas como completadas."""
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend import db
from backend.sync import sync_itson
from backend.summarize import summarize_pending
from backend.analyze import analyze_task
from backend.chat import send_chat_message
from backend.draft import draft_section
from backend.review import review_document
from backend import moodle_client, drive, pdf_builder
from backend.moodle_client import get_itson_client

load_dotenv()
db.init_db()

UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Estud API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


def _status(task: dict) -> str:
    if task["completed"]:
        return "completed"
    if not task["due"]:
        return "sin_fecha"
    due = datetime.fromisoformat(task["due"])
    now = datetime.now()
    if due < now:
        return "vencida"
    if due < now + timedelta(days=7):
        return "esta_semana"
    return "proxima"


@app.get("/api/profile")
def profile():
    tasks = db.list_tasks()
    courses = sorted({t["course"] for t in tasks if t["course"]})
    last_sync = max((t["updated_at"] for t in tasks), default=None)
    try:
        base_url, username, _ = moodle_client.get_credentials()
    except RuntimeError:
        base_url, username = "", ""
    return {
        "university": "ITSON",
        "username": username,
        "base_url": base_url,
        "courses": courses,
        "total_tasks": len(tasks),
        "completed_tasks": sum(1 for t in tasks if t["completed"]),
        "last_sync": last_sync,
    }


class SettingsBody(BaseModel):
    full_name: str = ""
    student_id: str = ""
    university: str = ""
    career: str = ""


@app.get("/api/settings")
def get_settings():
    settings = db.get_settings()
    if not settings.get("student_id"):
        settings["student_id"] = os.environ.get("ITSON_USERNAME", "")
    if not settings.get("university"):
        settings["university"] = "ITSON"
    return settings


@app.put("/api/settings")
def update_settings(body: SettingsBody):
    return db.update_settings(body.dict())


class PlatformCredentialsBody(BaseModel):
    username: str
    password: str = ""
    base_url: str = "https://ivirtual.itson.edu.mx"


@app.get("/api/settings/platform")
def get_platform_settings():
    creds = db.get_platform_credentials(moodle_client.PLATFORM)
    if not creds:
        return {
            "username": os.environ.get("ITSON_USERNAME", ""),
            "base_url": os.environ.get("ITSON_BASE_URL", "https://ivirtual.itson.edu.mx"),
            "password_set": bool(os.environ.get("ITSON_PASSWORD")),
        }
    return {
        "username": creds["username"],
        "base_url": creds["base_url"],
        "password_set": bool(creds["password"]),
    }


@app.put("/api/settings/platform")
def update_platform_settings(body: PlatformCredentialsBody):
    password = body.password if body.password else None
    db.set_platform_credentials(moodle_client.PLATFORM, body.base_url, body.username, password)
    moodle_client.reset_client()
    creds = db.get_platform_credentials(moodle_client.PLATFORM)
    return {"username": creds["username"], "base_url": creds["base_url"], "password_set": bool(creds["password"])}


@app.delete("/api/tasks")
def delete_all_tasks():
    db.clear_tasks()
    return {"ok": True}


class GoogleAppCredentialsBody(BaseModel):
    client_id: str
    client_secret: str
    allowed_domain: str = ""


@app.get("/api/drive/status")
def drive_status():
    oauth = db.get_google_oauth() or {}
    return {
        "configured": bool(oauth.get("client_id") and oauth.get("client_secret")),
        "connected": bool(oauth.get("refresh_token")),
        "email": oauth.get("email"),
        "allowed_domain": oauth.get("allowed_domain"),
    }


@app.put("/api/settings/google")
def set_google_app_credentials(body: GoogleAppCredentialsBody):
    db.set_google_app_credentials(body.client_id, body.client_secret, body.allowed_domain)
    return {"ok": True}


@app.get("/api/drive/auth/start")
def drive_auth_start():
    try:
        url = drive.get_auth_url()
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"url": url}


@app.get("/api/drive/callback")
def drive_auth_callback(code: str = "", error: str = ""):
    frontend = "http://localhost:5173/?page=drive"
    if error:
        return RedirectResponse(f"{frontend}&drive_error={error}")
    try:
        drive.handle_callback(code)
    except Exception as e:
        return RedirectResponse(f"{frontend}&drive_error={e}")
    return RedirectResponse(f"{frontend}&drive_connected=1")


@app.post("/api/drive/disconnect")
def drive_disconnect():
    db.disconnect_google()
    return {"ok": True}


@app.post("/api/drive/files/upload")
async def upload_drive_file(file: UploadFile = File(...), folder_id: str = None):
    try:
        content = await file.read()
        result = drive.upload_file(
            None,
            file.filename or "archivo",
            content,
            file.content_type or "application/octet-stream",
            folder_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo subir el archivo a Drive: {e}")
    return result


@app.get("/api/drive/files")
def list_drive_files(folder_id: str = None, q: str = None):
    try:
        files = drive.list_files(folder_id=folder_id, query=q)
        path = drive.get_file_path(folder_id) if folder_id else []
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo listar Drive: {e}")
    return {"files": files, "path": path}


class CreateFolderBody(BaseModel):
    name: str
    parent_id: str = None


@app.post("/api/drive/folders")
def create_drive_folder(body: CreateFolderBody):
    try:
        return drive.create_folder(body.name, body.parent_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo crear la carpeta: {e}")


@app.delete("/api/drive/files/{file_id}")
def delete_drive_file(file_id: str):
    try:
        drive.trash_file(file_id)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo borrar el archivo: {e}")
    return {"ok": True}


@app.get("/api/tasks/{task_id}/drive")
def get_drive_links(task_id: str):
    if not db.get_task(task_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return db.list_drive_links(task_id)


@app.post("/api/tasks/{task_id}/drive")
async def upload_to_drive(task_id: str, file: UploadFile = File(...)):
    if not db.get_task(task_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    try:
        content = await file.read()
        result = drive.upload_file(
            task_id, file.filename or "archivo", content, file.content_type or "application/octet-stream"
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo subir el archivo a Drive: {e}")
    return result


ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}


@app.post("/api/settings/logo")
async def upload_logo(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_LOGO_TYPES:
        raise HTTPException(status_code=400, detail="Formato no soportado. Usa PNG, JPG, SVG o WEBP.")

    ext = Path(file.filename or "").suffix or ".png"
    filename = f"logo-{uuid.uuid4().hex[:8]}{ext}"
    dest = UPLOADS_DIR / filename
    with open(dest, "wb") as f:
        f.write(await file.read())

    return db.set_logo_url(f"/uploads/{filename}")


MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _build_portada(task: dict) -> dict:
    settings = db.get_settings()
    now = datetime.now()
    return {
        "university": settings.get("university") or "ITSON",
        "career": settings.get("career") or "",
        "logo_url": settings.get("logo_url"),
        "course": task["course"],
        "title": task["summary"] or task["title"],
        "full_name": settings.get("full_name") or "",
        "student_id": settings.get("student_id") or os.environ.get("ITSON_USERNAME", ""),
        "professor": db.get_professor(task["course"]) if task["course"] else "",
        "date": f"{now.day} de {MESES_ES[now.month - 1]} de {now.year}",
    }


@app.get("/api/tasks/{task_id}/portada")
def get_portada(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return _build_portada(task)


class ProfessorBody(BaseModel):
    professor: str


@app.post("/api/tasks/{task_id}/portada/professor")
def set_portada_professor(task_id: str, body: ProfessorBody):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    if task["course"]:
        db.set_professor(task["course"], body.professor)
    return {"professor": body.professor}


class ChatBody(BaseModel):
    message: str


@app.get("/api/tasks/{task_id}/chat")
def get_chat(task_id: str):
    if not db.get_task(task_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return db.list_chat_messages(task_id)


@app.post("/api/tasks/{task_id}/chat")
def post_chat(task_id: str, body: ChatBody):
    try:
        reply = send_chat_message(task_id, body.message)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    except KeyError:
        raise HTTPException(status_code=500, detail="Falta OPENAI_API_KEY en el .env del backend")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo consultar al asistente: {e}")
    return reply


@app.get("/api/tasks")
def get_tasks():
    tasks = db.list_tasks()
    for t in tasks:
        t["status"] = _status(t)
        t["completed"] = bool(t["completed"])
    return tasks


class CompleteBody(BaseModel):
    completed: bool = True


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: str, body: CompleteBody):
    ok = db.set_completed(task_id, body.completed)
    if not ok:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return {"id": task_id, "completed": body.completed}


@app.post("/api/sync")
def sync():
    try:
        count = sync_itson()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo sincronizar iVirtual: {e}")
    return {"source": "itson_moodle", "tasks": count}


@app.post("/api/summarize")
def summarize():
    try:
        count = summarize_pending()
    except KeyError:
        raise HTTPException(status_code=500, detail="Falta OPENAI_API_KEY en el .env del backend")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo generar resúmenes: {e}")
    return {"summarized": count}


@app.get("/api/tasks/{task_id}/detail")
def get_task_detail(task_id: str, refresh: bool = False):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")

    if task["detail_json"] and not refresh:
        detail = json.loads(task["detail_json"])
    else:
        if task["source"] != "itson_moodle":
            raise HTTPException(status_code=501, detail="Fuente no soportada todavía")
        try:
            client = get_itson_client()
            detail = client.get_activity_detail(task["url"])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"No se pudo obtener el detalle de la tarea: {e}")
        db.set_detail(task_id, detail)

    detail["checklist"] = json.loads(task["checklist_json"]) if task["checklist_json"] else None
    detail["material_text"] = task["material_text"]
    return detail


@app.post("/api/tasks/{task_id}/analyze")
def analyze(task_id: str, force: bool = False):
    try:
        items = analyze_task(task_id, force=force)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    except KeyError:
        raise HTTPException(status_code=500, detail="Falta OPENAI_API_KEY en el .env del backend")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo analizar la tarea: {e}")
    return {"checklist": items}


class ChecklistToggleBody(BaseModel):
    item_id: int
    done: bool


@app.post("/api/tasks/{task_id}/checklist/toggle")
def toggle_checklist(task_id: str, body: ChecklistToggleBody):
    items = db.toggle_checklist_item(task_id, body.item_id, body.done)
    return {"checklist": items}


# --- Escritorio: documento por tarea (portada + contenido -> PDF) ---


@app.get("/api/tasks/{task_id}/document")
def get_document(task_id: str):
    if not db.get_task(task_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    return {"content": db.get_document(task_id)}


class DocumentBody(BaseModel):
    content: str = ""


@app.put("/api/tasks/{task_id}/document")
def put_document(task_id: str, body: DocumentBody):
    if not db.get_task(task_id):
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    db.set_document(task_id, body.content)
    return {"ok": True}


class DraftBody(BaseModel):
    instruction: str


@app.post("/api/tasks/{task_id}/document/draft")
def post_draft(task_id: str, body: DraftBody):
    current = db.get_document(task_id)
    try:
        draft = draft_section(task_id, body.instruction, current)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    except KeyError:
        raise HTTPException(status_code=500, detail="Falta OPENAI_API_KEY en el .env del backend")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo redactar: {e}")
    return {"draft": draft}


@app.post("/api/tasks/{task_id}/document/review")
def post_review(task_id: str):
    try:
        result = review_document(task_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    except KeyError:
        raise HTTPException(status_code=500, detail="Falta OPENAI_API_KEY en el .env del backend")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo revisar el avance: {e}")
    return result


def _build_task_pdf(task_id: str) -> bytes:
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    portada = _build_portada(task)
    content = db.get_document(task_id)
    return pdf_builder.build_pdf(portada, content)


@app.get("/api/tasks/{task_id}/document/pdf")
def get_document_pdf(task_id: str):
    try:
        pdf_bytes = _build_task_pdf(task_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo generar el PDF: {e}")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{task_id.split(":")[-1]}.pdf"'},
    )


@app.post("/api/tasks/{task_id}/document/upload-drive")
def upload_document_to_drive(task_id: str):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    try:
        pdf_bytes = _build_task_pdf(task_id)
        filename = f"{(task['summary'] or task['title'])[:60]}.pdf"
        result = drive.upload_file(task_id, filename, pdf_bytes, "application/pdf")
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo subir el PDF a Drive: {e}")
    return result
