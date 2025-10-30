from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import pusher
from mysql.connector import pooling
from datetime import datetime
import threading

app = Flask(__name__)
CORS(app)  # Público para cualquier dominio

# ==============================================
# 🔹 MYSQL CONEXIÓN OPTIMIZADA (POOLING)
# ==============================================
DB_CONFIG = {
    "host": "mysql-wilson.alwaysdata.net",
    "user": "wilson",
    "password": "wilsonCMV20_",
    "database": "wilson_db",
    "connection_timeout": 3
}
cnxpool = pooling.MySQLConnectionPool(pool_name="mypool", pool_size=10, **DB_CONFIG)

def get_db_connection():
    return cnxpool.get_connection()

# ==============================================
# 🔹 PUSHER CONFIG
# ==============================================
pusher_client = pusher.Pusher(
    app_id="2062323",
    key="b6bbf62d682a7a882f41",
    secret="36605cfd7b0a8de9935b",
    cluster="mt1",
    ssl=True
)

# ==============================================
# 🔹 FUNCIÓN AUX: crear canal ascendente (canal1, canal2...)
# ==============================================
def generar_canal_nuevo(db, cursor):
    """
    Inserta un nuevo canal con nombre canal1, canal2, ...
    Devuelve el nombre creado.
    """
    # obtener total actual
    cursor.execute("SELECT COUNT(*) AS total FROM channels")
    row = cursor.fetchone()
    total = row["total"] if row and "total" in row else 0
    nuevo_num = total + 1
    nuevo_nombre = f"canal{nuevo_num}"
    cursor.execute("INSERT INTO channels (name) VALUES (%s)", (nuevo_nombre,))
    db.commit()
    return nuevo_nombre

# ==============================================
# 🟢 JOIN - Cliente se une y crea canal nuevo si no tiene
# ==============================================
@app.route("/join", methods=["POST"])
def join_channel():
    data = request.get_json() or {}
    username = data.get("username")
    if not username:
        return jsonify({"error": "Nombre requerido"}), 400

    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Verificar si el usuario ya tiene canal
        cursor.execute("SELECT channel FROM conversations WHERE username=%s", (username,))
        existing = cursor.fetchone()

        if existing and existing.get("channel"):
            channel = existing["channel"]
            created = False
        else:
            channel = generar_canal_nuevo(db, cursor)
            cursor.execute("INSERT INTO conversations (username, channel) VALUES (%s, %s)", (username, channel))
            db.commit()
            created = True

        # Notificar admin sólo si se creó canal nuevo
        if created:
            try:
                pusher_client.trigger("admin_global", "nuevo-canal", {"channel": channel})
            except Exception as e:
                # no romper el flujo si pusher falla
                print("Warning: pusher admin_global trigger failed:", e)

        return jsonify({"channel": channel}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if db is not None:
            db.close()

# ==============================================
# 💬 ENVIAR MENSAJE (asincrónico para menor latencia)
# ==============================================
@app.route("/send", methods=["POST"])
def enviar_mensaje():
    data = request.get_json() or {}
    username = data.get("sender")
    message = data.get("message")
    channel = data.get("channel")

    if not username or not message or not channel:
        return jsonify({"error": "Campos incompletos"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def guardar_y_emitir(s, m, ch, ts):
        db2 = None
        cursor2 = None
        try:
            db2 = get_db_connection()
            cursor2 = db2.cursor()
            cursor2.execute(
                "INSERT INTO messages (username, message, channel, timestamp) VALUES (%s, %s, %s, %s)",
                (s, m, ch, ts)
            )
            db2.commit()
            # emitir en pusher
            try:
                pusher_client.trigger(ch, "new-message", {"sender": s, "message": m, "timestamp": ts})
            except Exception as e:
                print("Warning: pusher trigger failed:", e)
        except Exception as ex:
            print("Error guardar_y_emitir:", ex)
        finally:
            if cursor2 is not None:
                cursor2.close()
            if db2 is not None:
                db2.close()

    # lanzar hilo para no bloquear la respuesta
    threading.Thread(target=guardar_y_emitir, args=(username, message, channel, timestamp), daemon=True).start()

    # respuesta inmediata
    return jsonify({"status": "Enviado"}), 200

# ==============================================
# 📜 HISTORIAL DE MENSAJES (traer últimos N rápido)
# ==============================================
@app.route("/messages/<channel>", methods=["GET"])
def obtener_mensajes(channel):
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Tomamos los últimos 100 por id descendente (más rápido con índice), luego invertimos en Python
        cursor.execute("""
            SELECT username, message, timestamp
            FROM messages
            WHERE channel = %s
            ORDER BY id DESC
            LIMIT 100
        """, (channel,))
        rows = cursor.fetchall() or []
        rows.reverse()  # ahora están en orden ascendente (más natural)
        return jsonify(rows), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor is not None:
            cursor.close()
        if db is not None:
            db.close()

# ==============================================
# 🧩 PANEL ADMIN (recibe nuevos canales en vivo)
# ==============================================
@app.route("/")
def index():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT name FROM channels ORDER BY id ASC")
        canales = [row["name"] for row in cursor.fetchall()]
    finally:
        if cursor is not None:
            cursor.close()
        if db is not None:
            db.close()

    botones = "".join([f"<button id='btn_{c}' onclick=\"selectChannel('{c}')\">{c}</button>" for c in canales])

    return render_template_string(f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Panel Admin Chat</title>
<script src="https://js.pusher.com/8.2/pusher.min.js"></script>
<style>
body {{ margin:0; font-family:Arial; display:flex; height:100vh; background:#f5f6fa; }}
aside {{ width:25%; background:white; border-right:1px solid #ddd; padding:10px; overflow-y:auto; }}
aside button {{ width:100%; margin:5px 0; padding:8px; border:none; background:#eee; cursor:pointer; border-radius:6px; }}
aside button:hover {{ background:#dcdcdc; }}
main {{ flex:1; display:flex; flex-direction:column; }}
header {{ background:#5a2ca0; color:white; padding:10px; font-weight:bold; }}
#chat-box {{ flex:1; overflow-y:auto; padding:10px; background:#fafafa; display:flex; flex-direction:column; }}
.message {{ border-radius:8px; padding:8px; margin-bottom:6px; max-width:60%; }}
.user {{ background:#e0e7ff; align-self:flex-start; }}
.admin {{ background:#5a2ca0; color:white; align-self:flex-end; }}
footer {{ background:white; border-top:1px solid #ccc; padding:10px; display:flex; }}
footer input {{ flex:1; padding:8px; border:1px solid #ccc; border-radius:4px; }}
footer button {{ background:#5a2ca0; color:white; border:none; padding:8px 15px; border-radius:4px; margin-left:5px; cursor:pointer; }}
footer button:hover {{ background:#4a1f82; }}
</style>
</head>
<body>
  <aside>
    <h2>Canales Activos</h2>
    <div id="channel-list">{botones}</div>
  </aside>
  <main>
    <header id="channel-name">Selecciona un canal</header>
    <div id="chat-box"></div>
    <footer>
      <input id="message" placeholder="Escribe un mensaje...">
      <button onclick="sendMessage()">Enviar</button>
    </footer>
  </main>

<script>
let currentChannel = null;
let pusher = new Pusher('b6bbf62d682a7a882f41', {{cluster:'mt1'}});
let activeSub = null;

// Suscripción global del admin para recibir nuevos canales en vivo
let adminGlobal = pusher.subscribe("admin_global");
adminGlobal.bind("nuevo-canal", function(data) {{
  const c = data.channel;
  // si no existe el botón, crearlo
  if (!document.getElementById('btn_' + c)) {{
    const btn = document.createElement('button');
    btn.id = 'btn_' + c;
    btn.textContent = c;
    btn.onclick = function() {{ selectChannel(c); }};
    document.getElementById("channel-list").appendChild(btn);
  }}
}});

async function selectChannel(c) {{
  currentChannel = c;
  document.getElementById("channel-name").innerText = "Canal: " + c;
  const res = await fetch(`/messages/${{c}}`);
  const messages = await res.json();
  renderMessages(messages);

  // subscribir al canal seleccionado
  if (activeSub) pusher.unsubscribe(activeSub.name);
  activeSub = pusher.subscribe(c);
  activeSub.bind("new-message", function(d) {{ addMessage(d.sender, d.message, d.timestamp); }});
}}

function renderMessages(msgs) {{
  const box = document.getElementById("chat-box");
  box.innerHTML = "";
  msgs.forEach(m => addMessage(m.username, m.message, m.timestamp));
  box.scrollTop = box.scrollHeight;
}}

function addMessage(u, m, t) {{
  const div = document.createElement("div");
  div.className = "message " + (u === "ADMIN" ? "admin" : "user");
  div.innerHTML = `<strong>${{u}}</strong>: ${{m}}<div style='font-size:10px;opacity:.6;'>${{t}}</div>`;
  document.getElementById("chat-box").appendChild(div);
  document.getElementById("chat-box").scrollTop = document.getElementById("chat-box").scrollHeight;
}}

async function sendMessage() {{
  const msg = document.getElementById("message").value.trim();
  if (!msg || !currentChannel) return;
  await fetch("/send", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ sender: "ADMIN", message: msg, channel: currentChannel }})
  }});
  document.getElementById("message").value = "";
}}
</script>
</body>
</html>
""")

@app.route("/ping")
def ping():
    return jsonify({"status": "OK ✅"})

if __name__ == "__main__":
    app.run(debug=True, threaded=True)
