#include <Arduino.h>
#include <WiFi.h>

static const char *WIFI_SSID = "IOT-PI";
static const char *WIFI_PASS = "tuisse123";

static const unsigned long WIFI_RETRY_MS = 10000;
static unsigned long lastWifiAttemptMs = 0;

void connectToWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.printf("Connexion Wi-Fi vers \"%s\"...\n", WIFI_SSID);
  WiFi.disconnect(true, true);
  delay(200);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  lastWifiAttemptMs = millis();
}

void onWifiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_START:
      Serial.println("Wi-Fi STA demarre");
      break;

    case ARDUINO_EVENT_WIFI_STA_CONNECTED:
      Serial.println("Association AP OK");
      break;

    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.print("IP obtenue: ");
      Serial.println(WiFi.localIP());
      Serial.print("RSSI: ");
      Serial.println(WiFi.RSSI());
      break;

    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.printf("Deconnexion Wi-Fi, raison=%d\n",
                    info.wifi_sta_disconnected.reason);
      break;

    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  WiFi.onEvent(onWifiEvent);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  connectToWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED &&
      millis() - lastWifiAttemptMs >= WIFI_RETRY_MS) {
    connectToWifi();
  }

  static unsigned long lastStatusMs = 0;
  if (WiFi.status() == WL_CONNECTED && millis() - lastStatusMs >= 5000) {
    Serial.printf("Connecte a %s | IP=%s | RSSI=%d dBm\n", WIFI_SSID,
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
    lastStatusMs = millis();
  }
}
