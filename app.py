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
    incoming_msg = request.values.get("Body", "")

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
