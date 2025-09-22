import os
import re
from datetime import datetime, timezone
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client
from twilio.rest import Client as TwilioClient

# =====================
# Inicializar Flask
# =====================
app = Flask(__name__)

# =====================
# Variables de entorno
# =====================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")  # ej: "whatsapp:+14155238886"

# Conexión a Supabase (opcional)
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Cliente Twilio (opcional)
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# =====================
# Helpers
# =====================
def norm(s: str) -> str:
    """Normaliza texto quitando espacios extras y lo pasa a minúsculas"""
    return re.sub(r"\s+", " ", s.strip().lower())


# =====================
# Endpoints
# =====================
@app.get("/health")
def health():
    """Verifica que la app esté viva (para Render y Twilio)"""
    return "ok", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook principal para Twilio WhatsApp"""
    incoming = request.values.get("Body", "") or ""
    print("🟢 Mensaje entrante:", incoming, flush=True)

    # Crear respuesta de WhatsApp
    resp = MessagingResponse()

    # HOTFIX: siempre responder rápido
    incoming_norm = norm(incoming)
    if incoming_norm in ["hola", "hi", "hello"]:
        resp.message("👋 Hola! Estoy vivo y escuchando.")
    elif incoming_norm == "ayuda":
        resp.message(
            "👋 Comandos disponibles:\n"
            "• nota [texto] — guarda nota\n"
            "• listar notas — ver todas\n"
            "• buscar [texto] — buscar nota\n"
            "• recordar \"texto\" AAAA-MM-DD HH:MM — crea recordatorio\n"
        )
    else:
        resp.message(f"📩 Recibido: {incoming.strip()}")

    return str(resp), 200


# =====================
# Main
# =====================
if __name__ == "__main__":
    # Solo si corres local
    app.run(host="0.0.0.0", port=5000, debug=True)
