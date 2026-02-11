#include <Arduino.h>

// Définition de la broche de la LED (Pin 13 est la LED intégrée sur l'Arduino Uno)
const int LED_PIN = 13;

void setup() {
  // Initialisation de la broche en tant que sortie
  pinMode(LED_PIN, OUTPUT);
}

void loop() {
  // Allumer la LED
  digitalWrite(LED_PIN, HIGH);
  delay(1000); // Attendre 1 seconde
  
  // Éteindre la LED
  digitalWrite(LED_PIN, LOW);
  delay(1000); // Attendre 1 seconde
}
