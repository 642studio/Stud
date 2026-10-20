"""Genera el PDF de una tarea: portada (logo + datos) y el contenido redactado."""
import io
import re
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer

DEFAULT_LOGO = Path(__file__).resolve().parent.parent / "frontend" / "public" / "itson-logo.png"
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"

MAX_LOGO_WIDTH = 2.6 * inch
MAX_LOGO_HEIGHT = 1.4 * inch


def _logo_image(logo_url):
    path = None
    if logo_url and logo_url.startswith("/uploads/"):
        candidate = UPLOADS_DIR / logo_url[len("/uploads/"):]
        if candidate.exists():
            path = candidate
    if path is None and DEFAULT_LOGO.exists():
        path = DEFAULT_LOGO
    if path is None:
        return None

    try:
        with PILImage.open(path) as im:
            w, h = im.size
    except Exception:
        return None

    ratio = min(MAX_LOGO_WIDTH / w, MAX_LOGO_HEIGHT / h)
    img = Image(str(path), width=w * ratio, height=h * ratio)
    img.hAlign = "CENTER"
    return img


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _markdown_lite(text: str) -> str:
    text = _escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    return text.replace("\n", "<br/>")


def build_pdf(portada: dict, content: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter, topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        leftMargin=1 * inch, rightMargin=1 * inch,
    )
    styles = getSampleStyleSheet()

    label_style = ParagraphStyle(
        "label", parent=styles["Normal"], alignment=TA_CENTER,
        fontName="Helvetica-Bold", fontSize=12, spaceAfter=2,
    )
    value_style = ParagraphStyle(
        "value", parent=styles["Normal"], alignment=TA_CENTER, fontSize=12, spaceAfter=18,
    )
    footer_style = ParagraphStyle(
        "footer", parent=styles["Normal"], alignment=TA_CENTER,
        fontSize=9, textColor="#9CA3AF",
    )
    title_style = ParagraphStyle(
        "doctitle", parent=styles["Heading2"], spaceAfter=14,
    )
    body_style = ParagraphStyle(
        "body", parent=styles["Normal"], fontSize=11, leading=16, spaceAfter=10,
    )

    story = []

    logo = _logo_image(portada.get("logo_url"))
    if logo:
        story.append(logo)
        story.append(Spacer(1, 30))

    fields = [
        ("Alumno", portada.get("full_name") or "—"),
        ("ID", portada.get("student_id") or "—"),
        ("Asignación", portada.get("title") or "—"),
        ("Fecha", portada.get("date") or "—"),
        ("Materia", portada.get("course") or "—"),
        ("Profesor", portada.get("professor") or "—"),
    ]
    for label, value in fields:
        story.append(Paragraph(f"{label}—", label_style))
        story.append(Paragraph(_escape(value), value_style))

    story.append(Spacer(1, 16))
    story.append(Paragraph((portada.get("university") or "").upper(), footer_style))

    story.append(PageBreak())
    story.append(Paragraph(_escape(portada.get("title") or "")[:120], title_style))

    if content and content.strip():
        for block in content.split("\n\n"):
            block = block.strip()
            if block:
                story.append(Paragraph(_markdown_lite(block), body_style))
    else:
        story.append(Paragraph("(sin contenido todavía)", body_style))

    doc.build(story)
    return buf.getvalue()
