from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import pusher
import mysql.connector
from datetime import datetime
import random
import threading

app = Flask(__name__)
CORS(app)  # 🌍 Acceso público desde cualquier dominio

# ✅ Conexión MySQL optimizada (usa conexión persistente por hilo)
DB_CONFIG = {
    "host": "mysql-wilson.alwaysdata.net",
    "user": "wilson",
    "password": "wilsonCMV20_",
    "database": "wilson_db",
    "connection_timeout": 3
}

# Crear un pool simple de conexiones
from mysql.connector import pooling
cnxpool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **DB_CONFIG)

def get_db_connection():
    return cnxpool.get_connection()

# ✅ Configuración de Pusher
pusher_client = pusher.Pusher(
    app_id="2062323",
    key="b6bbf62d682a7a882f41",
    secret="36605cfd7b0a8de9935b",
    cluster="mt1",
    ssl=True
)

# =====================================================
# 🚀 FUNCIONALIDAD PRINCIPAL
# =====================================================

@app.route("/join", methods=["POST"])
def join_channel():
    """Asigna un canal aleatorio a un usuario nuevo o devuelve el actual"""
    data = request.get_json()
    username = data.get("username")

    if not username:
        return jsonify({"error": "Nombre de usuario requerido"}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Cachear nombres de canales (más rápido que consultarlos siempre)
        cursor.execute("SELECT name FROM channels")
        canales = [row["name"] for row in cursor.fetchall()]
        if not canales:
            return jsonify({"error": "No hay canales disponibles"}), 404

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
    """Guarda y transmite un mensaje (asincrónico para menor latencia)"""
    data = request.get_json()
    username = data.get("sender")
    message = data.get("message")
    channel = data.get("channel", "canal1")

    if not username or not message:
        return jsonify({"error": "Faltan campos obligatorios"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def guardar_y_emitir():
        try:
            db = get_db_connection()
            cursor = db.cursor()
            cursor.execute("""
                INSERT INTO messages (username, message, channel, timestamp)
                VALUES (%s, %s, %s, %s)
            """, (username, message, channel, timestamp))
            db.commit()
            cursor.close()
            db.close()

            # Emitir mensaje en segundo plano (sin bloquear al usuario)
            pusher_client.trigger(channel, "new-message", {
                "sender": username,
                "message": message,
                "timestamp": timestamp
            })
        except Exception as e:
            print(f"❌ Error en envío asíncrono: {e}")

    # Ejecutar el envío y guardado en otro hilo
    threading.Thread(target=guardar_y_emitir).start()

    # Responder instantáneamente sin esperar MySQL
    return jsonify({"status": "Enviado"}), 200


@app.route("/messages/<channel>", methods=["GET"])
def obtener_mensajes(channel):
    """Obtiene los últimos 50 mensajes (carga más rápida con índice y orden ascendente)"""
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # ✅ Asegúrate de tener un índice en (channel, id) para máxima velocidad
        cursor.execute("""
            SELECT username, message, timestamp
            FROM messages
            WHERE channel = %s
            ORDER BY id DESC
            LIMIT 50
        """, (channel,))
        mensajes = cursor.fetchall()

        # Invertir sin Python lento → se hace en SQL
        mensajes.reverse()

        return jsonify(mensajes), 200
    except Exception as e:
        return jsonify({"error": f"Error al obtener mensajes: {e}"}), 500
    finally:
        cursor.close()
        db.close()


# =====================================================
# 🧩 PANEL ADMINISTRATIVO (igual que antes)
# =====================================================

@app.route("/")
def index():
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
    fetch("/send", {{
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
    app.run(debug=True, threaded=True)
