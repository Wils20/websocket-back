from flask import Flask, request, jsonify
from flask_cors import CORS
import pusher
import mysql.connector
from datetime import datetime

app = Flask(__name__)

# Configurar CORS
CORS(app, origins=[
    "https://websocket-front-wil-git-master-wils20s-projects.vercel.app",
    "https://websocket-front-wil2-git-master-wils20s-projects.vercel.app"
])

# Configurar Pusher
pusher_client = pusher.Pusher(
    app_id='2062323',
    key='b6bbf62d682a7a882f41',
    secret='36605cfd7b0a8de9935b',
    cluster='mt1',
    ssl=True
)

# ✅ Conexión a MySQL
def get_db_connection():
    return mysql.connector.connect(
        host="mysql-wilson.alwaysdata.net",  # <-- cambia esto
        user="wilson",                      # <-- tu usuario
        password="wilsonCMV20_",           # <-- tu contraseña
        database="wilson_db"            # <-- tu base de datos
    )

# ✅ Guardar mensaje y enviar por Pusher
@app.route("/", methods=["POST"])
def enviar_mensaje():
    try:
        data = request.get_json()

        username = data.get("username")
        message = data.get("message")

        if not username or not message:
            return jsonify({"error": "Faltan campos 'username' o 'message'"}), 400

        # Guardar mensaje en la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (username, message) VALUES (%s, %s)",
            (username, message)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Obtener hora actual para enviar también por Pusher
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Enviar mensaje con Pusher
        pusher_client.trigger('my-channel', 'my-event', {
            'username': username,
            'message': message,
            'timestamp': timestamp
        })

        return jsonify({"status": "Mensaje guardado y enviado correctamente"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ✅ Obtener mensajes guardados
@app.route("/messages", methods=["GET"])
def obtener_mensajes():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username, message, timestamp FROM messages ORDER BY id DESC")
        mensajes = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify(mensajes), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)






