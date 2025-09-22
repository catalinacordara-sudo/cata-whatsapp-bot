from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return "ok", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "webhook alive", 200

    # Captura mensaje entrante
    incoming_msg = request.values.get("Body", "").lower()

    # Respuesta fija de prueba
    reply_text = "¡Conectadas! 🎉 Ya recibo tus mensajes desde WhatsApp."

    # Construye respuesta Twilio
    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    
