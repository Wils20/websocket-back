from flask import Flask, request
from flask_cors import CORS
import pusher

app = Flask(__name__)
CORS(app)

@app.route("/", methods=["POST"])
def hola_mundo():
    data = request.get_json()

    pusher_client = pusher.Pusher(
        app_id='2062323',
        key='b6bbf62d682a7a882f41',
        secret='36605cfd7b0a8de9935b',
        cluster='mt1',
        ssl=True
    )

    # Enviar mensaje con remitente
    pusher_client.trigger('my-channel', 'my-event', {
        'message': data["message"],
        'sender': data["sender"]
    })

    return "OK"

if __name__ == "__main__":
    app.run(debug=True)
