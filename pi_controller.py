import os
import sqlite3
import time

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


load_env_file(os.getenv("ENV_FILE", os.path.join(os.path.dirname(__file__), ".env")))

MQTT_BROKER = os.getenv("MQTT_BROKER", "10.160.24.192")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_KEEPALIVE = int(os.getenv("MQTT_KEEPALIVE", "60"))

TOPIC_TEMPERATURE = "salle_serveur/sensor/temperature"
TOPIC_HUMIDITY = "salle_serveur/sensor/humidity"
TOPIC_ALARM_CMD = "salle_serveur/alarm/cmd"
TOPIC_ALARM_STATE = "salle_serveur/alarm/state"
TOPIC_CONTROL = "salle_serveur/control/alarm"
TOPIC_STATUS_CONTROLLER = "salle_serveur/status/pi_controller"

TEMP_THRESHOLD = float(os.getenv("TEMP_THRESHOLD", "24.0"))
DB_PATH = os.getenv("DB_PATH", "sensors.db")

latest_temperature = None
latest_humidity = None
latest_alarm_state = "UNKNOWN"
manual_mode = False
last_command = None


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


def insert_measure(temperature: float, humidity: float):
    conn = db_connection()
    conn.execute(
        "INSERT INTO measures (temperature, humidity) VALUES (?, ?)",
        (temperature, humidity),
    )
    conn.commit()
    conn.close()


def insert_alarm_event(source: str, value: str):
    conn = db_connection()
    conn.execute(
        "INSERT INTO alarm_events (source, value) VALUES (?, ?)",
        (source, value),
    )
    conn.commit()
    conn.close()


def normalized_alarm(payload: str):
    p = payload.strip().upper()
    if p in {"ON", "1", "TRUE"}:
        return "ON"
    if p in {"OFF", "0", "FALSE"}:
        return "OFF"
    if p == "AUTO":
        return "AUTO"
    return None


def publish_alarm_command(client: mqtt.Client, state: str, source: str):
    global last_command
    if state not in {"ON", "OFF"}:
        return
    if state == last_command and source == "auto":
        return
    client.publish(TOPIC_ALARM_CMD, state, qos=1, retain=True)
    last_command = state
    insert_alarm_event(source, state)


def evaluate_auto(client: mqtt.Client):
    if latest_temperature is None:
        return
    next_state = "ON" if latest_temperature > TEMP_THRESHOLD else "OFF"
    publish_alarm_command(client, next_state, "auto")


def on_connect(client, userdata, flags, reason_code, properties=None):
    client.publish(TOPIC_STATUS_CONTROLLER, "online", qos=1, retain=True)
    client.subscribe(
        [
            (TOPIC_TEMPERATURE, 1),
            (TOPIC_HUMIDITY, 1),
            (TOPIC_CONTROL, 1),
            (TOPIC_ALARM_STATE, 1),
        ]
    )


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    time.sleep(2)


def on_message(client, userdata, message):
    global latest_temperature
    global latest_humidity
    global latest_alarm_state
    global manual_mode

    topic = message.topic
    payload = message.payload.decode(errors="ignore")

    if topic == TOPIC_TEMPERATURE:
        try:
            latest_temperature = float(payload)
            if not manual_mode:
                evaluate_auto(client)
        except ValueError:
            pass
        return

    if topic == TOPIC_HUMIDITY:
        try:
            latest_humidity = float(payload)
            if latest_temperature is not None:
                insert_measure(latest_temperature, latest_humidity)
        except ValueError:
            pass
        return

    if topic == TOPIC_CONTROL:
        parsed = normalized_alarm(payload)
        if parsed == "AUTO":
            manual_mode = False
            evaluate_auto(client)
            return
        if parsed in {"ON", "OFF"}:
            manual_mode = True
            publish_alarm_command(client, parsed, "manual")
        return

    if topic == TOPIC_ALARM_STATE:
        parsed = normalized_alarm(payload)
        if parsed in {"ON", "OFF"}:
            latest_alarm_state = parsed
            insert_alarm_event("actuator", parsed)


def create_client():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="pi-controller")
    except AttributeError:
        client = mqtt.Client(client_id="pi-controller")

    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.will_set(TOPIC_STATUS_CONTROLLER, "offline", qos=1, retain=True)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client


def main():
    init_db()
    client = create_client()
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            client.loop_forever()
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(2)


if __name__ == "__main__":
    main()
