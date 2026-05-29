import os
import requests
from flask import Flask, request

app = Flask(__name__)

VERIFY_TOKEN      = os.environ.get("VERIFY_TOKEN", "clinica_sonrisa_2026")
WHATSAPP_TOKEN    = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID   = os.environ.get("PHONE_NUMBER_ID")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = """Sos el asistente virtual por WhatsApp de "Clinica Dental Sonrisa", una clinica odontologica en Buenos Aires, Argentina. Atendes consultas y agendas turnos de forma calida, profesional y breve (respuestas cortas estilo WhatsApp, con algun emoji ocasional).

INFORMACION DE LA CLINICA:
- Horarios: Lunes a viernes 9 a 19hs, sabados 9 a 13hs.
- Direccion: Av. Cabildo 2200, Belgrano, CABA.
- Precios orientativos: Consulta inicial $15.000, Limpieza $25.000, Blanqueamiento $90.000, Caries desde $30.000, Ortodoncia desde $250.000, Implantes desde $400.000.
- Obras sociales: OSDE, Swiss Medical, Galeno y Medicus. Con otras se atiende particular con factura para reintegro.
- Para agendar un turno pedi: nombre, tratamiento y dia/horario preferido. Confirma repitiendo los datos y avisa que se envia recordatorio el dia anterior.

REGLAS:
- Respuestas breves, 1-3 oraciones maximo, tono argentino amable (usa "vos").
- Si preguntan algo medico complejo, sugeri agendar consulta con el profesional.
- Nunca inventes precios fuera de los listados.
- Siempre busca avanzar hacia agendar el turno."""

conversations = {}

def ask_claude(user_number, user_text):
    history = conversations.get(user_number, [])
    history.append({"role": "user", "content": user_text})
    history = history[-20:]
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "system": SYSTEM_PROMPT,
            "messages": history,
        },
        timeout=30,
    )
    data = resp.json()
    reply = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text").strip()
    if not reply:
        reply = "Disculpa, me lo repetis?"
    history.append({"role": "assistant", "content": reply})
    conversations[user_number] = history
    return reply

def send_whatsapp(to_number, text):
    requests.post(
        f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages",
        headers={
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": text},
        },
        timeout=30,
    )

@app.route("/webhook", methods=["GET"])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" in entry:
            msg = entry["messages"][0]
            if msg.get("type") == "text":
                user_number = msg["from"]
                user_text = msg["text"]["body"]
                reply = ask_claude(user_number, user_text)
                send_whatsapp(user_number, reply)
    except (KeyError, IndexError):
        pass
    return "OK", 200

@app.route("/", methods=["GET"])
def home():
    return "Bot de clinica funcionando", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
