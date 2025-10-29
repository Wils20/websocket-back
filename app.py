from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import pusher
import mysql.connector
from datetime import datetime
import time

app = Flask(__name__)

# 🔓 CORS (para frontends de Vercel)
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

# 🔹 Inicializar Pusher
pusher_client = pusher.Pusher(
    app_id='2062323',
    key='b6bbf62d682a7a882f41',
    secret='36605cfd7b0a8de9935b',
    cluster='mt1',
    ssl=True
)

# 🧠 Caché en memoria para historial de mensajes
cache = {}
CACHE_TTL = 5  # segundos (refresca cada 5s)

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

        # Guardar en DB
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO messages (username, message, channel, timestamp) VALUES (%s, %s, %s, %s)",
            (username, message, channel, timestamp)
        )
        db.commit()
        cursor.close()
        db.close()

        # ❌ Invalida caché del canal
        cache.pop(channel, None)

        # Enviar mensaje en tiempo real
        pusher_client.trigger(channel, 'new-message', {
            'sender': username,
            'message': message,
            'timestamp': timestamp
        })

        return jsonify({"status": "Mensaje enviado"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Obtener historial del canal (con caché)
@app.route("/messages/<channel>", methods=["GET"])
def obtener_mensajes(channel):
    try:
        now = time.time()

        # ⚡ Si hay caché fresco, úsalo
        if channel in cache and (now - cache[channel]["time"]) < CACHE_TTL:
            return jsonify(cache[channel]["data"]), 200

        # Sino, traer desde la DB
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT username, message, timestamp FROM messages WHERE channel=%s ORDER BY id DESC LIMIT 50",
            (channel,)
        )
        mensajes = cursor.fetchall()
        cursor.close()
        db.close()

        mensajes_ordenados = mensajes[::-1]

        # 🧠 Guardar en caché
        cache[channel] = {"data": mensajes_ordenados, "time": now}

        return jsonify(mensajes_ordenados), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Verificación del servidor
@app.route("/ping")
def ping():
    return jsonify({"status": "Servidor Flask activo ✅"}), 200


# ✅ Panel HTML (sin cambios)
@app.route("/")
def index():
    return render_template_string("""<!DOCTYPE html>
<html lang='es'>
<head>
  <meta charset='UTF-8'>
  <title>Panel Chat</title>
  <script src='https://cdn.tailwindcss.com'></script>
  <script src='https://js.pusher.com/8.2/pusher.min.js'></script>
</head>
<body class='bg-gray-100'>
  <div class='flex h-screen'>
    <aside class='w-1/4 bg-white shadow-lg p-4'>
      <h2 class='text-xl font-bold mb-4 text-purple-600'>📡 Canales</h2>
      <button onclick="selectChannel('general')" class='block w-full p-2 bg-purple-100 rounded mb-2'>general</button>
      <button onclick="selectChannel('ventas')" class='block w-full p-2 hover:bg-gray-200 rounded mb-2'>ventas</button>
      <button onclick="selectChannel('soporte')" class='block w-full p-2 hover:bg-gray-200 rounded mb-2'>soporte</button>
    </aside>
    <main class='flex-1 flex flex-col'>
      <div class='p-4 bg-white shadow'>
        <h2 id='channel-name' class='text-lg font-semibold text-purple-700'>Selecciona un canal</h2>
      </div>
      <div id='chat-box' class='flex-1 p-4 overflow-y-auto'></div>
      <div class='p-4 bg-white flex'>
        <input id='username' class='border rounded w-1/5 p-2 mr-2' placeholder='Tu nombre'>
        <input id='message' class='border rounded w-3/5 p-2 mr-2' placeholder='Mensaje...'>
        <button onclick='sendMessage()' class='bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700'>Enviar</button>
      </div>
    </main>
  </div>

<script>
let currentChannel = null;
let pusher = new Pusher('b6bbf62d682a7a882f41', { cluster: 'mt1' });
let channelPusher = null;

async function selectChannel(channel) {
  currentChannel = channel;
  document.getElementById("channel-name").innerText = "#" + channel;
  document.getElementById("chat-box").innerHTML = "";
  await loadMessages(channel);
  subscribeChannel(channel);
}

async function loadMessages(channel) {
  const res = await fetch(`/messages/${channel}`);
  const messages = await res.json();
  const chatBox = document.getElementById("chat-box");
  chatBox.innerHTML = "";
  messages.forEach(msg => {
    const div = document.createElement("div");
    div.className = "bg-gray-50 p-2 rounded mb-1";
    div.innerHTML = `<strong>${msg.username}:</strong> ${msg.message} <small class='text-gray-400'>${msg.timestamp}</small>`;
    chatBox.appendChild(div);
  });
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function sendMessage() {
  const sender = document.getElementById("username").value.trim();
  const message = document.getElementById("message").value.trim();
  if (!sender || !message || !currentChannel) return alert("Completa los campos y el canal.");
  await fetch("/send", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ sender, message, channel: currentChannel })
  });
  document.getElementById("message").value = "";
}

function subscribeChannel(channel) {
  if (channelPusher) channelPusher.unbind_all();
  channelPusher = pusher.subscribe(channel);
  channelPusher.bind('new-message', data => {
    if (currentChannel === channel) {
      const chatBox = document.getElementById("chat-box");
      const div = document.createElement("div");
      div.className = "bg-purple-50 p-2 rounded mb-1";
      div.innerHTML = `<strong>${data.sender}:</strong> ${data.message} <small class='text-gray-400'>${data.timestamp}</small>`;
      chatBox.appendChild(div);
      chatBox.scrollTop = chatBox.scrollHeight;
    }
  });
}
</script>
</body></html>""")


if __name__ == "__main__":
    app.run(debug=True)
