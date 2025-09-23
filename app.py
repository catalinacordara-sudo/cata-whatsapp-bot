from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    print("💜 Healthcheck / OK", flush=True)
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.values.get("Body", "") or ""
    from_num = request.values.get("From", "") or ""
    print(f"💬 Mensaje entrante: {body} | from={from_num}", flush=True)

    resp = MessagingResponse()
    resp.message(f"Recibí: {body}")

    xml = str(resp)  # TwiML
    return Response(xml, status=200, mimetype="application/xml")
