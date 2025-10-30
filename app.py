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
# 🔹 FUNCIÓN: crear canal ascendente (chat_1, chat_2...)
# ==============================================
def generar_chat_nuevo(db, cursor):
    cursor.execute("SELECT COUNT(*) AS total FROM channels")
    row = cursor.fetchone()
    total = row["total"] if row and "total" in row else 0
    nuevo_num = total + 1
    nuevo_nombre = f"chat_{nuevo_num}"
    cursor.execute("INSERT INTO channels (name) VALUES (%s)", (nuevo_nombre,))
    db.commit()
    return nuevo_nombre

# ==============================================
# 🟢 JOIN - Cliente se une y obtiene su chat
# ==============================================
@app.route("/join", methods=["POST"])
def join_chat():
    data = request.get_json() or {}
    username = data.get("username")
    if not username:
        return jsonify({"error": "Nombre requerido"}), 400

    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Verificar si ya tiene chat
        cursor.execute("SELECT channel FROM conversations WHERE username=%s", (username,))
        existing = cursor.fetchone()

        if existing and existing.get("channel"):
            chat = existing["channel"]
            created = False
        else:
            chat = generar_chat_nuevo(db, cursor)
            cursor.execute("INSERT INTO conversations (username, channel) VALUES (%s, %s)", (username, chat))
            db.commit()
            created = True

        # Notificar al admin si es un chat nuevo
        if created:
            try:
                pusher_client.trigger("admin_global", "nuevo-chat", {"chat": chat, "username": username})
            except Exception as e:
                print("⚠️ Pusher admin_global error:", e)

        return jsonify({"chat": chat, "username": username}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor: cursor.close()
        if db: db.close()

# ==============================================
# 💬 ENVIAR MENSAJE (asincrónico)
# ==============================================
@app.route("/send", methods=["POST"])
def enviar_mensaje():
    data = request.get_json() or {}
    username = data.get("sender")
    message = data.get("message")
    chat = data.get("channel")

    if not username or not message or not chat:
        return jsonify({"error": "Campos incompletos"}), 400

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def guardar_y_emitir():
        db2 = None
        cursor2 = None
        try:
            db2 = get_db_connection()
            cursor2 = db2.cursor()
            cursor2.execute(
                "INSERT INTO messages (username, message, channel, timestamp) VALUES (%s, %s, %s, %s)",
                (username, message, chat, timestamp)
            )
            db2.commit()

            pusher_client.trigger(chat, "new-message", {
                "sender": username,
                "message": message,
                "timestamp": timestamp
            })

        except Exception as e:
            print("⚠️ Error guardar_y_emitir:", e)
        finally:
            if cursor2: cursor2.close()
            if db2: db2.close()

    threading.Thread(target=guardar_y_emitir, daemon=True).start()
    return jsonify({"status": "enviado"}), 200

# ==============================================
# 📜 HISTORIAL DE MENSAJES
# ==============================================
@app.route("/messages/<chat>", methods=["GET"])
def obtener_mensajes(chat):
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT username, message, timestamp
            FROM messages
            WHERE channel = %s
            ORDER BY id DESC
            LIMIT 100
        """, (chat,))
        rows = cursor.fetchall() or []
        rows.reverse()
        return jsonify(rows), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor: cursor.close()
        if db: db.close()

# ==============================================
# 🧩 PANEL ADMIN
# ==============================================
@app.route("/")
def index():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT name FROM channels ORDER BY id ASC")
        chats = [row["name"] for row in cursor.fetchall()]
    finally:
        if cursor: cursor.close()
        if db: db.close()

    botones = "".join([f"<button id='btn_{c}' onclick=\"selectChat('{c}')\">{c}</button>" for c in chats])

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
    <h2>Chats Activos</h2>
    <div id="chat-list">{botones}</div>
  </aside>
  <main>
    <header id="chat-name">Selecciona un chat</header>
    <div id="chat-box"></div>
    <footer>
      <input id="message" placeholder="Escribe un mensaje...">
      <button onclick="sendMessage()">Enviar</button>
    </footer>
  </main>

<script>
let currentChat = null;
let pusher = new Pusher('b6bbf62d682a7a882f41', {{cluster:'mt1'}});
let activeSub = null;

// Admin escucha nuevos chats
let adminGlobal = pusher.subscribe("admin_global");
adminGlobal.bind("nuevo-chat", function(data) {{
  const c = data.chat;
  if (!document.getElementById('btn_' + c)) {{
    const btn = document.createElement('button');
    btn.id = 'btn_' + c;
    btn.textContent = `${{c}} (${data.username})`;
    btn.onclick = function() {{ selectChat(c); }};
    document.getElementById("chat-list").appendChild(btn);
  }}
}});

async function selectChat(c) {{
  currentChat = c;
  document.getElementById("chat-name").innerText = "Chat: " + c;
  const res = await fetch(`/messages/${{c}}`);
  const messages = await res.json();
  renderMessages(messages);

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
  if (!msg || !currentChat) return;
  await fetch("/send", {{
    method: "POST",
    headers: {{ "Content-Type": "application/json" }},
    body: JSON.stringify({{ sender: "ADMIN", message: msg, channel: currentChat }})
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
