from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os, requests

app = Flask(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

SYSTEM_PROMPT = """
Eres el asistente personal de Catalina Alejandra Córdova Araya (Cata).
Responde en español, con tono cálido, directo y práctico.
- Firma ejemplos de emails con: "muchas gracias y lo siento por molestarte."
- Ayuda en: negocios (Docor, Purrlandia, Wilaru), mensajes profesionales, organización diaria, nutrición y entrenamiento.
- Da pasos concretos y plantillas cuando convenga.
"""

def call_openai(user_text: str) -> str:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text}
        ],
        "max_tokens": 500
    }
    r = requests.post(url, json=data, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.form.get("Body", "").strip()
    resp = MessagingResponse()
    try:
        reply = call_openai(incoming_msg)
    except Exception as e:
        reply = "Ups, hubo un error al generar la respuesta. Intenta de nuevo más tarde."
    resp.message(reply)
    return str(resp), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
