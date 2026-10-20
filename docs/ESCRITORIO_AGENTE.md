# Escritorio como agente completo — estado y continuación

Objetivo del usuario (textual): *"el escritorio debe ser un asistente completo para que se arme
el pdf entregable (...) mediante el agente se pueda terminar el trabajo a punto de poder
aprobar y se suba"*.

Decisiones ya confirmadas con el usuario (no volver a preguntar):
- El agente **sugiere** qué puntos del checklist parecen cubiertos; **nunca los marca solo**.
- "Generar PDF y subir a Drive" **nunca se bloquea** por la revisión — es informativa, no un gate.
- El chat de investigación (antes solo en el modal del Dashboard) se **integra** al Escritorio,
  con botón para insertar sus respuestas directo al documento.

## Hecho (3 de 6)

1. **`backend/chat.py`** y **`backend/draft.py`** ya usan `task["material_text"]` (texto real
   extraído de PDFs/Docs/adjuntos por `backend/analyze.py`) como fuente principal de contexto,
   en vez de solo `detail["description_html"]` truncado (que casi siempre es solo un link).
   `chat.py::_system_prompt` también incluye ahora el contenido actual del documento
   (`db.get_document`) para que el chat sepa qué ya se escribió.
2. **`frontend/src/Workbench.jsx`**: el checklist de "Puntos a cubrir" ya es interactivo
   (`toggleChecklistItem`, mismo patrón que `TaskDetail.jsx`, llama
   `POST /api/tasks/{id}/checklist/toggle`), muestra un contador de progreso
   ("Puntos a cubrir — X de Y") y ya tiene el hueco para insignias de revisión por punto
   (`review-badge`, usando `review?.items`).
3. **`backend/review.py`** (nuevo) + endpoint **`POST /api/tasks/{id}/document/review`** en
   `backend/main.py`. Devuelve `{"items": [{"id", "covered", "note"}], "summary": "..."}`
   comparando el documento actual contra el checklist. `Workbench.jsx` ya tiene `runReview()`
   conectado a este endpoint y renderiza `review.summary` + las insignias por punto.

Backend verificado arrancando sin errores con estos tres cambios (no se probó en navegador
todavía más allá de eso).

## Pendiente (empezar aquí)

### 4. `ChatPanel.jsx` necesita las props `onInsert` y `quickActions`

`Workbench.jsx` **ya monta** `ChatPanel` así (sustituyendo la vieja caja de "Redactar con IA"
de una sola instrucción):

```jsx
<ChatPanel
  taskId={task.id}
  onInsert={insertIntoDocument}
  quickActions={[
    {
      label: "Redactar lo que falta",
      message:
        "Redacta un primer borrador que cubra los puntos del checklist que el " +
        "contenido actual todavía no cubre, en orden lógico.",
    },
  ]}
/>
```

Pero `frontend/src/ChatPanel.jsx` (usado también, sin estas props, dentro del modal
`TaskDetail.jsx` → pestaña "Asistente IA") solo acepta `{ taskId }` hoy. Como las props de más
simplemente se ignoran en React, **ahora mismo no truena nada, pero el botón de insertar y los
chips de acción rápida no aparecen**. Hay que extender `ChatPanel.jsx` (sin romper el uso en
`TaskDetail.jsx`, que seguirá llamándolo sin esas props — deben ser opcionales):

- Prop `onInsert?: (text: string) => void`: si viene, cada burbuja `role === "assistant"`
  muestra un botón pequeño "Insertar en el documento" debajo que llama
  `onInsert(m.content)` (hay que guardar los mensajes "crudos", no el HTML ya transformado por
  `renderMarkdownLite`, para no insertar HTML en el textarea del documento).
- Prop `quickActions?: {label, message}[]`: si viene, renderizar chips arriba del
  `<form className="chat-input-row">` que, al hacer click, hacen lo mismo que escribir
  `message` en el input y enviar (reusar la función `send`, quizás refactorizando su cuerpo a
  `sendMessage(text)` y que el `onSubmit` del form llame `sendMessage(input)`).
- Deshabilitar los chips mientras `sending` es true, igual que el input.

### 5. Bloques de código en el PDF y en el chat

Varias tareas reales (Estructuras de Datos, Programación III) piden código. Falta:
- `backend/pdf_builder.py`: la función que parte `content` en bloques (busca `_markdown_lite`
  y el loop que hace `content.split("\n\n")`) solo entiende `**negrita**`. Agregar detección de
  fences ` ```código``` ` y renderizarlos con `reportlab.platypus.Preformatted` + un
  `ParagraphStyle` con `fontName="Courier"` y `backColor` gris claro, en vez de `Paragraph`.
- `frontend/src/ChatPanel.jsx` (`renderMarkdownLite`): mismo tratamiento en pantalla — envolver
  el contenido de los fences en `<pre>` con fuente monoespaciada (puede compartirse con
  `Workbench`/editor si se quiere, pero no es obligatorio para v1).
- Los prompts de `chat.py` y `draft.py` **ya** le dicen al modelo que puede usar ` ``` ` para
  código (ya hecho en el paso 1) — solo falta que el render lo respete.

### 6. Probar todo el flujo en el navegador

Backend: `pkill -f "uvicorn backend.main:app"` y volver a levantarlo
(`./.venv/bin/uvicorn backend.main:app --port 8000`) después de cada cambio de backend.
Frontend: `preview_start` con el nombre `estud-frontend` (ya configurado en
`.claude/launch.json`).

Casos a cubrir:
1. Marcar/desmarcar un punto del checklist en el Escritorio y confirmar que persiste.
2. Usar el chat integrado: pedir "Redactar lo que falta" (chip), insertar la respuesta al
   documento, guardar.
3. "Revisar mi avance": confirmar que aparecen insignias por punto sin tocar los checkboxes, y
   que el resumen aparece cerca de "Dejar listo para subir".
4. Tarea con contenido que incluya un bloque ` ```código``` `: generar el PDF
   (`GET /api/tasks/{id}/document/pdf`) y confirmar que sale en fuente monoespaciada.
5. "Generar PDF y subir a Drive" sigue funcionando aunque la revisión marque puntos sin cubrir
   (no debe bloquear nunca).

## Nota suelta sin resolver

El usuario mencionó en algún punto que "hay que ajustar la navegación" (de Drive o general, no
se especificó el detalle) y quedó sin definir. Preguntar antes de asumir qué significa si se
retoma.
