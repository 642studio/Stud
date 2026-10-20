# Estud

Estud es una plataforma personal de gestión académica: se conecta a la plataforma escolar del
alumno (por ahora, iVirtual/Moodle de ITSON), extrae automáticamente sus tareas y actividades,
las resume y clasifica con IA, y ofrece un espacio de trabajo para resolverlas — desde armar la
portada hasta generar el PDF final listo para subir a Drive.

Pensado para escalar a otras universidades y otros usuarios sin tocar código: las credenciales
de la plataforma, el logo institucional y los datos de portada se configuran desde la app
(**Perfil**), no están hardcodeados.

## Qué hace

- **Sincroniza** tareas y eventos desde iVirtual (Moodle) usando el mismo endpoint interno que
  alimenta el "Línea de tiempo" del dashboard de Moodle — sin necesitar un navegador headless.
- **Resume y clasifica** cada tarea con IA: convierte títulos crípticos de Moodle en frases
  claras y les asigna un tipo (tarea, examen, proyecto, cuaderno, lectura, foro, práctica, otro).
- **Lee el material real**: descarga y extrae texto de adjuntos de Moodle, Google Docs y
  archivos PDF en Google Drive (no solo el link), y con eso arma una checklist de pasos
  concretos para cada tarea.
- **Portada**: plantilla reusable (nombre, matrícula, universidad, carrera, logo, profesor por
  materia) que se autocompleta en cada tarea.
- **Asistente de investigación**: chat por tarea con búsqueda web (vía la Responses API de
  OpenAI), con el material de la tarea como contexto.
- **Escritorio**: espacio de trabajo por tarea pensado como asistente de punta a punta — ves el
  resumen y lo que se pide, marcas el checklist, le pides al agente que redacte o te revise el
  avance (sin que la IA "apruebe" nada, solo sugiere), generas el PDF (portada + contenido) y lo
  subes directo a Google Drive con un click. Ver [`docs/ESCRITORIO_AGENTE.md`](docs/ESCRITORIO_AGENTE.md)
  para el estado detallado de esta función (parcialmente en progreso).
- **Google Drive**: conexión OAuth (restringible a un dominio institucional), con un visor de
  archivos completo (navegar carpetas, subir, crear carpetas, buscar, mover a la papelera).
- **Dashboard**: resumen a simple vista, filtros por materia/fecha/tipo, tags visuales.

## Arquitectura

```
Estud/
├── backend/            FastAPI + SQLite (API, scraping, IA, Drive, PDF)
│   ├── main.py          Rutas de la API
│   ├── db.py             Acceso a SQLite (estud.db)
│   ├── sync.py            Orquesta la sincronización con iVirtual
│   ├── moodle_client.py    Sesión de Moodle persistente entre requests
│   ├── summarize.py         Resumen + clasificación (tag) por tarea
│   ├── analyze.py            Checklist generada desde el material real
│   ├── doc_extract.py         Descarga/extrae texto (Drive, Docs, PDFs, adjuntos)
│   ├── chat.py                 Asistente de investigación (chat + web search + redacción)
│   ├── draft.py                 Redacción asistida de una sola instrucción (endpoint viejo)
│   ├── review.py                 Revisa el documento contra el checklist (sugerencia, no gate)
│   ├── pdf_builder.py              Genera el PDF (portada + contenido)
│   └── drive.py                     OAuth y operaciones de Google Drive
├── scraper/            Cliente de scraping de iVirtual (Moodle), reusable fuera del backend
│   └── itson_moodle.py
├── frontend/            React + Vite
│   └── src/
│       ├── App.jsx           Shell: sidebar + routing + estado de tareas
│       ├── Dashboard.jsx       Resumen, filtros, tarjetas de tareas
│       ├── TaskDetail.jsx       Modal de tarea: detalle / portada / asistente IA
│       ├── Workbench.jsx         Escritorio: resumen + portada + editor + IA + PDF/Drive
│       ├── Drive.jsx              Conexión y visor de Google Drive
│       ├── Profile.jsx             Perfil: cuenta, portada, logo
│       └── taskUtils.js              Constantes y helpers compartidos
├── docs/
│   └── ESCRITORIO_AGENTE.md   Plan y estado de "Escritorio como agente completo" (en progreso)
├── requirements.txt     Dependencias Python (backend)
└── estud.db             SQLite local (no se versiona — contiene credenciales)
```

El backend mantiene una sesión de Moodle autenticada en memoria (re-login automático si expira)
y persiste todo en una única base SQLite local: tareas, resúmenes, checklists, chat,
credenciales (de iVirtual y de Google), configuración de portada, y los documentos que se
redactan en el Escritorio.

### Modelo de datos (`estud.db`, ver `backend/db.py`)

| Tabla | Para qué |
|---|---|
| `tasks` | Una fila por tarea sincronizada: título/resumen/tag, `detail_json` (descripción+adjuntos+estado), `checklist_json`, `material_text` (texto real extraído de PDFs/Docs/adjuntos), `completed` |
| `settings` | Fila única: datos de portada (nombre, matrícula, universidad, carrera, logo) |
| `platform_credentials` | Credenciales de iVirtual por plataforma (hoy solo `itson_moodle`), editables desde Perfil |
| `google_oauth` | Fila única: Client ID/Secret de Google, dominio permitido, refresh token, email conectado |
| `course_professors` | Profesor guardado por materia, para la portada |
| `chat_messages` | Historial del chat/asistente, por `task_id` |
| `drive_links` | Archivos subidos a Drive desde una tarea (nombre + URL) |
| `task_documents` | El contenido que el alumno redacta por tarea en el Escritorio |

### API (`backend/main.py`)

Agrupada por área; todas devuelven JSON salvo donde se indica.

- **Tareas**: `GET/POST /api/tasks`, `.../complete`, `.../detail`, `.../analyze`,
  `.../checklist/toggle`, `DELETE /api/tasks` (borra todo, usado al cambiar de cuenta)
- **Sync e IA**: `POST /api/sync`, `POST /api/summarize`
- **Escritorio**: `GET/PUT /api/tasks/{id}/document`, `POST .../document/draft` (instrucción
  suelta), `POST .../document/review` (sugerencias vs. checklist), `GET .../document/pdf`
  (PDF inline), `POST .../document/upload-drive`
- **Asistente/chat**: `GET/POST /api/tasks/{id}/chat`
- **Portada**: `GET /api/tasks/{id}/portada`, `POST .../portada/professor`
- **Perfil**: `GET/PUT /api/profile`, `GET/PUT /api/settings`, `POST /api/settings/logo`,
  `GET/PUT /api/settings/platform`
- **Drive**: `GET /api/drive/status`, `PUT /api/settings/google`, `GET /api/drive/auth/start`,
  `GET /api/drive/callback`, `POST /api/drive/disconnect`, `GET /api/drive/files`,
  `POST /api/drive/files/upload`, `POST /api/drive/folders`, `DELETE /api/drive/files/{id}`,
  y las versiones por tarea `GET/POST /api/tasks/{id}/drive`

## Requisitos

- Python 3.9+
- Node.js 18+
- Una cuenta de iVirtual (Moodle) — matrícula y contraseña
- Una API key de OpenAI (resúmenes, checklist, chat, redacción)
- (Opcional) Credenciales OAuth de Google Cloud, solo si vas a usar Drive

## Instalación

```bash
git clone https://github.com/642studio/Stud.git
cd Stud

# Backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# Frontend
cd frontend
npm install
cd ..
```

Copia `.env.example` a `.env` y completa al menos `OPENAI_API_KEY`. Las credenciales de iVirtual
también se pueden dejar en blanco aquí y configurarse después desde **Perfil** en la app (tienen
prioridad sobre el `.env`).

```bash
cp .env.example .env
```

## Correrlo

```bash
# Backend (puerto 8000)
./.venv/bin/uvicorn backend.main:app --port 8000

# Frontend (puerto 5173), en otra terminal
cd frontend && npm run dev
```

Abre `http://localhost:5173`. La primera vez, ve a **Perfil** para:
1. Configurar tu cuenta de iVirtual (si no la pusiste en `.env`).
2. Completar tus datos de portada (nombre, matrícula, universidad, carrera) y subir el logo de
   tu institución.

Luego dale "Sincronizar iVirtual" en el Dashboard.

## Conectar Google Drive (opcional)

Drive requiere un cliente OAuth propio de Google Cloud — no viene configurado por defecto:

1. En [Google Cloud Console](https://console.cloud.google.com), crea o usa un proyecto y
   habilita la **Google Drive API**.
2. Configura la **Pantalla de consentimiento de OAuth** con tipo de usuario **Externo** (si el
   proyecto pertenece a una organización de Workspace, puede forzar "Interno" y bloquear cuentas
   de otro dominio — en ese caso hay que cambiarlo o usar un proyecto personal). En modo
   "Prueba", agrega tu correo como usuario de prueba.
3. Crea una credencial OAuth tipo **Aplicación web**, con
   `http://localhost:8000/api/drive/callback` como URI de redirección autorizada.
4. Copia el **Client ID** y **Client Secret** y pégalos en la pantalla **Drive** de Estud (ahí
   mismo puedes restringir el acceso a un dominio institucional, ej. `itson.edu.mx`).
5. Click en "Conectar con Google".

El scope solicitado es acceso completo a Drive (`drive`), necesario para poder navegar y
administrar archivos existentes, no solo los que la app crea.

## Notas de seguridad

- `estud.db` guarda en texto plano la contraseña de iVirtual y el Client Secret/refresh token de
  Google — está en `.gitignore`, nunca debe commitearse.
- `.env` y la carpeta `uploads/` (logos subidos) tampoco se versionan.
- La app está pensada para uso local/personal (un usuario por instancia); no implementa
  autenticación propia ni multi-tenancy.

## Estado / límites conocidos

- El scraper (`scraper/itson_moodle.py`) está hecho para el Moodle de ITSON específicamente,
  pero su diseño (login + endpoint AJAX del dashboard) es reusable para cualquier Moodle
  estándar cambiando la URL base.
- La extracción de material (`doc_extract.py`) cubre Google Docs, archivos en Google Drive y
  adjuntos nativos de Moodle; no cubre todavía otros proveedores (OneDrive, Dropbox, etc.).
- Un solo documento por tarea en el Escritorio (no hay versiones ni historial de redacción).
- "Escritorio como agente completo" está **en progreso** — ver
  [`docs/ESCRITORIO_AGENTE.md`](docs/ESCRITORIO_AGENTE.md) para el detalle exacto de qué falta
  antes de seguir con cualquier otra cosa en esa pantalla.
