import paho.mqtt.client as mqtt
from gpiozero import LED, Buzzer
import time

# --- CONFIGURATION ---
MQTT_BROKER = "10.160.24.192"
MQTT_TOPIC_TEMP = "salle_serveur/sensor/temperature"
MQTT_TOPIC_HUM = "salle_serveur/sensor/humidity"
MQTT_TOPIC_CONTROL = "salle_serveur/control/alarm"
MQTT_TOPIC_STATUS = "salle_serveur/status/alarm"
TEMP_THRESHOLD = 24.0

# Initialisation (Buzzer D6 -> GPIO 6, LED D8 -> GPIO 8)
led = LED(8)
buzzer = Buzzer(6)

manual_override = False

def update_alarm(state):
    if state:
        led.on()
        buzzer.on()
    else:
        led.off()
        buzzer.off()
    client.publish(MQTT_TOPIC_STATUS, "ON" if state else "OFF", retain=True)

def on_message(client, userdata, message):
    global manual_override
    try:
        topic = message.topic
        payload = message.payload.decode()
        
        if topic == MQTT_TOPIC_CONTROL:
            if payload == "ON":
                manual_override = True
                update_alarm(True)
                print("Manuel: Alarm ON")
            elif payload == "OFF":
                manual_override = False
                update_alarm(False)
                print("Manuel: Alarm OFF")
        
        elif topic == MQTT_TOPIC_TEMP:
            temp = float(payload)
            print(f"Température reçue: {temp}°C")

            if not manual_override:
                if temp > TEMP_THRESHOLD:
                    print("!!! ALERTE SEUIL DÉPASSÉ !!!")
                    update_alarm(True)
                else:
                    update_alarm(False)
            
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
    client.subscribe([(MQTT_TOPIC_TEMP, 0), (MQTT_TOPIC_CONTROL, 0)])
    client.loop_forever()
except KeyboardInterrupt:
    print("\nArrêt...")
finally:
    led.off()
    buzzer.off()
