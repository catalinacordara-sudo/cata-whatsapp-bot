import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Endpoint de salud
@app.route("/", methods=["GET"])
def index():
    return "OK", 200

# Ruta del webhook de Twilio
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip().lower()
    resp = MessagingResponse()

    # Lógica de notas simple
    if incoming_msg.startswith("nota"):
        contenido = incoming_msg.replace("nota", "", 1).strip()
        if contenido:
            resp.message(f"✔️ Nota guardada: {contenido}")
        else:
            resp.message("❗ No escribiste nada después de 'nota'.")
    elif incoming_msg == "listar notas":
        # aquí iría la lógica para listar notas
        resp.message("No tienes notas todavía.")
    else:
        resp.message("Hola, soy tu Catabot. Usa 'nota <texto>' para guardar notas.")

    return str(resp), 200
