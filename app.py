from flask import Flask, request, jsonify
from flask_cors import CORS
import pusher
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# 🔹 CORS: permite tus frontends (vercel)
CORS(app, origins=[
    "https://websocket-front-wil-git-master-wils20s-projects.vercel.app",
    "https://websocket-front-wil2-git-master-wils20s-projects.vercel.app"
])

# 🔹 Conexión a MySQL (AlwaysData)
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

        if not username or not message:
            return jsonify({"error": "Missing 'sender' or 'message'"}), 400

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO messages (username, message, timestamp) VALUES (%s, %s, %s)",
            (username, message, timestamp)
        )
        db.commit()
        cursor.close()
        db.close()

        # Enviar mensaje a Pusher
        pusher_client.trigger('my-channel', 'my-event', {
            'sender': username,
            'message': message,
            'timestamp': timestamp
        })

        return jsonify({"status": "Mensaje guardado y enviado correctamente"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Ruta para obtener mensajes guardados
@app.route("/messages", methods=["GET"])
def obtener_mensajes():
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT username, message, timestamp FROM messages ORDER BY id ASC")
        mensajes = cursor.fetchall()
        cursor.close()
        db.close()
        return jsonify(mensajes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Ruta raíz para verificar conexión
@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Servidor Flask activo ✅"}), 200


if __name__ == "__main__":
    app.run(debug=True)
