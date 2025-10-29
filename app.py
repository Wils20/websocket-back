from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import pusher
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# 🔓 CORS (para frontends)
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

# 🔹 Pusher
pusher_client = pusher.Pusher(
    app_id='2062323',
    key='b6bbf62d682a7a882f41',
    secret='36605cfd7b0a8de9935b',
    cluster='mt1',
    ssl=True
)

# ✅ Enviar mensaje
@app.route("/send", methods=["POST"])
def enviar_mensaje():
    try:
        data = request.get_json()
        username = data.get("sender")
        message = data.get("message")
        channel = data.get("channel", "general")

        if not username or not message:
            return jsonify({"error": "Missing 'sender' or 'message'"}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO messages (username, message, channel, timestamp) VALUES (%s, %s, %s, %s)",
            (username, message, channel, timestamp)
        )
        db.commit()
        cursor.close()
        db.close()

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


# ✅ HTML del panel administrativo (sin Tailwind)
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Panel de Canales</title>
<script src="https://js.pusher.com/8.2/pusher.min.js"></script>
<style>
body {
  margin: 0;
  font-family: Arial, sans-serif;
  background: #f4f4f4;
  display: flex;
  height: 100vh;
}
aside {
  width: 25%;
  background: #fff;
  border-right: 1px solid #ccc;
  overflow-y: auto;
  padding: 20px;
}
aside h2 {
  color: #5a2ca0;
  font-size: 20px;
  margin-bottom: 10px;
}
aside button {
  display: block;
  width: 100%;
  background: #eee;
  border: none;
  padding: 10px;
  margin-bottom: 5px;
  text-align: left;
  cursor: pointer;
  border-radius: 5px;
  transition: background 0.2s;
}
aside button:hover {
  background: #ddd;
}
main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
header {
  background: #fff;
  border-bottom: 1px solid #ccc;
  padding: 10px 20px;
  font-weight: bold;
  color: #5a2ca0;
}
#chat-box {
  flex: 1;
  padding: 15px;
  overflow-y: auto;
  background: #fafafa;
}
.message {
  background: #fff;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
}
.message strong {
  color: #333;
}
.message small {
  color: #888;
  font-size: 11px;
}
footer {
  background: #fff;
  padding: 10px;
  display: flex;
  border-top: 1px solid #ccc;
}
footer input {
  padding: 8px;
  margin-right: 5px;
  border: 1px solid #ccc;
  border-radius: 4px;
}
footer input#username {
  width: 20%;
}
footer input#message {
  flex: 1;
}
footer button {
  background: #5a2ca0;
  color: white;
  border: none;
  padding: 8px 15px;
  border-radius: 4px;
  cursor: pointer;
}
footer button:hover {
  background: #4b2386;
}
</style>
</head>
<body>
  <aside>
    <h2>📡 Canales</h2>
    <button onclick="selectChannel('general')">general</button>
    <button onclick="selectChannel('ventas')">ventas</button>
    <button onclick="selectChannel('soporte')">soporte</button>
    <button onclick="selectChannel('marketing')">marketing</button>
    <button onclick="selectChannel('gmail.com')">gmail.com</button>
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
let pusher = new Pusher('b6bbf62d682a7a882f41', { cluster: 'mt1' });
let channelPusher = null;

function selectChannel(channel) {
    currentChannel = channel;
    document.getElementById("channel-name").innerText = "#" + channel;
    document.getElementById("chat-box").innerHTML = "<p>Cargando mensajes...</p>";
    loadMessages(channel);
    subscribeChannel(channel);
}

async function loadMessages(channel) {
    try {
        const res = await fetch(`/messages/${channel}`);
        if (!res.ok) throw new Error("Error al obtener mensajes");
        const messages = await res.json();
        renderMessages(messages);
    } catch (e) {
        document.getElementById("chat-box").innerHTML = "<p style='color:red;'>Error al cargar mensajes</p>";
    }
}

function renderMessages(messages) {
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";
    messages.forEach(msg => {
        const msgDiv = document.createElement("div");
        msgDiv.className = "message";
        msgDiv.innerHTML = `<strong>${msg.username}:</strong> ${msg.message} <br><small>${msg.timestamp}</small>`;
        chatBox.appendChild(msgDiv);
    });
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
    const sender = document.getElementById("username").value.trim();
    const message = document.getElementById("message").value.trim();
    if (!sender || !message || !currentChannel) {
        alert("Completa todos los campos y selecciona un canal.");
        return;
    }
    await fetch("/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender, message, channel: currentChannel })
    });
    document.getElementById("message").value = "";
}

function subscribeChannel(channel) {
    if (channelPusher) {
        channelPusher.unbind_all();
        pusher.unsubscribe(channelPusher.name);
    }
    channelPusher = pusher.subscribe(channel);
    channelPusher.bind('new-message', data => {
        if (currentChannel === channel) {
            const chatBox = document.getElementById("chat-box");
            const msgDiv = document.createElement("div");
            msgDiv.className = "message";
            msgDiv.style.background = "#f5e8ff";
            msgDiv.innerHTML = `<strong>${data.sender}:</strong> ${data.message} <br><small>${data.timestamp}</small>`;
            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    });
}
</script>
</body>
</html>
""")


@app.route("/ping")
def ping():
    return jsonify({"status": "Servidor Flask activo ✅"}), 200


if __name__ == "__main__":
    app.run(debug=True)
