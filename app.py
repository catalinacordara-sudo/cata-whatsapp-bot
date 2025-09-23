import os
from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# ---------- util ----------
def twiml(text: str) -> str:
    resp = MessagingResponse()
    resp.message(text)
    return str(resp)

# ---------- rutas ----------
@app.route("/", methods=["GET"])
def root():
    return "ok", 200

@app.route("/debug", methods=["GET"])
def debug():
    body = request.args.get("Body", "").strip()
    if not body:
        body = "(sin Body)"
    return Response(twiml(f"Echo debug: {body}"), mimetype="text/xml")

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming = (request.values.get("Body", "") or "").strip()
    print(f"💬 Mensaje entrante: {incoming}", flush=True)

    if not incoming:
        return Response(twiml("No entendí. Escribe 'ayuda'."), mimetype="text/xml")

    msg = incoming.lower()

    if msg == "ayuda":
        texto = (
            "👋 *Comandos disponibles*\n"
            "• nota <texto> — guarda una nota (demo)\n"
            "• listar notas — ver notas (demo)\n"
            "• ayuda — muestra este menú"
        )
        return Response(twiml(texto), mimetype="text/xml")

    if msg.startswith("nota "):
        contenido = incoming[5:].strip()
        if contenido:
            return Response(twiml(f"✅ Nota guardada: {contenido}"), mimetype="text/xml")
        return Response(twiml("❗ Escribe algo después de 'nota'."), mimetype="text/xml")

    if msg == "listar notas":
        return Response(twiml("📒 Aún sin notas (demo)."), mimetype="text/xml")

    return Response(twiml("Hola 👋. Escribe 'ayuda' para ver comandos."), mimetype="text/xml")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
