# app.py
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming = (request.values.get("Body", "") or "").strip()
    print(f"💬 Mensaje entrante: {incoming}", flush=True)

    # TwiML de respuesta
    resp = MessagingResponse()
    if incoming:
        resp.message(f"Eco: {incoming}")
    else:
        resp.message("Recibí tu mensaje ✅")

    # Devolver SIEMPRE TwiML con el mime-type correcto
    xml = str(resp)  # <Response><Message>...</Message></Response>
    return Response(xml, mimetype="application/xml")  # también vale "text/xml"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
