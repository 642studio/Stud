"""Mantiene una sesión de Moodle (iVirtual) viva entre requests del backend."""
import os

from backend import db
from scraper.itson_moodle import MoodleSession

PLATFORM = "itson_moodle"

_session = None


def get_credentials():
    """Credenciales guardadas en la base de datos (editables en Perfil), con .env como respaldo."""
    creds = db.get_platform_credentials(PLATFORM)
    if creds and creds.get("username") and creds.get("password"):
        return creds["base_url"] or os.environ.get("ITSON_BASE_URL", ""), creds["username"], creds["password"]

    base_url = os.environ.get("ITSON_BASE_URL", "")
    username = os.environ.get("ITSON_USERNAME", "")
    password = os.environ.get("ITSON_PASSWORD", "")
    if not (base_url and username and password):
        raise RuntimeError("No hay credenciales de iVirtual configuradas. Agrégalas en Perfil.")
    return base_url, username, password


def get_itson_client() -> MoodleSession:
    global _session
    if _session is None:
        base_url, username, password = get_credentials()
        _session = MoodleSession(base_url, username, password)
        _session.login()
    return _session


def reset_client():
    """Fuerza un nuevo login la próxima vez que se use el cliente (tras cambiar credenciales)."""
    global _session
    _session = None
