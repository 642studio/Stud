"""Conexión con Google Drive (OAuth) para subir archivos de tareas y obtener su enlace."""
import io
import os

# Google puede devolver, además del scope pedido, scopes ya otorgados antes
# (ej. el "drive.file" de una conexión previa) — por defecto oauthlib trata
# eso como error en vez de solo informarlo.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

import requests as http
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from backend import db

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]
REDIRECT_URI = "http://localhost:8000/api/drive/callback"
TOKEN_URI = "https://oauth2.googleapis.com/token"
AUTH_URI = "https://accounts.google.com/o/oauth2/auth"

# PKCE: el code_verifier generado al armar la URL de autorización debe
# reusarse en el callback (una instancia de Flow nueva no lo conoce).
# Un solo usuario/proceso backend, así que basta con guardarlo en memoria.
_pending_code_verifier = None


def _require_app_credentials():
    creds = db.get_google_oauth()
    if not creds or not creds.get("client_id") or not creds.get("client_secret"):
        raise RuntimeError("Falta configurar el Client ID y Client Secret de Google en Perfil.")
    return creds


def _flow(code_verifier: str = None) -> Flow:
    creds = _require_app_credentials()
    client_config = {
        "web": {
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI, code_verifier=code_verifier
    )


def get_auth_url() -> str:
    global _pending_code_verifier
    creds = _require_app_credentials()
    flow = _flow()
    kwargs = {"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true"}
    if creds.get("allowed_domain"):
        kwargs["hd"] = creds["allowed_domain"]
    url, _ = flow.authorization_url(**kwargs)
    _pending_code_verifier = flow.code_verifier
    return url


def handle_callback(code: str) -> dict:
    global _pending_code_verifier
    app_creds = _require_app_credentials()
    flow = _flow(code_verifier=_pending_code_verifier)
    flow.fetch_token(code=code)
    _pending_code_verifier = None
    credentials = flow.credentials

    resp = http.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
        timeout=15,
    )
    resp.raise_for_status()
    email = resp.json().get("email", "")

    allowed_domain = app_creds.get("allowed_domain")
    if allowed_domain and not email.lower().endswith(f"@{allowed_domain.lower()}"):
        raise RuntimeError(
            f"Esa cuenta ({email}) no pertenece al dominio institucional {allowed_domain}. "
            "Conéctate con tu correo institucional."
        )

    if not credentials.refresh_token:
        raise RuntimeError(
            "Google no entregó un refresh token (puede pasar si ya habías autorizado antes). "
            "Revoca el acceso en myaccount.google.com/permissions e intenta de nuevo."
        )

    db.set_google_tokens(credentials.refresh_token, email)
    return {"email": email}


def _get_service():
    app_creds = _require_app_credentials()
    oauth = db.get_google_oauth()
    if not oauth or not oauth.get("refresh_token"):
        raise RuntimeError("Google Drive no está conectado. Conéctalo en Perfil.")

    credentials = Credentials(
        token=None,
        refresh_token=oauth["refresh_token"],
        token_uri=TOKEN_URI,
        client_id=app_creds["client_id"],
        client_secret=app_creds["client_secret"],
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=credentials)


def upload_file(task_id: str, filename: str, content: bytes, mimetype: str, folder_id: str = None) -> dict:
    """task_id=None sube el archivo sin asociarlo a ninguna tarea (ej. desde el visor de Drive)."""
    service = _get_service()
    file_metadata = {"name": filename}
    if folder_id:
        file_metadata["parents"] = [folder_id]
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mimetype, resumable=False)
    created = service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()

    service.permissions().create(
        fileId=created["id"], body={"role": "reader", "type": "anyone"}
    ).execute()

    link = created["webViewLink"]
    if task_id:
        db.add_drive_link(task_id, filename, link)
    return {"name": filename, "url": link}


FILE_FIELDS = "id, name, mimeType, iconLink, webViewLink, modifiedTime, size, parents, trashed"
FOLDER_MIME = "application/vnd.google-apps.folder"


def list_files(folder_id: str = None, query: str = None):
    service = _get_service()
    if query:
        q = f"trashed = false and name contains '{query}'"
    else:
        parent = folder_id or "root"
        q = f"'{parent}' in parents and trashed = false"

    resp = (
        service.files()
        .list(
            q=q,
            fields=f"files({FILE_FIELDS})",
            orderBy="folder,modifiedTime desc",
            pageSize=200,
        )
        .execute()
    )
    files = resp.get("files", [])
    for f in files:
        f["isFolder"] = f.get("mimeType") == FOLDER_MIME
    return files


def get_file_path(folder_id: str):
    """Breadcrumb: lista de {id, name} desde la raíz hasta folder_id."""
    if not folder_id or folder_id == "root":
        return []
    service = _get_service()
    path = []
    current = folder_id
    for _ in range(20):
        meta = service.files().get(fileId=current, fields="id, name, parents").execute()
        path.insert(0, {"id": meta["id"], "name": meta["name"]})
        parents = meta.get("parents")
        if not parents or parents[0] == "root":
            break
        current = parents[0]
    return path


def create_folder(name: str, parent_id: str = None) -> dict:
    service = _get_service()
    metadata = {"name": name, "mimeType": FOLDER_MIME}
    if parent_id:
        metadata["parents"] = [parent_id]
    created = service.files().create(body=metadata, fields=FILE_FIELDS).execute()
    created["isFolder"] = True
    return created


def trash_file(file_id: str):
    service = _get_service()
    service.files().update(fileId=file_id, body={"trashed": True}).execute()
