@app.post("/webhook")
def webhook():
    from twilio.twiml.messaging_response import MessagingResponse
    incoming = request.values.get("Body", "") or ""
    print(">>> Llego WhatsApp:", incoming, flush=True)

    # HOTFIX: responde siempre rápido para probar conectividad
    resp = MessagingResponse()
    resp.message("✅ Vivo y escuchando: " + incoming[:60])
    return str(resp), 200
import os
import re
from datetime import datetime, timezone
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from supabase import create_client
from twilio.rest import Client as TwilioClient

app = Flask(__name__)

# ====== ENV ======
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Opcionales (solo si usarás recordatorios /cron)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")  # ej: "whatsapp:+14155238886"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ====== HELPERS ======
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def extract_tags(text: str) -> list[str]:
    # Devuelve hashtags únicos en minúsculas (sin #)
    tags = {t[1:].lower() for t in re.findall(r"#\w+", text)}
    return list(tags)

def ok(resp_text: str):
    tw = MessagingResponse()
    tw.message(resp_text)
    return str(tw), 200

# ====== COMANDOS ======
HELP_TEXT = (
    "👋 *Comandos disponibles*\n"
    "• *nota [texto]* — guarda nota (puedes incluir #etiquetas)\n"
    "• *listar notas* — ver todas (no archivadas)\n"
    "• *listar #etiqueta* — ver por etiqueta\n"
    "• *buscar [texto]* — buscar en tus notas\n"
    "• *editar nota N: [nuevo texto]* — edita por número\n"
    "• *borrar nota N* — elimina\n"
    "• *archivar nota N* / *desarchivar nota N*\n"
    "• *stats* — conteos\n"
    "• *recordar \"texto\" AAAA-MM-DD HH:MM* — crea recordatorio (24h, UTC local → ajusta tu zona)\n"
)

# ====== WEBHOOK ======
@app.route("/webhook", methods=["POST"])
def webhook():
    raw_msg = (request.values.get("Body", "") or "").strip()
    incoming = norm(raw_msg)
    user_id = request.values.get("From", "")  # ej: "whatsapp:+614..."
    if not user_id:
        return ok("No pude identificar tu número. Intenta nuevamente.")

    # ----- AYUDA -----
    if incoming in ("ayuda", "help", "menu"):
        return ok(HELP_TEXT)

    # ----- AGREGAR NOTA -----
    if incoming.startswith(("nota ", "nota:", "nota,")) or incoming == "nota":
        contenido = re.sub(r"(?i)^nota\s*[: ,]?\s*", "", raw_msg).strip()
        if not contenido:
            return ok("⚠️ Escribe algo después de *nota*. Ej: *nota Comprar bolsas*")
        tags = extract_tags(contenido)
        data = {"user_id": user_id, "texto": contenido, "archivado": False, "tags": tags}
        supabase.table("notas").insert(data).execute()
        return ok(f"✅ Nota guardada: {contenido}")

    # ----- LISTAR NOTAS (todas, no archivadas) -----
    if incoming in ("listar notas", "listar nota", "ver notas", "mostrar notas"):
        res = (supabase.table("notas")
               .select("*")
               .eq("user_id", user_id)
               .eq("archivado", False)
               .order("created_at", desc=False)
               .execute())
        if not res.data:
            return ok("📭 No tienes notas todavía.")
        notas = [f"{i+1}. {n['texto']}" for i, n in enumerate(res.data)]
        return ok("📝 *Tus notas:*\n" + "\n".join(notas))

    # ----- LISTAR POR ETIQUETA: 'listar #tag' -----
    m_tag = re.match(r"^listar\s+(#\w+)$", incoming)
    if m_tag:
        tag = m_tag.group(1)[1:].lower()
        res = (supabase.table("notas")
               .select("*")
               .eq("user_id", user_id)
               .eq("archivado", False)
               .contains("tags", [tag])  # requiere columna 'tags' tipo array/text[]
               .order("created_at", desc=False)
               .execute())
        if not res.data:
            return ok(f"📭 No hay notas con #{tag}.")
        notas = [f"{i+1}. {n['texto']}" for i, n in enumerate(res.data)]
        return ok(f"🏷️ *Notas con #{tag}:*\n" + "\n".join(notas))

    # ----- BUSCAR -----
    if incoming.startswith("buscar "):
        term = incoming.replace("buscar ", "", 1).strip()
        if not term:
            return ok("Formato: *buscar extractor*")
        res = (supabase.table("notas")
               .select("*")
               .eq("user_id", user_id)
               .eq("archivado", False)
               .ilike("texto", f"%{term}%")
               .order("created_at", desc=False)
               .execute())
        if not res.data:
            return ok("🔎 No encontré coincidencias.")
        notas = [f"{i+1}. {n['texto']}" for i, n in enumerate(res.data)]
        return ok("🔎 *Resultados:*\n" + "\n".join(notas))

    # ----- EDITAR NOTA -----
    m_edit = re.match(r"^editar nota\s+(\d+)\s*:\s*(.+)$", incoming)
    if m_edit:
        idx = int(m_edit.group(1)) - 1
        nuevo = raw_msg.split(":", 1)[1].strip() if ":" in raw_msg else ""
        res = (supabase.table("notas")
               .select("id")
               .eq("user_id", user_id)
               .eq("archivado", False)
               .order("created_at", desc=False)
               .execute())
        if not res.data or not (0 <= idx < len(res.data)):
            return ok("❌ No existe esa nota.")
        note_id = res.data[idx]["id"]
        tags = extract_tags(nuevo)
        supabase.table("notas").update({"texto": nuevo, "tags": tags}).eq("id", note_id).execute()
        return ok(f"✏️ Nota {idx+1} actualizada.")

    # ----- ARCHIVAR / DESARCHIVAR -----
    m_arch = re.match(r"^(archivar|desarchivar)\s+nota\s+(\d+)$", incoming)
    if m_arch:
        action = m_arch.group(1)
        idx = int(m_arch.group(2)) - 1
        res = (supabase.table("notas")
               .select("id")
               .eq("user_id", user_id)
               .order("created_at", desc=False)
               .execute())
        if not res.data or not (0 <= idx < len(res.data)):
            return ok("❌ No existe esa nota.")
        note_id = res.data[idx]["id"]
        supabase.table("notas").update({"archivado": action == "archivar"}).eq("id", note_id).execute()
        return ok(("📦 Archivada." if action == "archivar" else "📤 Desarchivada.") + f" (nota {idx+1})")

    # ----- BORRAR -----
    m_del = re.match(r"^(borrar|eliminar|quitar)\s+nota\s+(\d+)$", incoming)
    if m_del:
        idx = int(m_del.group(2)) - 1
        res = (supabase.table("notas")
               .select("id")
               .eq("user_id", user_id)
               .eq("archivado", False)
               .order("created_at", desc=False)
               .execute())
        if not res.data or not (0 <= idx < len(res.data)):
            return ok("❌ No existe esa nota.")
        note_id = res.data[idx]["id"]
        supabase.table("notas").delete().eq("id", note_id).execute()
        return ok(f"🗑️ Nota {idx+1} borrada.")

    # ----- STATS -----
    if incoming == "stats":
        tot = supabase.table("notas").select("id", count="exact").eq("user_id", user_id).execute().count or 0
        act = (supabase.table("notas")
               .select("id", count="exact")
               .eq("user_id", user_id).eq("archivado", False)
               .execute().count or 0)
        arc = tot - act
        return ok(f"📊 *Stats*\nActivas: {act}\nArchivadas: {arc}\nTotal: {tot}")

    # ----- RECORDATORIOS -----
    # Formato: recordar "texto" 2025-09-22 18:00
    m_rem = re.match(r'^recordar\s+"(.+)"\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})$', incoming)
    if m_rem:
        if not twilio_client or not TWILIO_WHATSAPP_FROM:
            return ok("Para usar recordatorios, configura TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN y TWILIO_WHATSAPP_FROM.")
        texto = m_rem.group(1)
        dt_str = f"{m_rem.group(2)} {m_rem.group(3)}"
        try:
            due = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except Exception:
            return ok("Fecha/hora inválida. Usa AAAA-MM-DD HH:MM (24h). Ej: 2025-09-22 18:00")
        supabase.table("recordatorios").insert({
            "user_id": user_id,
            "texto": texto,
            "due_at": due.isoformat(),
            "enviado": False
        }).execute()
        return ok(f"⏰ Recordatorio guardado para {dt_str} (UTC).")

    # Si nada coincide
    return ok("No te entendí. Escribe *ayuda* para ver comandos.")

# ====== CRON (llama cada 1-5 min con un scheduler/cron externo) ======
@app.route("/cron", methods=["GET"])
def cron():
    if not twilio_client or not TWILIO_WHATSAPP_FROM:
        return "cron disabled", 200
    now = datetime.now(timezone.utc).isoformat()
    res = (supabase.table("recordatorios")
           .select("*")
           .eq("enviado", False)
           .lte("due_at", now)
           .execute())
    for r in res.data or []:
        try:
            twilio_client.messages.create(
                from_=TWILIO_WHATSAPP_FROM,
                to=r["user_id"],  # ej: "whatsapp:+614..."
                body=f"⏰ Recordatorio: {r['texto']}"
            )
            supabase.table("recordatorios").update({"enviado": True}).eq("id", r["id"]).execute()
        except Exception as e:
            print("cron send error:", e, flush=True)
    return f"processed {len(res.data or [])}", 200

# ====== Health ======
@app.route("/health", methods=["GET"])
def health():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
