import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

# Inicializa Flask
app = Flask(__name__)

# Endpoint de healthcheck
@app.route("/", methods=["GET"])
def health():
    print("💜 Healthcheck / OK", flush=True)
    return "OK", 200

# Endpoint principal para Twilio
@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.values.get("Body", "") or ""
    from_num = request.values.get("From", "") or ""
    print(f"💬 Mensaje entrante: {body} | from={from_num}", flush=True)

    resp = MessagingResponse()
    resp.message(f"Recibí: {body}")

    # ⚠️ Devuelve XML con el header correcto
    return str(resp), 200, {"Content-Type": "application/xml; charset=utf-8"}

# Endpoint de prueba TwiML (opcional)
@app.route("/twiml-test", methods=["POST"])
def twiml_test():
    r = MessagingResponse()
    r.message("🚀 TwiML OK (ruta de prueba)")
    return str(r), 200, {"Content-Type": "application/xml; charset=utf-8"}

# Run local (Render usará gunicorn con Procfile)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
