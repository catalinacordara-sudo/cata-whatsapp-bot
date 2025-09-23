# app.py
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route("/webhook", methods=["GET","POST"])
def webhook():
    incoming = (request.values.get("Body", "") or "").strip()
    print(f"💬 Mensaje entrante: {incoming}", flush=True)

    resp = MessagingResponse()
    if reqest.method=="GET":
        # Prueba desde el navegador
        resp.message(Webhook ok (GET)")
    else:
        #Twilio usara POST
        resp.message("Webhook OK(GET)✅")
    else:
        #Twilio usara POST
        if incoming:
            resp.message(f"Eco:{incoming}")
        else:
            resp.message(Recibi tu mensaje")

    xml = str(resp)  
    return Response(xml, mimetype="application/xml")  
