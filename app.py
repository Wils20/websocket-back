from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import pusher
import mysql.connector
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=[
    "https://websocket-front-wil.vercel.app",
    "https://websocket-front2-wil.vercel.app",
    "https://websocket-front-wil-git-master-wils20s-projects.vercel.app",
    "https://websocket-front2-wil-git-master-wils20s-projects.vercel.app",
    "http://localhost:5000"  # para pruebas locales
])

# 🔹 Conexión a MySQL
def get_db_connection():
    return mysql.connector.connect(
        host="mysql-wilson.alwaysdata.net",
        user="wilson",
        password="wilsonCMV20_",
        database="wilson_db"
    )

# 🔹 Inicializar Pusher
pusher_client = pusher.Pusher(
    app_id='2062323',
    key='b6bbf62d682a7a882f41',
    secret='36605cfd7b0a8de9935b',
    cluster='mt1',
    ssl=True
)

# ✅ Ruta para enviar mensajes
@app.route("/send", methods=["POST"])
def enviar_mensaje():
    try:
        data = request.get_json()
        username = data.get("sender")
        message = data.get("message")
        channel = data.get("channel")

        if not username or not message or not channel:
            return jsonify({"error": "Faltan datos"}), 400

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

        # Enviar a Pusher
        pusher_client.trigger('my-channel', 'my-event', {
            'sender': username,
            'message': message,
            'channel': channel,
            'timestamp': timestamp
        })

        return jsonify({"status": "Mensaje guardado y enviado"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Ruta para obtener mensajes por canal
@app.route("/messages", methods=["GET"])
def obtener_mensajes():
    try:
        channel = request.args.get("channel")
        if not channel:
            return jsonify({"error": "Falta el parámetro 'channel'"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT username, message, timestamp FROM messages WHERE channel = %s ORDER BY id ASC",
            (channel,)
        )
        mensajes = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify(mensajes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Ruta del panel administrativo
@app.route("/", methods=["GET"])
def home():
    html = """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Panel de Canales - Chat Admin</title>
  <script src="https://js.pusher.com/7.2/pusher.min.js"></script>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: "Segoe UI", Tahoma, sans-serif; }
    body { height: 100vh; display: flex; background: #f2f3f5; }
    .container { display: flex; width: 100%; }
    .sidebar { width: 260px; background: #ffffff; border-right: 1px solid #ddd; padding: 20px; }
    .sidebar h2 { font-size: 18px; margin-bottom: 10px; color: #444; }
    .sidebar ul { list-style: none; }
    .sidebar li { padding: 10px; margin-bottom: 5px; background: #f8f9fa; border-radius: 8px; cursor: pointer; transition: background 0.2s; }
    .sidebar li:hover, .sidebar li.active { background: #dbeafe; color: #1e40af; }
    .chat-section { flex: 1; display: flex; flex-direction: column; }
    .chat-header { padding: 15px; border-bottom: 1px solid #ddd; background: #ffffff; }
    .chat-messages { flex: 1; padding: 20px; overflow-y: auto; background: #f1f5f9; }
    .message { margin-bottom: 15px; }
    .message strong { color: #1d4ed8; }
    .message .time { font-size: 0.8em; color: gray; margin-left: 5px; }
    .chat-input { display: flex; border-top: 1px solid #ddd; background: #ffffff; padding: 10px; }
    .chat-input input { padding: 10px; margin-right: 5px; border: 1px solid #ccc; border-radius: 8px; flex: 1; }
    .chat-input button { background: #1d4ed8; color: white; border: none; padding: 10px 15px; border-radius: 8px; cursor: pointer; }
    .chat-input button:hover { background: #2563eb; }
    .placeholder { color: gray; text-align: center; margin-top: 50px; }
  </style>
</head>
<body>
  <div class="container">
    <aside class="sidebar">
      <h2>📡 Canales</h2>
      <ul id="channelList">
        <li data-channel="canal1@gmail.com">canal1@gmail.com</li>
        <li data-channel="canal2@gmail.com">canal2@gmail.com</li>
        <li data-channel="soporte@gmail.com">soporte@gmail.com</li>
      </ul>
    </aside>

    <main class="chat-section">
      <div class="chat-header">
        <h2 id="activeChannel">Selecciona un canal</h2>
      </div>

      <div id="messages" class="chat-messages">
        <p class="placeholder">Selecciona un canal para ver el historial...</p>
      </div>

      <div class="chat-input">
        <input type="text" id="sender" placeholder="Tu nombre" />
        <input type="text" id="messageInput" placeholder="Escribe un mensaje..." />
        <button id="sendBtn">Enviar</button>
      </div>
    </main>
  </div>

  <script>
    const pusher = new Pusher("b6bbf62d682a7a882f41", { cluster: "mt1" });
    let currentChannel = null;
    const channelList = document.getElementById("channelList");
    const messageContainer = document.getElementById("messages");
    const activeChannel = document.getElementById("activeChannel");
    const senderInput = document.getElementById("sender");
    const messageInput = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendBtn");

    channelList.addEventListener("click", async (e) => {
      if (e.target.tagName === "LI") {
        document.querySelectorAll(".sidebar li").forEach(li => li.classList.remove("active"));
        e.target.classList.add("active");
        currentChannel = e.target.dataset.channel;
        activeChannel.textContent = currentChannel;
        await loadMessages(currentChannel);
      }
    });

    async function loadMessages(channel) {
      messageContainer.innerHTML = "<p class='placeholder'>Cargando mensajes...</p>";
      const res = await fetch(`/messages?channel=${channel}`);
      const data = await res.json();
      messageContainer.innerHTML = "";
      data.forEach(msg => {
        const div = document.createElement("div");
        div.classList.add("message");
        div.innerHTML = `<strong>${msg.username}</strong>: ${msg.message} <span class="time">(${msg.timestamp})</span>`;
        messageContainer.appendChild(div);
      });
    }

    sendBtn.addEventListener("click", async () => {
      const sender = senderInput.value.trim();
      const message = messageInput.value.trim();
      if (!sender || !message || !currentChannel) {
        alert("Completa tu nombre, el mensaje y selecciona un canal.");
        return;
      }
      await fetch("/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sender, message, channel: currentChannel })
      });
      messageInput.value = "";
    });

    const pusherChannel = pusher.subscribe("my-channel");
    pusherChannel.bind("my-event", function (data) {
      if (data.channel === currentChannel) {
        const div = document.createElement("div");
        div.classList.add("message");
        div.innerHTML = `<strong>${data.sender}</strong>: ${data.message} <span class="time">(${data.timestamp})</span>`;
        messageContainer.appendChild(div);
        messageContainer.scrollTop = messageContainer.scrollHeight;
      }
    });
  </script>
</body>
</html>
"""
    return Response(html, mimetype="text/html")


if __name__ == "__main__":
    app.run(debug=True)
