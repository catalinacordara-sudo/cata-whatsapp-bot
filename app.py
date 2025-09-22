import os
import re
from datetime import datetime, timezone

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

# Supabase
from supabase import create_client, Client

# =========================================
# App & clientes
# =========================================
app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        # No detenemos el servidor; solo dejamos registro
        print("No se pudo crear cliente Supabase:", e, flush=True)
else:
    print("⚠️ Falta SUPABASE_URL o SUPABASE_KEY en variables de entorno", flush=True)

# =========================================
# Helpers
# =========================================
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def must_supabase(resp: MessagingResponse) -> bool:
    """Valida que haya cliente Supabase antes de usar DB."""
    global supabase
    if supabase is None:
        resp.message("⚠️ No hay conexión a base de datos. Revisa SUPABASE_URL y SUPABASE_KEY en Render.")
        return False
    return True

def parse_int(s: str) -> int | None:
    try:
        return int(s)
    except Exception:
        return None

def spanish_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# =========================================
# Rutas de salud
# =========================================
@app.get("/")
def root():
    return "OK", 200

@app.get("/healthz")
def healthz():
    return {"ok": True}, 200

# =========================================
# Webhook WhatsApp
# =========================================
@app.route("/webhook", methods=["POST"])
def webhook():
    incoming = norm(request.values.get("Body", ""))
    print("Mensaje entrante:", incoming, flush=True)

    resp = MessagingResponse()

    if not incoming:
        resp.message("No recibí texto. Escribe *ayuda* para ver comandos.")
        return str(resp), 200

    low = incoming.lower()

    # -------- AYUDA --------
    if low in ("ayuda", "help", "menu"):
        resp.message(
            "👋 *Comandos disponibles*\n"
            "• *nota [texto]* — guarda nota (puedes usar #etiquetas)\n"
            "• *listar notas* — ver todas (no archivadas)\n"
            "• *listar #etiqueta* — ver por etiqueta\n"
            "• *buscar [texto]* — buscar en tus notas\n"
            "• *editar nota N: [nuevo texto]* — edita por número\n"
            "• *borrar nota N* — elimina\n"
            "• *archivar nota N* / *desarchivar nota N*\n"
            "• *stats* — conteos\n"
            "• *recordar \"texto\" AAAA-MM-DD HH:MM* — guarda recordatorio (zona UTC por ahora)\n"
        )
        return str(resp), 200

    # ==========================================================
    # NOTAS (DB: tabla 'notas' con columnas: id (PK), texto text,
    # etiquetas text[], archivada boolean default false, created_at timestamp)
    # ==========================================================

    # -------- AGREGAR NOTA --------
    if low.startswith("nota "):
        if not must_supabase(resp):
            return str(resp), 200

        contenido = norm(incoming[5:])
        if not contenido:
            resp.message("✍️ Escribe algo después de *nota*.")
            return str(resp), 200

        # extraer etiquetas tipo #algo
        etiquetas = [t[1:] for t in re.findall(r"#\w+", contenido)]
        try:
            supabase.table("notas").insert({
                "texto": contenido,
                "etiquetas": etiquetas or None,
                "archivada": False
            }).execute()
            resp.message(f"✅ Nota guardada: {contenido}")
        except Exception as e:
            print("Error insert nota:", e, flush=True)
            resp.message("❌ No pude guardar la nota. Revisa que exista la tabla *notas* en Supabase.")
        return str(resp), 200

    # -------- LISTAR NOTAS / LISTAR #ETIQUETA --------
    if low == "listar notas" or low.startswith("listar #"):
        if not must_supabase(resp):
            return str(resp), 200

        try:
            if low.startswith("listar #"):
                tag = incoming.split("#", 1)[1].strip()
                q = supabase.table("notas").select("id,texto,etiquetas,archivada,created_at") \
                    .contains("etiquetas", [tag]) \
                    .order("created_at", desc=False)
            else:
                q = supabase.table("notas").select("id,texto,etiquetas,archivada,created_at") \
                    .eq("archivada", False) \
                    .order("created_at", desc=False)

            res = q.execute()
            data = res.data or []
            if not data:
                resp.message("No tienes notas todavía.")
                return str(resp), 200

            lines = []
            for i, n in enumerate(data, start=1):
                marca = "📦" if n.get("archivada") else "📝"
                lines.append(f"{i}. {marca} {n.get('texto')}")
            resp.message("Tus notas:\n" + "\n".join(lines))
        except Exception as e:
            print("Error listar notas:", e, flush=True)
            resp.message("❌ No pude listar notas. Verifica la tabla *notas*.")
        return str(resp), 200

    # -------- BUSCAR --------
    if low.startswith("buscar "):
        if not must_supabase(resp):
            return str(resp), 200
        term = norm(incoming[7:])
        if not term:
            resp.message("Indica qué buscar, ej: *buscar extractor*")
            return str(resp), 200
        try:
            res = supabase.table("notas").select("id,texto,archivada,created_at") \
                .like("texto", f"%{term}%").order("created_at", desc=False).execute()
            data = res.data or []
            if not data:
                resp.message("No encontré notas que coincidan.")
            else:
                lines = [f"{i}. {'📦' if n['archivada'] else '📝'} {n['texto']}"
                         for i, n in enumerate(data, start=1)]
                resp.message("Resultados:\n" + "\n".join(lines))
        except Exception as e:
            print("Error buscar:", e, flush=True)
            resp.message("❌ Hubo un problema al buscar.")
        return str(resp), 200

    # -------- EDITAR / BORRAR / (DES)ARCHIVAR por índice visible --------
    # El índice visible es la posición en el listado cronológico (no el id real).
    def _resolver_id_por_indice(idx_visible: int) -> int | None:
        """Devuelve el id real de la nota por su posición en orden cronológico ascendente (no archivadas)."""
        try:
            res = supabase.table("notas").select("id").order("created_at", desc=False).execute()
            data = res.data or []
            if 1 <= idx_visible <= len(data):
                return data[idx_visible - 1]["id"]
            return None
        except Exception as e:
            print("Error resolviendo id por índice:", e, flush=True)
            return None

    # editar nota N: nuevo texto
    if low.startswith("editar nota "):
        if not must_supabase(resp):
            return str(resp), 200
        m = re.match(r"editar nota\s+(\d+)\s*:\s*(.+)", incoming, flags=re.I)
        if not m:
            resp.message("Formato: *editar nota N: nuevo texto*")
            return str(resp), 200
        idx = parse_int(m.group(1))
        nuevo = norm(m.group(2))
        if not idx or not nuevo:
            resp.message("Formato: *editar nota N: nuevo texto*")
            return str(resp), 200
        note_id = _resolver_id_por_indice(idx)
        if not note_id:
            resp.message("No existe esa nota.")
            return str(resp), 200
        try:
            etiquetas = [t[1:]] if (t := re.search(r"#\w+", nuevo)) else None
            supabase.table("notas").update({"texto": nuevo, "etiquetas": etiquetas}).eq("id", note_id).execute()
            resp.message(f"✏️ Nota {idx} actualizada.")
        except Exception as e:
            print("Error editar:", e, flush=True)
            resp.message("❌ No pude editar la nota.")
        return str(resp), 200

    # borrar nota N
    if low.startswith("borrar nota "):
        if not must_supabase(resp):
            return str(resp), 200
        idx = parse_int(incoming.split()[-1])
        if not idx:
            resp.message("Formato: *borrar nota N*")
            return str(resp), 200
        note_id = _resolver_id_por_indice(idx)
        if not note_id:
            resp.message("No existe esa nota.")
            return str(resp), 200
        try:
            supabase.table("notas").delete().eq("id", note_id).execute()
            resp.message(f"🗑️ Nota {idx} borrada.")
        except Exception as e:
            print("Error borrar:", e, flush=True)
            resp.message("❌ No pude borrar la nota.")
        return str(resp), 200

    # archivar / desarchivar
    if low.startswith("archivar nota ") or low.startswith("desarchivar nota "):
        if not must_supabase(resp):
            return str(resp), 200
        des = low.startswith("desarchivar")
        idx = parse_int(incoming.split()[-1])
        if not idx:
            resp.message(f"Formato: *{'desarchivar' if des else 'archivar'} nota N*")
            return str(resp), 200
        note_id = _resolver_id_por_indice(idx)
        if not note_id:
            resp.message("No existe esa nota.")
            return str(resp), 200
        try:
            supabase.table("notas").update({"archivada": des is False}).eq("id", note_id).execute()
            resp.message(("📦 Archivada" if not des else "📤 Desarchivada") + f" la nota {idx}.")
        except Exception as e:
            print("Error (des)archivar:", e, flush=True)
            resp.message("❌ No pude actualizar la nota.")
        return str(resp), 200

    # -------- STATS --------
    if low == "stats":
        if not must_supabase(resp):
            return str(resp), 200
        try:
            total = supabase.table("notas").select("id", count="exact").execute().count or 0
            activas = supabase.table("notas").select("id", count="exact").eq("archivada", False).execute().count or 0
            arch = total - activas
            resp.message(f"📊 Notas totales: {total}\n📝 Activas: {activas}\n📦 Archivadas: {arch}")
        except Exception as e:
            print("Error stats:", e, flush=True)
            resp.message("❌ No pude calcular estadísticas.")
        return str(resp), 200

    # -------- RECORDAR "texto" AAAA-MM-DD HH:MM --------
    if low.startswith("recordar "):
        if not must_supabase(resp):
            return str(resp), 200

        m = re.match(r'recordar\s+"(.+?)"\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})', incoming, flags=re.I)
        if not m:
            resp.message('Formato: *recordar "texto" AAAA-MM-DD HH:MM* (zona UTC por ahora)')
            return str(resp), 200

        texto = m.group(1).strip()
        fecha = m.group(2)
        hora = m.group(3)
        try:
            when = datetime.fromisoformat(f"{fecha} {hora}")
        except Exception:
            resp.message("Fecha/hora inválidas. Usa AAAA-MM-DD HH:MM (24h).")
            return str(resp), 200

        try:
            supabase.table("recordatorios").insert({
                "texto": texto,
                "cuando_utc": when.isoformat()
            }).execute()
            resp.message(f"⏰ Recordatorio guardado para {spanish_datetime(when)}:\n• {texto}\n"
                         "(*Para enviarlo automático necesitas un cron; por ahora queda guardado*)")
        except Exception as e:
            print("Error guardar recordatorio:", e, flush=True)
            resp.message("❌ No pude guardar el recordatorio. Verifica tabla *recordatorios*.")
        return str(resp), 200

    # -------- Fallback --------
    resp.message("No te entendí. Escribe *ayuda* para ver comandos.")
    return str(resp), 200


# =========================================
# Main local (Render usa gunicorn via Procfile)
# =========================================
if __name__ == "__main__":
    # Para pruebas locales
    app.run(host="0.0.0.0", port=5000)
