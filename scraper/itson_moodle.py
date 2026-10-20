"""Scraper de iVirtual (Moodle) de ITSON: login + extracción de cursos y tareas próximas."""
import os
import re
import json
from datetime import datetime

import requests
from bs4 import BeautifulSoup


class MoodleSession:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.sesskey = None

    def login(self):
        login_url = f"{self.base_url}/login/index.php"
        resp = self.session.get(login_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        token_input = soup.find("input", {"name": "logintoken"})
        logintoken = token_input["value"] if token_input else ""

        resp = self.session.post(
            login_url,
            data={
                "username": self.username,
                "password": self.password,
                "logintoken": logintoken,
            },
        )

        if "login/index.php" in resp.url:
            soup = BeautifulSoup(resp.text, "html.parser")
            error = soup.find(id="loginerrormessage") or soup.find(class_="loginerrors")
            msg = error.get_text(strip=True) if error else "motivo desconocido"
            raise RuntimeError(f"No se pudo iniciar sesión en iVirtual: {msg}")

        self.sesskey = self._extract_sesskey(resp.text)
        return True

    @staticmethod
    def _extract_sesskey(html: str):
        m = re.search(r'"sesskey"\s*:\s*"([a-zA-Z0-9]+)"', html)
        if m:
            return m.group(1)
        m = re.search(r"sesskey=([a-zA-Z0-9]+)", html)
        return m.group(1) if m else None

    def get_dashboard_html(self) -> str:
        resp = self.session.get(f"{self.base_url}/my/")
        if not self.sesskey:
            self.sesskey = self._extract_sesskey(resp.text)
        return resp.text

    def get_page(self, url: str):
        """GET autenticado; si la sesión expiró, reloguea una vez y reintenta."""
        resp = self.session.get(url)
        if "login/index.php" in resp.url:
            self.login()
            resp = self.session.get(url)
        return resp

    def get_courses(self):
        html = self.get_dashboard_html()
        soup = BeautifulSoup(html, "html.parser")
        courses, seen = [], set()
        for link in soup.select('a[href*="/course/view.php?id="]'):
            href, name = link.get("href"), link.get_text(strip=True)
            if name and href and href not in seen:
                seen.add(href)
                courses.append({"name": name, "url": href})
        return courses

    def get_upcoming_events(self, limit: int = 50):
        """Reutiliza el endpoint AJAX que alimenta el bloque 'Línea de tiempo' del dashboard."""
        if not self.sesskey:
            self.get_dashboard_html()
        if not self.sesskey:
            raise RuntimeError("No se encontró sesskey; no se puede llamar al API interno de Moodle.")

        ajax_url = f"{self.base_url}/lib/ajax/service.php?sesskey={self.sesskey}&info=core_calendar_get_action_events_by_timesort"
        payload = [
            {
                "index": 0,
                "methodname": "core_calendar_get_action_events_by_timesort",
                "args": {"limitnum": limit, "timesortfrom": 0},
            }
        ]
        resp = self.session.post(ajax_url, json=payload)
        resp.raise_for_status()
        data = resp.json()

        if data and data[0].get("error"):
            raise RuntimeError(f"Moodle AJAX error: {data[0].get('exception')}")

        events = data[0]["data"]["events"] if data and "data" in data[0] else []
        tasks = []
        for ev in events:
            tasks.append(
                {
                    "id": ev.get("id"),
                    "course": (ev.get("course") or {}).get("fullname"),
                    "title": ev.get("name"),
                    "description_html": (ev.get("description") or None),
                    "due": datetime.fromtimestamp(ev["timesort"]).isoformat() if ev.get("timesort") else None,
                    "url": ev.get("url"),
                    "overdue": ev.get("overdue", False),
                    "modulename": ev.get("modulename"),
                }
            )
        return tasks

    def get_activity_detail(self, url: str) -> dict:
        """Trae la descripción completa, adjuntos y estado de entrega de una actividad."""
        resp = self.get_page(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup.select("script, style"):
            tag.decompose()

        desc_el = soup.select_one("div.activity-description") or soup.select_one(
            "div.box.generalbox.center, div.box.generalbox"
        )
        description_html = str(desc_el) if desc_el else None

        attachments, seen = [], set()
        for a in soup.select('a[href*="pluginfile.php"]'):
            href = a.get("href")
            if href and href not in seen:
                seen.add(href)
                name = a.get_text(strip=True) or href.rsplit("/", 1)[-1]
                attachments.append({"name": name, "url": href})

        status = {}
        status_table = soup.select_one("table.submissionstatustable")
        if status_table:
            for row in status_table.select("tr"):
                cells = row.select("th, td")
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    val = cells[-1].get_text(" ", strip=True)
                    if key and val and key != val and key not in status:
                        status[key] = val

        return {
            "description_html": description_html,
            "attachments": attachments,
            "status": status,
        }


def main():
    from dotenv import load_dotenv

    load_dotenv()
    base_url = os.environ["ITSON_BASE_URL"]
    username = os.environ["ITSON_USERNAME"]
    password = os.environ["ITSON_PASSWORD"]

    client = MoodleSession(base_url, username, password)
    client.login()
    print("Login OK\n")

    courses = client.get_courses()
    print(f"Cursos encontrados: {len(courses)}")
    for c in courses:
        print(f" - {c['name']}")

    tasks = client.get_upcoming_events()
    print(f"\nTareas/eventos próximos: {len(tasks)}")
    for t in tasks:
        print(f" - [{t['course']}] {t['title']} | vence: {t['due']} | overdue: {t['overdue']}")

    out_path = os.path.join(os.path.dirname(__file__), "..", "tasks_raw.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print(f"\nGuardado en {out_path}")


if __name__ == "__main__":
    main()
