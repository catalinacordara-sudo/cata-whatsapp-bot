from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests
import os

app = Flask(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT", "Eres el asistente personal de Catalina (Cata).")

@app.route("/health", methods=["GET"])
def health():
    return "ok", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip().lower()
    resp = MessagingResponse()
    reply = ""

    if incoming_msg.startswith("nota "):
        contenido = incoming_msg.replace("nota ", "", 1).strip()
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

    elif incoming_msg.startswith("borrar nota "):
        try:
            idx = int(
                incoming_msg.replace("borrar nota ", "")
                                  .replace("eliminar nota","")
                                  .replace("quitar nota,"")
                                  .strip()
            ) - 1
            res = supabase.table("notas").select("id").order("created_at", desc=False).execute()
            if 0 <= idx < len(res.data):
                note_id = res.data[idx]["id"]
                supabase.table("notas").delete().eq("id", note_id).execute()
                reply = f"🗑️ Nota {idx+1} borrada."
            else:
                reply = "No existe esa nota."
        except:
            reply = "Formato: 'borrar nota 2'"

    else:
        reply = "👋 Hola, soy tu Catabot.\nPuedes usar:\n- 'nota <texto>' para guardar\n- 'listar notas' para verlas\n- 'borrar nota <número>' para borrar"

    try:
        reply_text = call_openai(incoming_msg)
    except Exception as e:
        print("OpenAI error:", e, flush=True)
        reply_text = "Ups, hubo un error al generar la respuesta. Intenta de nuevo más tarde."

    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp), 200

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
        "max_tokens": 500
    }
    r = requests.post(url, json=data, headers=headers, timeout=45)
    if r.status_code != 200:
        print("OpenAI error:", r.status_code, r.text, flush=True)
        raise Exception(f"OpenAI API error {r.status_code}")
    return r.json()["choices"][0]["message"]["content"]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client
import os

app = Flask(__name__)

# 🔑 Configuración Supabase (desde variables de entorno en Render)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip().lower()
    resp = MessagingResponse()
    reply = ""

    if incoming_msg.startswith("nota "):
        # ejemplo: "nota comprar café"
        contenido = incoming_msg.replace("nota ", "", 1).strip()
        if contenido:
            supabase.table("notas").insert({"texto": contenido}).execute()
            reply = f"✅ Nota guardada: {contenido}"
        else:
            reply = "⚠️ No escribiste nada después de 'nota'."

    elif incoming_msg == "listar notas":
        res = supabase.table("notas").select("*").execute()
        if res.data:
            notas = [f"{i+1}. {n['texto']}" for i, n in enumerate(res.data)]
            reply = "📝 Tus notas:\n" + "\n".join(notas)
        else:
            reply = "No tienes notas todavía."
            
    elif incoming_msg.startswith("borrar nota "):
    try:
        idx = int(incoming_msg.replace("borrar nota ", "", 1).strip()) - 1
        res = supabase.table("notas").select("id").order("created_at", desc=False).execute()
        if 0 <= idx < len(res.data):
            note_id = res.data[idx]["id"]
            supabase.table("notas").delete().eq("id", note_id).execute()
            reply = f"🗑️ Nota {idx+1} borrada."
        else:
            reply = "No existe esa nota."
    except:
        reply = "Formato: 'borrar nota 2'"        

    else:
        reply = "👋 Hola, soy tu Catabot. Puedes usar:\n- 'nota <texto>' para guardar\n- 'listar notas' para verlas"

    resp.message(reply)
    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
