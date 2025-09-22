from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Salud / debug rápido
@app.route("/health", methods=["GET"])
def health():
    return "ok", 200

# Webhook: aceptamos GET (para probar desde el navegador) y POST (Twilio)
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        print(">>> GET /webhook recibido", flush=True)
        return "webhook alive", 200

    # POST (Twilio)
    print(">>> POST /webhook recibido. Form:", dict(request.form), flush=True)

    # Respuesta fija para descartar problemas con OpenAI
    reply_text = "¡Conectadas! 🎉 Ya recibo tus mensajes desde WhatsApp."

    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
