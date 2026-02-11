#include <Arduino.h>
#include <DHT.h>
#include <PubSubClient.h>
#include <WiFi.h>

#define FW_TAG "esp32-clean-v1"

static const char *WIFI_SSID = "IOT-PI";
static const char *WIFI_PASS = "tuisse123";

static const unsigned long WIFI_RETRY_MS = 15000;
static const unsigned long MQTT_RETRY_MS = 5000;
static const unsigned long SENSOR_PUBLISH_MS = 10000;

static unsigned long lastWifiAttemptMs = 0;
static unsigned long lastMqttAttemptMs = 0;
static unsigned long lastSensorPublishMs = 0;

static const char *MQTT_HOST = "192.168.50.1";
static const uint16_t MQTT_PORT = 1883;

static const char *TOPIC_TEMPERATURE = "salle_serveur/sensor/temperature";
static const char *TOPIC_HUMIDITY = "salle_serveur/sensor/humidity";
static const char *TOPIC_STATUS = "salle_serveur/status/esp32";

static const uint8_t DHT_PIN = 4;
#ifndef DHT_SENSOR_TYPE
#define DHT_SENSOR_TYPE DHT11
#endif
static const uint8_t DHT_TYPE = DHT_SENSOR_TYPE;

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
DHT dht(DHT_PIN, DHT_TYPE);
String mqttClientId;

bool publishFloat(const char *topic, float value, uint8_t decimals) {
  char payload[20];
  dtostrf(value, 0, decimals, payload);
  return mqttClient.publish(topic, payload, true);
}

bool readDhtValidated(float &temperature, float &humidity) {
  for (uint8_t attempt = 0; attempt < 3; attempt++) {
    const float h = dht.readHumidity();
    const float t = dht.readTemperature();

    if (!isnan(h) && !isnan(t) && h >= 0.0f && h <= 100.0f && t >= -40.0f &&
        t <= 85.0f) {
      temperature = t;
      humidity = h;
      return true;
    }
    delay(250);
  }
  return false;
}

void connectToWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.printf("Wi-Fi: connexion a \"%s\"...\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  lastWifiAttemptMs = millis();
}

void onWifiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.printf("Wi-Fi OK: IP=%s RSSI=%d\n",
                    WiFi.localIP().toString().c_str(), WiFi.RSSI());
      break;

    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.printf("Wi-Fi down: reason=%d\n", info.wifi_sta_disconnected.reason);
      break;

    default:
      break;
  }
}

void connectToMqtt() {
  if (WiFi.status() != WL_CONNECTED || mqttClient.connected()) {
    return;
  }

  if (millis() - lastMqttAttemptMs < MQTT_RETRY_MS) {
    return;
  }

  lastMqttAttemptMs = millis();
  Serial.printf("MQTT: connexion a %s:%u...\n", MQTT_HOST, MQTT_PORT);

  const bool ok = mqttClient.connect(mqttClientId.c_str(), TOPIC_STATUS, 1,
                                     true, "offline");
  if (!ok) {
    Serial.printf("MQTT echec: rc=%d\n", mqttClient.state());
    return;
  }

  Serial.println("MQTT OK");
  mqttClient.publish(TOPIC_STATUS, "online", true);
}

void publishDhtReadings() {
  if (!mqttClient.connected()) {
    return;
  }

  if (millis() - lastSensorPublishMs < SENSOR_PUBLISH_MS) {
    return;
  }
  lastSensorPublishMs = millis();

  float humidity = NAN;
  float temperature = NAN;
  if (!readDhtValidated(temperature, humidity)) {
    Serial.println("DHT erreur");
    return;
  }

  const bool tOk = publishFloat(TOPIC_TEMPERATURE, temperature, 1);
  const bool hOk = publishFloat(TOPIC_HUMIDITY, humidity, 1);
  if (!tOk || !hOk) {
    Serial.println("MQTT publish capteur KO");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println();
  Serial.printf("FW=%s build=%s %s\n", FW_TAG, __DATE__, __TIME__);

  dht.begin();

  WiFi.onEvent(onWifiEvent);
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  mqttClient.setServer(MQTT_HOST, MQTT_PORT);

  uint64_t chipId = ESP.getEfuseMac();
  char idBuffer[32];
  snprintf(idBuffer, sizeof(idBuffer), "esp32-%04X%08X",
           (uint16_t)(chipId >> 32), (uint32_t)chipId);
  mqttClientId = String(idBuffer);

  connectToWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED &&
      millis() - lastWifiAttemptMs >= WIFI_RETRY_MS) {
    connectToWifi();
  }

  connectToMqtt();

  if (mqttClient.connected()) {
    mqttClient.loop();
    publishDhtReadings();
  }
}
