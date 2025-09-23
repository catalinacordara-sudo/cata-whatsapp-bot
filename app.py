import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    # Pista visible en logs de Render:
    print("💜 Healthcheck / OK", flush=True)
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.values.get("Body", "") or ""
    from_num = request.values.get("From", "") or ""
    print(f"💬 Mensaje entrante: {body} | from={from_num}", flush=True)

    # RESPUESTA INMEDIATA
    resp = MessagingResponse()
    resp.message(f"Recibí: {body}")
    # Twilio espera texto XML TwiML. str(resp) lo devuelve.
    return str(resp), 200
