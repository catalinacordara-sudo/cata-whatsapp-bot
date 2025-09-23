from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    incoming = (request.values.get("Body", "") or "").strip()
    print(f"💬 Mensaje entrante: {incoming}", flush=True)

    resp = MessagingResponse()
    if request.method == "GET":
        resp.message("Webhook OK (GET) ✅")
    else:
        if incoming:
            resp.message(f"Eco: {incoming}")
        else:
            resp.message("Recibí tu mensaje ✅")

    return Response(str(resp), mimetype="application/xml")
