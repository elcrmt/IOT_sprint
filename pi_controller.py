import paho.mqtt.client as mqtt
from gpiozero import LED, Buzzer
import time

# --- CONFIGURATION ---
MQTT_BROKER = "localhost"
MQTT_TOPIC = "salle_serveur/sensor/temperature"
TEMP_THRESHOLD = 25.0

# Initialisation (Buzzer D6 -> GPIO 6, LED D8 -> GPIO 8)
led = LED(8)
buzzer = Buzzer(6)

def on_message(client, userdata, message):
    try:
        temp = float(message.payload.decode())
        print(f"Température reçue: {temp}°C")

        if temp > TEMP_THRESHOLD:
            print("!!! ALERTE : SEUIL DÉPASSÉ !!!")
            led.on()
            buzzer.on()
        else:
            led.off()
            buzzer.off()
            
    except Exception as e:
        print(f"Erreur: {e}")

# --- MQTT SETUP ---
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
except AttributeError:
    client = mqtt.Client()

client.on_message = on_message

print(f"Contrôleur démarré (via gpiozero). Seuil: {TEMP_THRESHOLD}°C")
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_forever()
except KeyboardInterrupt:
    print("\nArrêt...")
finally:
    led.off()
    buzzer.off()
