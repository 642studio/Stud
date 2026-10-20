"""Descarga y extrae texto de materiales de una tarea: adjuntos de Moodle, Drive, Google Docs, PDFs directos."""
import io
import re
from typing import Optional

import requests
from pypdf import PdfReader

GOOGLE_DOC_RE = re.compile(r"docs\.google\.com/document/d/([a-zA-Z0-9_-]+)")
GOOGLE_DRIVE_RE = re.compile(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)")

MAX_CHARS_PER_DOC = 6000
MAX_PDF_PAGES = 30
TIMEOUT = 20


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    parts = [page.extract_text() or "" for page in reader.pages[:MAX_PDF_PAGES]]
    return "\n".join(parts)


def _looks_like_pdf(resp) -> bool:
    return "pdf" in resp.headers.get("content-type", "") or resp.content[:4] == b"%PDF"


def _text_from_response(resp) -> Optional[str]:
    """Interpreta una respuesta HTTP como PDF o texto plano, sin confiar solo en content-type
    (Google Drive sirve PDFs como application/octet-stream)."""
    if not resp.ok:
        return None
    if _looks_like_pdf(resp):
        return _extract_pdf_text(resp.content)[:MAX_CHARS_PER_DOC] or None
    ctype = resp.headers.get("content-type", "")
    if "text" in ctype:
        return resp.text[:MAX_CHARS_PER_DOC] or None
    return None


def extract_links(description_html: Optional[str]) -> list:
    if not description_html:
        return []
    return re.findall(r'href="([^"]+)"', description_html)


def fetch_text_from_url(url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """Intenta extraer texto legible de una URL de material: Google Docs, Drive, PDF o adjunto de Moodle."""
    s = session or requests.Session()
    try:
        m = GOOGLE_DOC_RE.search(url)
        if m:
            resp = s.get(f"https://docs.google.com/document/d/{m.group(1)}/export?format=txt", timeout=TIMEOUT)
            return _text_from_response(resp)

        m = GOOGLE_DRIVE_RE.search(url)
        if m:
            resp = s.get(f"https://drive.google.com/uc?export=download&id={m.group(1)}", timeout=TIMEOUT)
            return _text_from_response(resp)

        resp = s.get(url, timeout=TIMEOUT)
        return _text_from_response(resp)
    except Exception:
        return None
