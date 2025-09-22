import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming = request.values.get("Body", "").strip()
    print("Mensaje entrante:", incoming, flush=True)

    resp = MessagingResponse()
    resp.message(f"Recibí tu mensaje: {incoming}")

    return str(resp), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
