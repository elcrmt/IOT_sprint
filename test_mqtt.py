import paho.mqtt.client as mqtt
import time

def on_message(client, userdata, message):
    print(f"{message.topic}: {message.payload.decode()}")

# Test connection with potential CallbackAPIVersion issues
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client() # Fallback for older paho-mqtt versions

client.on_message = on_message

print("Connecting to MQTT broker at 10.160.24.192...")
try:
    client.connect("10.160.24.192", 1883, 60)
    client.subscribe("salle_serveur/#")
    client.loop_start()
    print("Listening for 15 seconds (waiting for ESP32 data)...")
    time.sleep(15)
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"Error: {e}")
