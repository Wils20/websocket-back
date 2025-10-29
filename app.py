from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import mysql.connector
from datetime import datetime
import os

app = Flask(__name__, static_folder="static")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# 🔹 Conexión a MySQL
def get_db_connection():
    return mysql.connector.connect(
        host="mysql-wilson.alwaysdata.net",
        user="wilson",
        password="wilsonCMV20_",
        database="wilson_db"
    )

# 🔹 Guardar mensaje y emitirlo a los clientes
@socketio.on("send_message")
def handle_message(data):
    username = data.get("sender")
    message = data.get("message")
    channel = data.get("channel", "general")

    if not username or not message:
        return

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

    emit("new_message", {
        "sender": username,
        "message": message,
        "timestamp": timestamp,
        "channel": channel
    }, broadcast=True)

# 🔹 Obtener historial rápido
@app.route("/messages/<channel>")
def get_messages(channel):
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT username, message, timestamp FROM messages WHERE channel=%s ORDER BY id DESC LIMIT 50",
        (channel,)
    )
    messages = cursor.fetchall()
    cursor.close()
    db.close()
    return jsonify(messages[::-1])

# 🔹 Servir el index.html
@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")

# 🔹 Verificación
@app.route("/ping")
def ping():
    return jsonify({"status": "Servidor Flask activo ✅"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False)
