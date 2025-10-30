from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import pusher
import mysql.connector
from datetime import datetime
import random

app = Flask(__name__)

# ✅ CORS - dominios permitidos
CORS(app, origins=[
    "https://websocket-front-wil.vercel.app",
    "https://websocket-front2-wil.vercel.app",
    "https://websocket-front-wil-git-master-wils20s-projects.vercel.app",
    "https://websocket-front2-wil-git-master-wils20s-projects.vercel.app"
])

# ✅ Configuración de conexión MySQL
DB_CONFIG = {
    "host": "mysql-wilson.alwaysdata.net",
    "user": "wilson",
    "password": "wilsonCMV20_",
    "database": "wilson_db"
}

def get_db_connection():
    """Crea y devuelve una conexión MySQL"""
    return mysql.connector.connect(**DB_CONFIG)

# ✅ Configuración de Pusher
pusher_client = pusher.Pusher(
    app_id='2062323',
    key='b6bbf62d682a7a882f41',
    secret='36605cfd7b0a8de9935b',
    cluster='mt1',
    ssl=True
)

# =====================================================
# 🚀 RUTAS PRINCIPALES
# =====================================================

@app.route("/join", methods=["POST"])
def join_channel():
    """Asigna un canal aleatorio a un nuevo usuario o devuelve el actual"""
    data = request.get_json()
    username = data.get("username")

    if not username:
        return jsonify({"error": "Nombre de usuario requerido"}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Buscar canales disponibles
        cursor.execute("SELECT name FROM channels")
        canales = [row["name"] for row in cursor.fetchall()]
        if not canales:
            return jsonify({"error": "No hay canales disponibles"}), 404

        # Verificar si el usuario ya tiene canal
        cursor.execute("SELECT channel FROM conversations WHERE username=%s", (username,))
        existing = cursor.fetchone()

        if existing:
            channel = existing["channel"]
        else:
            channel = random.choice(canales)
            cursor.execute("INSERT INTO conversations (username, channel) VALUES (%s, %s)", (username, channel))
            db.commit()

        return jsonify({"channel": channel}), 200

    except Exception as e:
        return jsonify({"error": f"Error interno: {e}"}), 500

    finally:
        cursor.close()
        db.close()


@app.route("/send", methods=["POST"])
def enviar_mensaje():
    """Guarda y transmite un mensaje"""
    data = request.get_json()
    username = data.get("sender")
    message = data.get("message")
    channel = data.get("channel", "canal1")

    if not username or not message:
        return jsonify({"error": "Faltan campos obligatorios"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO messages (username, message, channel, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (username, message, channel, timestamp))
        db.commit()

        # Enviar a Pusher
        pusher_client.trigger(channel, 'new-message', {
            'sender': username,
            'message': message,
            'timestamp': timestamp
        })

        return jsonify({"status": "Mensaje enviado correctamente"}), 200

    except Exception as e:
        return jsonify({"error": f"Error al enviar mensaje: {e}"}), 500

    finally:
        cursor.close()
        db.close()


@app.route("/messages/<channel>", methods=["GET"])
def obtener_mensajes(channel):
    """Devuelve los últimos 50 mensajes de un canal"""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT username, message, timestamp
            FROM messages
            WHERE channel = %s
            ORDER BY id DESC LIMIT 50
        """, (channel,))
        mensajes = cursor.fetchall()
        return jsonify(mensajes[::-1]), 200

    except Exception as e:
        return jsonify({"error": f"Error al obtener mensajes: {e}"}), 500

    finally:
        cursor.close()
        db.close()


# =====================================================
# 🧩 PANEL ADMINISTRATIVO
# =====================================================

@app.route("/")
def index():
    """Panel HTML con lista de canales y chat"""
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT name FROM channels")
    canales = [row["name"] for row in cursor.fetchall()]
    cursor.close()
    db.close()

    botones = "".join([f"<button onclick=\"selectChannel('{c}')\">{c}</button>" for c in canales])

    return render_template_string(f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Panel de Canales</title>
<script src="https://js.pusher.com/8.2/pusher.min.js"></script>
<style>
body {{ margin: 0; font-family: Arial, sans-serif; background: #f4f4f4; display: flex; height: 100vh; }}
aside {{ width: 25%; background: #fff; border-right: 1px solid #ccc; overflow-y: auto; padding: 20px; }}
aside h2 {{ color: #5a2ca0; font-size: 20px; margin-bottom: 10px; }}
aside button {{ display: block; width: 100%; background: #eee; border: none; padding: 10px; margin-bottom: 5px; text-align: left; cursor: pointer; border-radius: 5px; transition: background 0.2s; }}
aside button:hover {{ background: #ddd; }}
main {{ flex: 1; display: flex; flex-direction: column; }}
header {{ background: #fff; border-bottom: 1px solid #ccc; padding: 10px 20px; font-weight: bold; color: #5a2ca0; }}
#chat-box {{ flex: 1; padding: 15px; overflow-y: auto; background: #fafafa; }}
.message {{ background: #fff; border-radius: 6px; padding: 8px 10px; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }}
.message strong {{ color: #333; }}
.message small {{ color: #888; font-size: 11px; }}
footer {{ background: #fff; padding: 10px; display: flex; border-top: 1px solid #ccc; }}
footer input {{ padding: 8px; margin-right: 5px; border: 1px solid #ccc; border-radius: 4px; }}
footer input#username {{ width: 20%; }}
footer input#message {{ flex: 1; }}
footer button {{ background: #5a2ca0; color: white; border: none; padding: 8px 15px; border-radius: 4px; cursor: pointer; }}
footer button:hover {{ background: #4b2386; }}
</style>
</head>
<body>
  <aside>
    <h2>📡 Canales</h2>
    {botones}
  </aside>
  <main>
    <header id="channel-name">Selecciona un canal</header>
    <div id="chat-box"></div>
    <footer>
      <input id="username" placeholder="Tu nombre">
      <input id="message" placeholder="Escribe un mensaje...">
      <button onclick="sendMessage()">Enviar</button>
    </footer>
  </main>

<script>
let currentChannel = null;
let pusher = new Pusher('b6bbf62d682a7a882f41', {{ cluster: 'mt1' }});
let channelPusher = null;

function selectChannel(channel) {{
    currentChannel = channel;
    document.getElementById("channel-name").innerText = "#" + channel;
    document.getElementById("chat-box").innerHTML = "<p>Cargando mensajes...</p>";
    loadMessages(channel);
    subscribeChannel(channel);
}}

async function loadMessages(channel) {{
    const res = await fetch(`/messages/${{channel}}`);
    const messages = await res.json();
    renderMessages(messages);
}}

function renderMessages(messages) {{
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";
    messages.forEach(m => {{
        const div = document.createElement("div");
        div.className = "message";
        div.innerHTML = `<strong>${{m.username}}:</strong> ${{m.message}} <br><small>${{m.timestamp}}</small>`;
        chatBox.appendChild(div);
    }});
    chatBox.scrollTop = chatBox.scrollHeight;
}}

async function sendMessage() {{
    const sender = document.getElementById("username").value.trim();
    const message = document.getElementById("message").value.trim();
    if (!sender || !message || !currentChannel) return alert("Completa todos los campos.");
    await fetch("/send", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ sender, message, channel: currentChannel }})
    }});
    document.getElementById("message").value = "";
}}

function subscribeChannel(channel) {{
    if (channelPusher) {{
        channelPusher.unbind_all();
        pusher.unsubscribe(channelPusher.name);
    }}
    channelPusher = pusher.subscribe(channel);
    channelPusher.bind('new-message', data => {{
        if (currentChannel !== channel) return;
        const chatBox = document.getElementById("chat-box");
        const msgDiv = document.createElement("div");
        msgDiv.className = "message";
        msgDiv.style.background = "#f5e8ff";
        msgDiv.innerHTML = `<strong>${{data.sender}}:</strong> ${{data.message}} <br><small>${{data.timestamp}}</small>`;
        chatBox.appendChild(msgDiv);
        chatBox.scrollTop = chatBox.scrollHeight;
    }});
}}
</script>
</body>
</html>
""")


@app.route("/ping")
def ping():
    return jsonify({"status": "Servidor activo ✅"})


if __name__ == "__main__":
    app.run(debug=True)
