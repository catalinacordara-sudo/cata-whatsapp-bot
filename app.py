from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# --- Ruta principal del webhook ---
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").lower()

    # Llamamos a la función de respuesta (por ahora fija para probar)
    reply_text = call_openai(incoming_msg)

    # Creamos respuesta para Twilio
    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp)

# --- Función de respuesta (fija por ahora) ---
def call_openai(user_text: str) -> str:
    return "¡Conectadas! 🎉 Ya recibo tus mensajes desde WhatsApp."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
