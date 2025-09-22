import os
import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client

app = Flask(__name__)

# 🔑 Variables de entorno (Render)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Eres el asistente personal de Cata.")

# 🔌 Cliente Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- Webhook de WhatsApp ----------
@app.route("/webhook", methods=["POST"])
def webhook():
    # raw_msg conserva mayúsculas; incoming_msg es para detectar comandos (minúsculas)
    raw_msg = request.values.get("Body", "").strip()
    incoming_msg = raw_msg.lower()

    reply = ""

    # --------- NOTAS ----------
    if incoming_msg.startswith("nota "):
        # ejemplo: "nota Comprar bolsas"
        contenido = raw_msg[5:].strip()
        if contenido:
            supabase.table("notas").insert({"texto": contenido}).execute()
            reply = f"✅ Nota guardada: {contenido}"
        else:
            reply = "⚠️ No escribiste nada después de 'nota'."

    elif incoming_msg == "listar notas":
        res = supabase.table("notas").select("*").order("created_at", desc=False).execute()
        if res.data:
            notas = [f"{i+1}. {n['texto']}" for i, n in enumerate(res.data)]
            reply = "📝 Tus notas:\n" + "\n".join(notas)
        else:
            reply = "No tienes notas todavía."

    elif (incoming_msg.startswith("borrar nota")
          or incoming_msg.startswith("eliminar nota")
          or incoming_msg.startswith("quitar nota")):
        try:
            # Quita el prefijo detectado y toma el número
            idx_str = incoming_msg
            for p in ["borrar nota", "eliminar nota", "quitar nota"]:
                if idx_str.startswith(p):
                    idx_str = idx_str[len(p):]
                    break
            idx = int(idx_str.strip()) - 1

            # Busca el id real por posición (orden cronológico)
            res = supabase.table("notas").select("id").order("created_at", desc=False).execute()
            if 0 <= idx < len(res.data):
                note_id = res.data[idx]["id"]
                supabase.table("notas").delete().eq("id", note_id).execute()
                reply = f"🗑️ Nota {idx+1} borrada."
            else:
                reply = "❌ No existe esa nota."
        except Exception:
            reply = "Formato: 'borrar nota 2'"

    # --------- FALLBACK IA ----------
    else:
        try:
            reply = call_openai(raw_msg)
        except Exception as e:
            print("OpenAI error:", e, flush=True)
            reply = "Ups, tuve un problema generando la respuesta."

    # Enviar SIEMPRE lo que quedó en reply
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp), 200


# ---------- Función para llamar a OpenAI (fallback) ----------
def call_openai(user_text: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        "max_tokens": 500,
        "temperature": 0.7,
    }
    r = requests.post(url, json=data, headers=headers, timeout=45)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
