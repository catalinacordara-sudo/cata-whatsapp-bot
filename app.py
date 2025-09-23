import os
import re
from datetime import datetime, timezone

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client

# ─────────────────────────────
# Configuración
# ─────────────────────────────
app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_KEY en variables de entorno.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Helpers
def norm(s: str) -> str:
    """Normaliza texto para matching de comandos."""
    return (s or "").strip()

def list_to_bullets(rows, field="texto", titulo="Tus notas"):
    if not rows:
        return "🗒️ Aún sin notas."
    return "🗒️ " + titulo + ":\n" + "\n".join([f"{i+1}. {r[field]}" for i, r in enumerate(rows)])

HELP_TEXT = (
    "👋 *Comandos disponibles*\n"
    "nota <texto> — guarda una nota\n"
    "listar notas — ver notas\n"
    "borrar nota N — elimina por número\n"
    "editar nota N: <nuevo texto> — edita por número\n"
    "\n"
    "recordatorio <texto> — guarda un recordatorio\n"
    "listar recordatorios — ver recordatorios\n"
    "borrar recordatorio N — elimina por número\n"
    "editar recordatorio N: <nuevo texto> — edita por número\n"
)

# ─────────────────────────────
# Rutas
# ─────────────────────────────
@app.route("/", methods=["GET"])
def root():
    # Página de vida sencilla
    return "Echo debug: ping"

@app.route("/webhook", methods=["POST"])
def webhook():
    resp = MessagingResponse()

    try:
        incoming = request.values.get("Body", "") or ""
        text = norm(incoming).lower()
        wa_from = request.values.get("From", "") or ""
        # ID de usuario por WhatsApp (suficiente para separar tus datos)
        wa_id = wa_from.replace("whatsapp:", "").strip()

        # === AYUDA / MENÚ ===
        if text in ("ayuda", "help", "menu"):
            resp.message(HELP_TEXT)
            return str(resp), 200

        # =========================
        #        NOTAS
        # =========================
        # Guardar nota
        if text.startswith("nota "):
            contenido = norm(incoming[5:])
            if not contenido:
                resp.message("⚠️ Escribe algo después de *nota*.")
                return str(resp), 200

            supabase.table("notas").insert({"user_id": wa_id, "texto": contenido}).execute()
            resp.message(f"✅ Nota guardada: {contenido}")
            return str(resp), 200

        # Listar notas
        if text in ("listar notas", "listar nota"):
            res = (
                supabase.table("notas")
                .select("id, texto")
                .eq("user_id", wa_id)
                .order("created_at")
                .execute()
            )
            rows = res.data or []
            resp.message(list_to_bullets(rows, "texto", "Tus notas"))
            return str(resp), 200

        # Borrar nota N
        if text.startswith("borrar nota"):
            n_str = norm(text.replace("borrar nota", "", 1))
            if not n_str.isdigit():
                resp.message("❌ Formato: *borrar nota N* (ej: borrar nota 2)")
                return str(resp), 200

            res = (
                supabase.table("notas")
                .select("id")
                .eq("user_id", wa_id)
                .order("created_at")
                .execute()
            )
            rows = res.data or []
            n = int(n_str)
            if n < 1 or n > len(rows):
                resp.message("❌ Ese número de nota no existe.")
                return str(resp), 200

            note_id = rows[n - 1]["id"]
            supabase.table("notas").delete().eq("id", note_id).execute()
            resp.message(f"🗑️ Nota {n} borrada.")
            return str(resp), 200

        # Editar nota N: nuevo texto
        if text.startswith("editar nota"):
            resto = norm(incoming[len("editar nota") :])
            partes = resto.split(":", 1)
            if len(partes) != 2:
                resp.message("❌ Formato: *editar nota N: nuevo texto*")
                return str(resp), 200

            n_str, nuevo = norm(partes[0]), norm(partes[1])
            if not n_str.isdigit() or not nuevo:
                resp.message("❌ Formato: *editar nota N: nuevo texto*")
                return str(resp), 200

            res = (
                supabase.table("notas")
                .select("id")
                .eq("user_id", wa_id)
                .order("created_at")
                .execute()
            )
            rows = res.data or []
            n = int(n_str)
            if n < 1 or n > len(rows):
                resp.message("❌ Ese número de nota no existe.")
                return str(resp), 200

            note_id = rows[n - 1]["id"]
            supabase.table("notas").update({"texto": nuevo}).eq("id", note_id).execute()
            resp.message(f"✍️ Nota {n} editada: {nuevo}")
            return str(resp), 200

        # =========================
        #     RECORDATORIOS
        # =========================
        # Guardar recordatorio
        if text.startswith("recordatorio "):
            contenido = norm(incoming[len("recordatorio "):])
            if not contenido:
                resp.message("⚠️ Escribe algo después de *recordatorio*.")
                return str(resp), 200

            supabase.table("recordatorios").insert({"user_id": wa_id, "texto": contenido}).execute()
            resp.message(f"⏰ Recordatorio guardado: {contenido}")
            return str(resp), 200

        # Listar recordatorios
        if text in ("listar recordatorios", "listar recordatorio"):
            res = (
                supabase.table("recordatorios")
                .select("id, texto")
                .eq("user_id", wa_id)
                .order("created_at")
                .execute()
            )
            rows = res.data or []
            if not rows:
                resp.message("⏰ Aún sin recordatorios.")
            else:
                lista = "\n".join([f"{i+1}. {r['texto']}" for i, r in enumerate(rows)])
                resp.message("⏰ Tus recordatorios:\n" + lista)
            return str(resp), 200

        # Borrar recordatorio N
        if text.startswith("borrar recordatorio"):
            n_str = norm(text.replace("borrar recordatorio", "", 1))
            if not n_str.isdigit():
                resp.message("❌ Formato: *borrar recordatorio N* (ej: borrar recordatorio 2)")
                return str(resp), 200

            res = (
                supabase.table("recordatorios")
                .select("id")
                .eq("user_id", wa_id)
                .order("created_at")
                .execute()
            )
            rows = res.data or []
            n = int(n_str)
            if n < 1 or n > len(rows):
                resp.message("❌ Ese número de recordatorio no existe.")
                return str(resp), 200

            rec_id = rows[n - 1]["id"]
            supabase.table("recordatorios").delete().eq("id", rec_id).execute()
            resp.message(f"🗑️ Recordatorio {n} borrado.")
            return str(resp), 200

        # Editar recordatorio N: nuevo texto
        if text.startswith("editar recordatorio"):
            resto = norm(incoming[len("editar recordatorio") :])
            partes = resto.split(":", 1)
            if len(partes) != 2:
                resp.message("❌ Formato: *editar recordatorio N: nuevo texto*")
                return str(resp), 200

            n_str, nuevo = norm(partes[0]), norm(partes[1])
            if not n_str.isdigit() or not nuevo:
                resp.message("❌ Formato: *editar recordatorio N: nuevo texto*")
                return str(resp), 200

            res = (
                supabase.table("recordatorios")
                .select("id")
                .eq("user_id", wa_id)
                .order("created_at")
                .execute()
            )
            rows = res.data or []
            n = int(n_str)
            if n < 1 or n > len(rows):
                resp.message("❌ Ese número de recordatorio no existe.")
                return str(resp), 200

            rec_id = rows[n - 1]["id"]
            supabase.table("recordatorios").update({"texto": nuevo}).eq("id", rec_id).execute()
            resp.message(f"✍️ Recordatorio {n} editado: {nuevo}")
            return str(resp), 200

        # Default
        resp.message("No te entendí. Escribe *ayuda* para ver comandos.")
        return str(resp), 200

    except Exception as e:
        print("⚠️ Error en webhook:", e)
        resp.message("⚠️ Error interno")
        return str(resp), 200


if __name__ == "__main__":
    # Útil para pruebas locales (Render usa Gunicorn/Procfile)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
