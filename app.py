from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import pusher
import mysql.connector 
from datetime import datetime

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

# ✅ Ruta para enviar mensaje
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

        # Enviar mensaje en tiempo real por Pusher
        pusher_client.trigger(channel, 'new-message', {
            'sender': username,
            'message': message,
            'timestamp': timestamp
        })

        return jsonify({"status": "Mensaje enviado"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Ruta para obtener historial de un canal
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
        return jsonify(mensajes[::-1]), 200  # Revertir para mostrar en orden cronológico
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Panel administrativo HTML integrado
@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Panel de Canales - Chat Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://js.pusher.com/8.2/pusher.min.js"></script>
</head>
<body class="bg-gray-100">
    <div class="flex h-screen">
        <!-- Panel lateral -->
        <aside class="w-1/4 bg-white shadow-lg p-4 overflow-y-auto">
            <h2 class="text-xl font-bold mb-4 text-purple-600">📡 Canales</h2>
            <div id="channel-list" class="space-y-2">
                <button onclick="selectChannel('general')" class="w-full text-left p-2 rounded bg-purple-100 hover:bg-purple-200">general</button>
                <button onclick="selectChannel('ventas')" class="w-full text-left p-2 rounded hover:bg-gray-200">ventas</button>
                <button onclick="selectChannel('soporte')" class="w-full text-left p-2 rounded hover:bg-gray-200">soporte</button>
                <button onclick="selectChannel('marketing')" class="w-full text-left p-2 rounded hover:bg-gray-200">marketing</button>
                <button onclick="selectChannel('gmail.com')" class="w-full text-left p-2 rounded hover:bg-gray-200">gmail.com</button>
            </div>
        </aside>

        <!-- Área de chat -->
        <main class="flex-1 flex flex-col">
            <div class="p-4 bg-white shadow flex justify-between items-center">
                <h2 id="channel-name" class="text-lg font-semibold text-purple-700">Selecciona un canal</h2>
            </div>

            <div id="chat-box" class="flex-1 p-4 overflow-y-auto"></div>

            <div class="p-4 bg-white flex">
                <input id="username" class="border rounded w-1/5 p-2 mr-2" placeholder="Tu nombre">
                <input id="message" class="border rounded w-3/5 p-2 mr-2" placeholder="Escribe un mensaje...">
                <button onclick="sendMessage()" class="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700">Enviar</button>
            </div>
        </main>
    </div>

<script>
let currentChannel = null;

// 🧭 Seleccionar canal
function selectChannel(channel) {
    currentChannel = channel;
    document.getElementById("channel-name").innerText = "#" + channel;
    document.getElementById("chat-box").innerHTML = "";
    loadMessages(channel);
    subscribeChannel(channel);
}

// 🔁 Cargar historial del canal
async function loadMessages(channel) {
    const res = await fetch(`/messages/${channel}`);
    const messages = await res.json();
    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";

    messages.forEach(msg => {
        const msgDiv = document.createElement("div");
        msgDiv.className = "bg-gray-50 p-2 rounded mb-1";
        msgDiv.innerHTML = `<strong>${msg.username}:</strong> ${msg.message} <small class="text-gray-400">${msg.timestamp}</small>`;
        chatBox.appendChild(msgDiv);
    });

    chatBox.scrollTop = chatBox.scrollHeight;
}

// 🚀 Enviar mensaje
async function sendMessage() {
    const sender = document.getElementById("username").value.trim();
    const message = document.getElementById("message").value.trim();

    if (!sender || !message || !currentChannel) {
        alert("Completa todos los campos y selecciona un canal.");
        return;
    }

    await fetch("/send", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ sender, message, channel: currentChannel })
    });

    document.getElementById("message").value = "";
}

// ⚡ Conectar con Pusher para mensajes instantáneos
let pusher = new Pusher('b6bbf62d682a7a882f41', { cluster: 'mt1' });
let channelPusher = null;

function subscribeChannel(channel) {
    if (channelPusher) channelPusher.unbind_all();

    channelPusher = pusher.subscribe(channel);
    channelPusher.bind('new-message', function(data) {
        if (currentChannel === channel) {
            const chatBox = document.getElementById("chat-box");
            const msgDiv = document.createElement("div");
            msgDiv.className = "bg-purple-50 p-2 rounded mb-1";
            msgDiv.innerHTML = `<strong>${data.sender}:</strong> ${data.message} <small class="text-gray-400">${data.timestamp}</small>`;
            chatBox.appendChild(msgDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    });
}
</script>
</body>
</html>
""")

# ✅ Verificación del servidor
@app.route("/ping")
def ping():
    return jsonify({"status": "Servidor Flask activo ✅"}), 200

if __name__ == "__main__":
    app.run(debug=True)
