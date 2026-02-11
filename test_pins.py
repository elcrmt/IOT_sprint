from gpiozero import LED, Buzzer
from time import sleep

# Test des pins GPIO 8 (D8) et GPIO 6 (D6)
led = LED(8)
buzzer = Buzzer(6)

print("--- TEST HARDWARE ---")
print("Allumage LED (GPIO 8) et Buzzer (GPIO 6) pendant 5 secondes...")

try:
    led.on()
    buzzer.on()
    for i in range(5, 0, -1):
        print(f"{i}...")
        sleep(1)
except KeyboardInterrupt:
    print("\nInterrompu.")

led.off()
buzzer.off()
print("Test terminé. Si rien ne s'est passé, vérifiez votre câblage.")
print("Rappel : GPIO 8 = Pin physique 24, GPIO 6 = Pin physique 31.")
