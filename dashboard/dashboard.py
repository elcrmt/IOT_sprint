import os
import sqlite3
import threading
import time

from flask import Flask, jsonify, render_template, request
import paho.mqtt.client as mqtt

def load_env_file(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in {"\"", "'"}:
                    v = v[1:-1]
                if k:
                    os.environ[k] = v
    except FileNotFoundError:
        return


load_env_file(
    os.getenv(
        "ENV_FILE",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
    )
)

app = Flask(__name__)

MQTT_BROKER = os.getenv("MQTT_BROKER", "10.160.24.192")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))
TEMP_THRESHOLD = float(os.getenv("TEMP_THRESHOLD", "24.0"))
DB_PATH = os.getenv("DB_PATH", "sensors.db")

TOPIC_ALARM_CONTROL = "salle_serveur/control/alarm"
TOPIC_ALARM_STATE = "salle_serveur/alarm/state"
TOPIC_STATUS_ESP32 = "salle_serveur/status/esp32"
TOPIC_STATUS_CONTROLLER = "salle_serveur/status/pi_controller"

runtime = {
    "alarm_state": "UNKNOWN",
    "esp32_online": False,
    "controller_online": False,
}


def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS measures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alarm_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            value TEXT NOT NULL,
            ts DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_measures_ts ON measures(ts DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alarm_events_ts ON alarm_events(ts DESC)")
    conn.commit()
    conn.close()


def latest_measure():
    conn = db_connection()
    row = conn.execute(
        "SELECT id, temperature, humidity, ts FROM measures ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "temperature": row["temperature"],
        "humidity": row["humidity"],
        "ts": row["ts"],
    }


def history(limit: int):
    conn = db_connection()
    rows = conn.execute(
        "SELECT id, temperature, humidity, ts FROM measures ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "temperature": row["temperature"],
            "humidity": row["humidity"],
            "ts": row["ts"],
        }
        for row in rows
    ]


def latest_alarm_from_db():
    conn = db_connection()
    row = conn.execute(
        "SELECT value FROM alarm_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return "UNKNOWN"
    return row["value"]


def resolve_alarm_state():
    state = runtime["alarm_state"]
    if state in {"ON", "OFF"}:
        return state
    return latest_alarm_from_db()


def normalize_control_payload(data):
    mode = str(data.get("mode", "")).strip().upper()
    if mode == "AUTO":
        return "AUTO"
    if "state" in data:
        state = str(data.get("state", "")).strip().upper()
        if state in {"ON", "OFF"}:
            return state
    if "on" in data:
        return "ON" if bool(data.get("on")) else "OFF"
    return None


def mqtt_on_connect(client, userdata, flags, reason_code, properties=None):
    client.subscribe(
        [
            (TOPIC_ALARM_STATE, 1),
            (TOPIC_STATUS_ESP32, 1),
            (TOPIC_STATUS_CONTROLLER, 1),
        ]
    )


def mqtt_on_message(client, userdata, message):
    payload = message.payload.decode(errors="ignore").strip().upper()
    if message.topic == TOPIC_ALARM_STATE and payload in {"ON", "OFF"}:
        runtime["alarm_state"] = payload
    elif message.topic == TOPIC_STATUS_ESP32:
        runtime["esp32_online"] = payload == "ONLINE"
    elif message.topic == TOPIC_STATUS_CONTROLLER:
        runtime["controller_online"] = payload == "ONLINE"


def create_mqtt_client():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="dashboard-api")
    except AttributeError:
        client = mqtt.Client(client_id="dashboard-api")

    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message
    return client


mqtt_client = create_mqtt_client()


def mqtt_loop():
    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            mqtt_client.loop_forever()
        except Exception:
            time.sleep(2)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/latest")
def api_latest():
    measure = latest_measure()
    return jsonify(
        {
            "measure": measure,
            "alarm_state": resolve_alarm_state(),
            "threshold": TEMP_THRESHOLD,
            "esp32_online": runtime["esp32_online"],
            "controller_online": runtime["controller_online"],
        }
    )


@app.route("/api/history")
def api_history():
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20
    limit = max(1, min(limit, 500))
    return jsonify(history(limit))


@app.route("/api/alarm/state")
def api_alarm_state():
    return jsonify({"state": resolve_alarm_state()})


@app.route("/api/alarm", methods=["POST"])
def api_alarm():
    data = request.get_json(silent=True) or {}
    payload = normalize_control_payload(data)
    if payload is None:
        return jsonify({"status": "error", "message": "invalid payload"}), 400

    info = mqtt_client.publish(TOPIC_ALARM_CONTROL, payload, qos=1, retain=True)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        return jsonify({"status": "error", "message": "mqtt publish failed"}), 500

    return jsonify({"status": "ok", "sent": payload})


@app.route("/api/data")
def api_data_compat():
    measure = latest_measure()
    if not measure:
        return jsonify(
            {
                "temperature": 0.0,
                "humidity": 0.0,
                "threshold": TEMP_THRESHOLD,
                "alarm_state": resolve_alarm_state(),
                "esp32_online": runtime["esp32_online"],
                "controller_online": runtime["controller_online"],
            }
        )

    return jsonify(
        {
            "temperature": float(measure["temperature"]),
            "humidity": float(measure["humidity"]),
            "threshold": TEMP_THRESHOLD,
            "alarm_state": resolve_alarm_state(),
            "esp32_online": runtime["esp32_online"],
            "controller_online": runtime["controller_online"],
            "ts": measure["ts"],
        }
    )


def main():
    init_db()
    t = threading.Thread(target=mqtt_loop, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
