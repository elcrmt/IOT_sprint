from flask import Flask, render_template, jsonify, request
import paho.mqtt.client as mqtt
import threading
import time

app = Flask(__name__)

# --- CONFIGURATION ---
MQTT_BROKER = "10.160.24.192" # Modifie l'IP ici si besoin
MQTT_TOPICS = {
    "temp": "salle_serveur/sensor/temperature",
    "hum": "salle_serveur/sensor/humidity",
    "status": "salle_serveur/status/alarm",
    "control": "salle_serveur/control/alarm",
    "esp32_status": "salle_serveur/status/esp32"
}

# État global du système
system_data = {
    "temperature": 0.0,
    "humidity": 0.0,
    "threshold": 24.0,
    "alarm_state": "OFF",
    "esp32_online": False
}

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"MQTT Connecté (code {rc})")
    client.subscribe([(v, 0) for k, v in MQTT_TOPICS.items() if k != "control"])

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    try:
        if msg.topic == MQTT_TOPICS["temp"]:
            system_data["temperature"] = float(payload)
        elif msg.topic == MQTT_TOPICS["hum"]:
            system_data["humidity"] = float(payload)
        elif msg.topic == MQTT_TOPICS["status"]:
            system_data["alarm_state"] = payload
        elif msg.topic == MQTT_TOPICS["esp32_status"]:
            system_data["esp32_online"] = (payload.lower() == "online")
    except Exception as e:
        print(f"Error parsing MQTT message: {e}")

# MQTT Client setup
try:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    mqtt_client = mqtt.Client()

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def start_mqtt():
    while True:
        try:
            print(f"Tentative de connexion MQTT à {MQTT_BROKER}...")
            mqtt_client.connect(MQTT_BROKER, 1883, 60)
            mqtt_client.loop_forever()
        except Exception as e:
            print(f"MQTT Error: {e}. Retrying in 5s...")
            time.sleep(5)

# API Endpoints
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    return jsonify(system_data)

@app.route('/api/alarm', methods=['POST'])
def toggle_alarm():
    data = request.json
    state = "ON" if data.get("on") else "OFF"
    mqtt_client.publish(MQTT_TOPICS["control"], state)
    return jsonify({"status": "sent", "state": state})

if __name__ == '__main__':
    # Thread pour le client MQTT
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()
    
    # Lancement Flask
    print("Dashboard lancé sur http://localhost:5000")
    app.run(host='0.0.0.0', port=5000)
