import os
import re
from datetime import datetime, timezone

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client

# ------------------------
# Config & Clients
# ------------------------
app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Falta SUPABASE_URL o SUPABASE_KEY en variables de entorno.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Utilidad: normalizar texto (para matching de comandos)
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

# Extraer etiquetas tipo #compras #casa
def extract_tags(text: str) -> list[str]:
    return list({t[1:].lower() for t in re.findall(r"#\w+", text or "")})

HELP_TEXT = (
    "👋 *Comandos disponibles*\n"
    "• *nota <texto>* — guarda una nota (puedes incluir #etiquetas)\n"
    "• *listar notas* — ver todas (no archivadas)\n"
    "• *listar #etiqueta* — ver por etiqueta\n"
    "• *buscar [texto]* — buscar en tus notas\n"
    "• *editar nota N: <nuevo texto>* — edita por número\n"
    "• *borrar nota N* — elimina\n"
    "• *archivar nota N* / *desarchivar nota N*\n"
    "• *stats* — conteos\n"
    "• *ayuda* — muestra este menú\n"
)

# ------------------------
# Helpers de BD
# Tabla recomendada:
# CREATE TABLE IF NOT EXISTS public.notas (
#   id bigserial PRIMARY KEY,
#   wa_id text NOT NULL,
#   texto text NOT NULL,
#   tags text[] DEFAULT '{}',
#   archived boolean DEFAULT false,
#   created_at timestamptz DEFAULT now()
# );
# CREATE INDEX IF NOT EXISTS notas_wa_id_created_idx ON public.notas(wa_id, created_at);
# CREATE INDEX IF NOT EXISTS notas_tags_gin ON public.notas USING GIN (tags);
# CREATE INDEX IF NOT EXISTS notas_texto_trgm ON public.notas USING GIN (texto gin_trgm_ops);
# (Para el índice trgm: habilita extensión pg_trgm en Supabase SQL Editor: CREATE EXTENSION IF NOT EXISTS pg_trgm;)
# ------------------------

def list_notes(wa_id: str, only_active: bool = True):
    q = supabase.table("notas").select("*").eq("wa_id", wa_id).order("created_at", desc=False)
    if only_active:
        q = q.eq("archived", False)
    return q.execute().data or []

def list_notes_by_tag(wa_id: str, tag: str):
    # tags ? 'tag' (contiene) – Supabase REST usa filter en PostgREST:
    # usamos 'contains' con array
    return (
        supabase.table("notas")
        .select("*")
        .eq("wa_id", wa_id)
        .eq("archived", False)
        .contains("tags", [tag.lower()])
        .order("created_at", desc=False)
        .execute()
        .data
        or []
    )

def search_notes(wa_id: str, query: str):
    # Búsqueda simple con ilike
    return (
        supabase.table("notas")
        .select("*")
        .eq("wa_id", wa_id)
        .eq("archived", False)
        .ilike("texto", f"%{query}%")
        .order("created_at", desc=False)
        .execute()
        .data
        or []
    )

def insert_note(wa_id: str, texto: str):
    tags = extract_tags(texto)
    return (
        supabase.table("notas")
        .insert({"wa_id": wa_id, "texto": texto, "tags": tags})
        .execute()
        .data
    )

def update_note_text_by_index(wa_id: str, index_1_based: int, new_text: str):
    data = list_notes(wa_id, only_active=True)
    if not data or index_1_based < 1 or index_1_based > len(data):
        return None, "No existe esa nota."
    row = data[index_1_based - 1]
    tags = extract_tags(new_text)
    res = (
        supabase.table("notas")
        .update({"texto": new_text, "tags": tags})
        .eq("id", row["id"])
        .execute()
        .data
    )
    return res, None

def delete_note_by_index(wa_id: str, index_1_based: int):
    data = list_notes(wa_id, only_active=True)
    if not data or index_1_based < 1 or index_1_based > len(data):
        return None, "No existe esa nota."
    row = data[index_1_based - 1]
    supabase.table("notas").delete().eq("id", row["id"]).execute()
    return True, None

def set_archived_by_index(wa_id: str, index_1_based: int, archived: bool):
    data = list_notes(wa_id, only_active=not archived)  # si voy a archivar, miro activas; si desarchivar, miro archivadas
    if archived:
        data = list_notes(wa_id, only_active=True)
    else:
        # Para desarchivar, listar archivadas
        data = (
            supabase.table("notas")
            .select("*")
            .eq("wa_id", wa_id)
            .eq("archived", True)
            .order("created_at", desc=False)
            .execute()
            .data
            or []
        )
    if not data or index_1_based < 1 or index_1_based > len(data):
        return None, "No existe esa nota."
    row = data[index_1_based - 1]
    supabase.table("notas").update({"archived": archived}).eq("id", row["id"]).execute()
    return True, None

def format_notes(data):
    if not data:
        return "No tienes notas todavía."
    lines = [f"{i+1}. {row['texto']}" for i, row in enumerate(data)]
    return "\n".join(lines)

# ------------------------
# Webhook Twilio
# ------------------------
@app.route("/", methods=["GET"])
def root():
    # Página de vida simple
    return "Echo debug: ping"

@app.route("/webhook", methods=["POST"])
def webhook():
    from twilio.twiml.messaging_response import MessagingResponse
    resp = MessagingResponse()
    try:
        incoming = request.values.get("Body", "").strip().lower()
        print("Mensaje entrante:", incoming)

        if incoming == "ayuda":
            resp.message("👋 Comandos disponibles:\n- nota <texto>\n- listar notas")
        elif incoming.startswith("nota "):
            texto = incoming.replace("nota ", "").strip()
            # guardar nota en Supabase
            supabase.table("notas").insert({"texto": texto}).execute()
            resp.message(f"✅ Nota guardada: {texto}")
        elif incoming.startswith("listar notas"):
            data = supabase.table("notas").select("*").order("id").execute()
            rows = data.data
            if not rows:
                resp.message("📒 No tienes notas todavía.")
            else:
                msg = "📒 Tus notas:\n"
                for r in rows:
                    msg += f"{r['id']}. {r['texto']}\n"
                resp.message(msg)
        else:
            resp.message("Hola 👋. Escribe 'ayuda' para ver comandos.")

    except Exception as e:
        print("❌ Error en webhook:", e)
        resp.message(f"⚠️ Error interno: {e}")

    return str(resp), 200


    # --------- Comandos ----------
    if mlow in ["ayuda", "help", "menu"]:
        reply = HELP_TEXT

    elif mlow.startswith("nota "):
        contenido = msg[5:].strip()
        if not contenido:
            reply = "⚠️ Escribe algo después de 'nota'."
        else:
            insert_note(wa_id, contenido)
            reply = f"✅ Nota guardada: {contenido}"

    elif mlow == "listar notas":
        data = list_notes(wa_id, only_active=True)
        reply = format_notes(data)

    elif mlow.startswith("listar #"):
        tag = mlow.replace("listar", "", 1).strip()
        tag = tag.lstrip("#").strip()
        if not tag:
            reply = "⚠️ Debes indicar una etiqueta, ej: *listar #casa*"
        else:
            data = list_notes_by_tag(wa_id, tag)
            reply = format_notes(data)

    elif mlow.startswith("buscar "):
        q = msg[7:].strip()
        if not q:
            reply = "⚠️ Usa: *buscar texto*"
        else:
            data = search_notes(wa_id, q)
            if not data:
                reply = "Sin coincidencias."
            else:
                reply = "Coincidencias:\n" + format_notes(data)

    elif mlow.startswith("borrar nota "):
        # borrar nota N
        idx_str = mlow.replace("borrar nota", "", 1).strip()
        try:
            n = int(idx_str)
            ok, err = delete_note_by_index(wa_id, n)
            reply = "🗑️ Nota borrada." if ok else f"⚠️ {err}"
        except Exception:
            reply = "⚠️ Formato: *borrar nota 2*"

    elif mlow.startswith("editar nota "):
        # editar nota N: nuevo texto
        m = re.match(r"editar nota\s+(\d+)\s*:\s*(.+)$", msg, flags=re.IGNORECASE)
        if not m:
            reply = "⚠️ Formato: *editar nota 2: nuevo texto*"
        else:
            n = int(m.group(1))
            new_text = m.group(2).strip()
            res, err = update_note_text_by_index(wa_id, n, new_text)
            reply = "✏️ Nota actualizada." if not err else f"⚠️ {err}"

    elif mlow.startswith("archivar nota "):
        idx_str = mlow.replace("archivar nota", "", 1).strip()
        try:
            n = int(idx_str)
            ok, err = set_archived_by_index(wa_id, n, archived=True)
            reply = "📦 Nota archivada." if ok else f"⚠️ {err}"
        except Exception:
            reply = "⚠️ Formato: *archivar nota 1*"

    elif mlow.startswith("desarchivar nota "):
        idx_str = mlow.replace("desarchivar nota", "", 1).strip()
        try:
            n = int(idx_str)
            ok, err = set_archived_by_index(wa_id, n, archived=False)
            reply = "🗃️ Nota desarchivada." if ok else f"⚠️ {err}"
        except Exception:
            reply = "⚠️ Formato: *desarchivar nota 1*"

    elif mlow == "stats":
        total = supabase.table("notas").select("id", count="exact").eq("wa_id", wa_id).execute().count or 0
        activas = (
            supabase.table("notas")
            .select("id", count="exact")
            .eq("wa_id", wa_id)
            .eq("archived", False)
            .execute()
            .count
            or 0
        )
        reply = f"📊 Total: {total}\n🟢 Activas: {activas}\n📦 Archivadas: {total - activas}"

    elif mlow in ["hola", "hi", "hey"]:
        reply = "Hola 👋. Escribe *ayuda* para ver comandos."

    else:
        reply = "No te entendí. Escribe *ayuda* para ver comandos."

    resp.message(reply)
    return str(resp), 200


# ------------------------
# Gunicorn entrypoint (Render)
# ------------------------
if __name__ == "__main__":
    # Útil para correr local (no en Render)
    app.run(host="0.0.0.0", port=5000)
