import paho.mqtt.client as mqtt
import time
import os

def on_message(client, userdata, message):
    print(f"{message.topic}: {message.payload.decode()}")

MQTT_BROKER = os.getenv("MQTT_BROKER", "10.160.24.192")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Test connection with potential CallbackAPIVersion issues
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client() # Fallback for older paho-mqtt versions

client.on_message = on_message

if MQTT_USERNAME:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

print(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.subscribe("salle_serveur/#")
    client.loop_start()
    print("Listening for 15 seconds (waiting for ESP32 data)...")
    time.sleep(15)
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"Error: {e}")
