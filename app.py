from flask import Flask, request, jsonify
from flask_cors import CORS
import pusher

app = Flask(__name__)

# Configuración de CORS para permitir solo tu dominio
CORS(app, origins=["https://websocket-front-wil-git-master-wils20s-projects.vercel.app"])
CORS(app, origins=["https://websocket-front-wil2-git-master-wils20s-projects.vercel.app"])

# Inicialización de Pusher
pusher_client = pusher.Pusher(
    app_id='2062323',
    key='b6bbf62d682a7a882f41',
    secret='36605cfd7b0a8de9935b',
    cluster='mt1',
    ssl=True
)

@app.route("/", methods=["POST"])
def hola_mundo():
    try:
        data = request.get_json()

        if not data or 'message' not in data or 'sender' not in data:
            return jsonify({"error": "Missing 'message' or 'sender'"}), 400

        # Enviar mensaje con remitente a Pusher
        pusher_client.trigger('my-channel', 'my-event', {
            'message': data["message"],
            'sender': data["sender"]
        })

        return jsonify({"status": "Message sent successfully"}), 200

    except Exception as e:
        # En caso de error con Pusher o cualquier otra excepción
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
