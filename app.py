from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import pusher
import mysql.connector
from datetime import datetime
import random
import string

app = Flask(__name__)

# 🔓 CORS (autoriza solo tus frontends)
CORS(app, origins=[
    "https://websocket-front-wil.vercel.app",
    "https://websocket-front2-wil.vercel.app",
    "https://websocket-front-wil-git-master-wils20s-projects.vercel.app",
    "https://websocket-front2-wil-git-master-wils20s-projects.vercel.app"
])

# 🔹 Conexión a MySQL
def get_db_connection():
    return mysql.connector.connect(
        host="mysql-wilson.alwaysdata.net",
        user="wilson",
        password="wilsonCMV20_",
        database="wilson_db"
    )

# 🔹 Configuración de Pusher
pusher_client = pusher.Pusher(
    app_id='2062323',
    key='b6bbf62d682a7a882f41',
    secret='36605cfd7b0a8de9935b',
    cluster='mt1',
    ssl=True
)

# ✅ Generar nombre de canal aleatorio
def generar_canal():
    return "channel_" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

# ✅ Endpoint: asignar canal automático a cada usuario
@app.route("/join", methods=["POST"])
def join_channel():
    try:
        data = request.get_json()
        username = data.get("username")
        if not username:
            return jsonify({"error": "Missing 'username'"}), 400

        canal = generar_canal()

        # Guardar canal asignado
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO channels (username, channel_name, joined_at) VALUES (%s, %s, %s)",
            (username, canal, datetime.now())
        )
        db.commit()
        cursor.close()
        db.close()

        return jsonify({"channel": canal}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Enviar mensaje
@app.route("/send", methods=["POST"])
def enviar_mensaje():
    try:
        data = request.get_json()
        username = data.get("sender")
        message = data.get("message")
        channel = data.get("channel")

        if not username or not message or not channel:
            return jsonify({"error": "Missing fields"}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Guardar mensaje
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO messages (username, message, channel, timestamp) VALUES (%s, %s, %s, %s)",
            (username, message, channel, timestamp)
        )
        db.commit()
        cursor.close()
        db.close()

        # Enviar mensaje por Pusher
        pusher_client.trigger(channel, 'new-message', {
            'sender': username,
            'message': message,
            'timestamp': timestamp
        })

        return jsonify({"status": "Mensaje enviado"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Obtener mensajes de un canal
@app.route("/messages/<channel>", methods=["GET"])
def obtener_mensajes(channel):
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT username, message, timestamp FROM messages WHERE channel=%s ORDER BY id DESC LIMIT 50",
            (channel,)
        )
        mensajes = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify(mensajes[::-1]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Interfaz simple para probar el chat
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Chat con canal automático</title>
<script src="https://js.pusher.com/8.2/pusher.min.js"></script>
<style>
body {
  font-family: Arial, sans-serif;
  background: #f4f4f4;
  margin: 0;
  padding: 20px;
}
#chat-area { display:none; }
#chat-box {
  background: white;
  border: 1px solid #ccc;
  height: 300px;
  overflow-y: auto;
  padding: 10px;
  margin-top: 10px;
}
.message { margin-bottom: 8px; }
.message strong { color: #5a2ca0; }
</style>
</head>
<body>
<h2>💬 Chat con canal automático</h2>
<p>Ingresa tu nombre y obtendrás un canal único.</p>

<input id="username" placeholder="Tu nombre">
<button onclick="joinChat()">Unirme</button>

<div id="chat-area">
  <h3 id="canal"></h3>
  <div id="chat-box"></div>
  <input id="message" placeholder="Escribe un mensaje...">
  <button onclick="sendMessage()">Enviar</button>
</div>

<script>
let currentChannel = null;
let pusher = new Pusher('b6bbf62d682a7a882f41', { cluster: 'mt1' });
let channelPusher = null;
let username = "";

async function joinChat() {
    username = document.getElementById("username").value.trim();
    if (!username) return alert("Ingresa un nombre primero");
    const res = await fetch("/join", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({username})
    });
    const data = await res.json();
    if (data.channel) {
        currentChannel = data.channel;
        document.getElementById("chat-area").style.display = "block";
        document.getElementById("canal").innerText = "Tu canal: #" + currentChannel;
        subscribeChannel(currentChannel);
        loadMessages(currentChannel);
    } else {
        alert("Error al crear canal");
    }
}

async function loadMessages(channel) {
    const res = await fetch("/messages/" + channel);
    const msgs = await res.json();
    const box = document.getElementById("chat-box");
    box.innerHTML = msgs.map(m => "<div class='message'><strong>" + m.username + ":</strong> " + m.message + "</div>").join("");
    box.scrollTop = box.scrollHeight;
}

async function sendMessage() {
    const message = document.getElementById("message").value.trim();
    if (!message) return;
    await fetch("/send", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({sender: username, message, channel: currentChannel})
    });
    document.getElementById("message").value = "";
}

function subscribeChannel(channel) {
    channelPusher = pusher.subscribe(channel);
    channelPusher.bind('new-message', data => {
        const box = document.getElementById("chat-box");
        box.innerHTML += "<div class='message'><strong>" + data.sender + ":</strong> " + data.message + "</div>";
        box.scrollTop = box.scrollHeight;
    });
}
</script>
</body>
</html>
""")


# ✅ Endpoint de prueba
@app.route("/ping")
def ping():
    return jsonify({"status": "Servidor Flask activo ✅"}), 200


if __name__ == "__main__":
    app.run(debug=True)
