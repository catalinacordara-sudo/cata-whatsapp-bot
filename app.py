import os
import re
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client

app = Flask(__name__)

# ====== ENV ======
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Eres el asistente personal de Cata, directo y cálido.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ====== Helpers ======
def norm(s: str) -> str:
    """minúsculas + espacios colapsados"""
    return re.sub(r"\s+", " ", s.strip().lower())

def call_openai(user_text: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "max_tokens": 500,
        "temperature": 0.7,
    }
    r = requests.post(url, json=data, headers=headers, timeout=45)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ====== Health ======
@app.route("/health", methods=["GET"])
def health():
    return "ok", 200

# ====== Webhook WA/Twilio ======
@app.route("/webhook", methods=["POST"])
def webhook():
    raw_msg = request.values.get("Body", "") or ""
    incoming = norm(raw_msg)

    # Respuesta por defecto (solo se usará si no hay comando de notas)
    reply = ""

    # ---------- NOTAS: AGREGAR ----------
    # acepta: "nota ...", "nota: ...", "nota, ...", "agregar nota ...", "añadir nota ..."
    nota_prefixes = ("nota ", "nota:", "nota,", "agregar nota ", "añadir nota ")
    if incoming.startswith(nota_prefixes):
        # Conserva mayúsculas del contenido usando raw_msg
        # Encuentra el primer espacio/colon/coma tras "nota"
        m = re.search(r"(?i)^(nota|agregar nota|añadir nota)\s*[: ,]?\s*(.*)$", raw_msg.strip())
        contenido = (m.group(2) if m and m.group(2) else "").strip()
        if contenido:
            supabase.table("notas").insert({"texto": contenido}).execute()
            reply = f"✅ Nota guardada: {contenido}"
        else:
            reply = "⚠️ Escribe algo después de ‘nota’. Ej: *nota Comprar bolsas*"

    # ---------- NOTAS: LISTAR ----------
    elif incoming in ("listar notas", "listar nota", "ver notas", "mostrar notas"):
        res = supabase.table("notas").select("*").order("created_at", desc=False).execute()
        if res.data:
            notas = [f"{i+1}. {n['texto']}" for i, n in enumerate(res.data)]
            reply = "📝 *Tus notas:*\n" + "\n".join(notas)
        else:
            reply = "No tienes notas todavía. Prueba con *nota Comprar bolsas*"

    # ---------- NOTAS: BORRAR ----------
    # acepta: borrar/eliminar/quitar nota 2   (con espacios/puntos/2 puntos)
    elif incoming.startswith(("borrar nota", "eliminar nota", "quitar nota")):
        try:
            # Extrae el número que venga en el mensaje
            m = re.search(r"(?:borrar|eliminar|quitar)\s+nota[^0-9]*([0-9]+)", incoming)
            if not m:
                raise ValueError("no-number")
            idx = int(m.group(1)) - 1

            res = supabase.table("notas").select("id").order("created_at", desc=False).execute()
            if 0 <= idx < len(res.data):
                note_id = res.data[idx]["id"]
                supabase.table("notas").delete().eq("id", note_id).execute()
                reply = f"🗑️ Nota {idx+1} borrada."
            else:
                reply = "❌ No existe esa nota."
        except Exception:
            reply = "Formato: *borrar nota 2* (usa el número que ves en *listar notas*)"

    # ---------- FALLBACK IA ----------
    else:
        try:
            reply = call_openai(raw_msg.strip())
        except Exception as e:
            print("OpenAI error:", e, flush=True)
            reply = "Ups, tuve un problema generando la respuesta."

    # Enviar SIEMPRE la respuesta a WhatsApp
    tw = MessagingResponse()
    tw.message(reply)
    return str(tw), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
