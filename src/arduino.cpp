#include <Arduino.h>
#include <SPI.h>
#include <Ethernet.h>
#include <PubSubClient.h>

#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif

#ifndef MQTT_HOST_A
#define MQTT_HOST_A 192
#endif
#ifndef MQTT_HOST_B
#define MQTT_HOST_B 168
#endif
#ifndef MQTT_HOST_C
#define MQTT_HOST_C 50
#endif
#ifndef MQTT_HOST_D
#define MQTT_HOST_D 1
#endif

#ifndef MQTT_USER
#define MQTT_USER ""
#endif

#ifndef MQTT_PASS
#define MQTT_PASS ""
#endif

#ifndef LED_ACTIVE_LOW
#define LED_ACTIVE_LOW 0
#endif
#ifndef BUZZER_ACTIVE_LOW
#define BUZZER_ACTIVE_LOW 0
#endif

#ifndef BUZZER_PIN
#define BUZZER_PIN 6
#endif
#ifndef LED_PIN
#define LED_PIN 8
#endif

static const uint8_t BUZZER_GPIO = BUZZER_PIN;
static const uint8_t LED_GPIO = LED_PIN;

static const char *TOPIC_ALARM_CMD = "salle_serveur/alarm/cmd";
static const char *TOPIC_ALARM_STATE = "salle_serveur/alarm/state";
static const char *TOPIC_STATUS = "salle_serveur/status/arduino";

byte macAddress[] = {0xB8, 0x27, 0xEB, 0xAB, 0xCD, 0x01};
IPAddress fallbackIp(192, 168, 50, 40);
IPAddress fallbackDns(192, 168, 50, 1);
IPAddress fallbackGateway(192, 168, 50, 1);
IPAddress fallbackSubnet(255, 255, 255, 0);

EthernetClient ethernetClient;
PubSubClient mqttClient(ethernetClient);
IPAddress mqttHost(MQTT_HOST_A, MQTT_HOST_B, MQTT_HOST_C, MQTT_HOST_D);

unsigned long lastMqttAttemptMs = 0;
const unsigned long mqttRetryMs = 5000;
bool alarmOn = false;
bool stateDirty = false;

static uint8_t levelFor(bool enabled, bool activeLow) {
  if (!activeLow) {
    return enabled ? HIGH : LOW;
  }
  return enabled ? LOW : HIGH;
}

bool isOnPayload(const String &payloadUpper) {
  return payloadUpper == "ON" || payloadUpper == "1" || payloadUpper == "TRUE" ||
         payloadUpper.indexOf("\"ON\"") >= 0 || payloadUpper.indexOf("TRUE") >= 0;
}

bool isOffPayload(const String &payloadUpper) {
  return payloadUpper == "OFF" || payloadUpper == "0" || payloadUpper == "FALSE" ||
         payloadUpper.indexOf("\"OFF\"") >= 0 || payloadUpper.indexOf("FALSE") >= 0;
}

void applyAlarmState(bool enabled) {
  alarmOn = enabled;
  digitalWrite(BUZZER_GPIO, levelFor(enabled, BUZZER_ACTIVE_LOW));
  digitalWrite(LED_GPIO, levelFor(enabled, LED_ACTIVE_LOW));
  stateDirty = true;
}

void publishAlarmStateIfDirty() {
  if (!stateDirty || !mqttClient.connected()) {
    return;
  }
  if (mqttClient.publish(TOPIC_ALARM_STATE, alarmOn ? "ON" : "OFF", true)) {
    stateDirty = false;
  }
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  String payloadStr;
  payloadStr.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) {
    payloadStr += static_cast<char>(payload[i]);
  }
  payloadStr.toUpperCase();

  if (String(topic) != TOPIC_ALARM_CMD) {
    return;
  }

  if (isOnPayload(payloadStr)) {
    applyAlarmState(true);
  } else if (isOffPayload(payloadStr)) {
    applyAlarmState(false);
  }
}

void connectMqtt() {
  if (mqttClient.connected()) {
    return;
  }

  if (millis() - lastMqttAttemptMs < mqttRetryMs) {
    return;
  }
  lastMqttAttemptMs = millis();

  String clientId = "arduino-alarm-" + String((uint16_t)random(0xFFFF), HEX);
  bool connected = false;

  if (strlen(MQTT_USER) > 0) {
    connected = mqttClient.connect(
        clientId.c_str(), MQTT_USER, MQTT_PASS, TOPIC_STATUS, 1, true, "offline");
  } else {
    connected = mqttClient.connect(clientId.c_str(), TOPIC_STATUS, 1, true, "offline");
  }

  if (!connected) {
    return;
  }

  mqttClient.publish(TOPIC_STATUS, "online", true);
  mqttClient.subscribe(TOPIC_ALARM_CMD, 1);
  stateDirty = true;
}

void setupEthernet() {
  Ethernet.init(10);
  if (Ethernet.begin(macAddress) == 0) {
    Ethernet.begin(macAddress, fallbackIp, fallbackDns, fallbackGateway, fallbackSubnet);
  }
  delay(1500);
}

void setup() {
  pinMode(BUZZER_GPIO, OUTPUT);
  pinMode(LED_GPIO, OUTPUT);
  digitalWrite(BUZZER_GPIO, LOW);
  digitalWrite(LED_GPIO, LOW);

  randomSeed(analogRead(A0));
  setupEthernet();

  mqttClient.setServer(mqttHost, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
}

void loop() {
  if (Ethernet.linkStatus() == LinkOFF) {
    setupEthernet();
  }

  connectMqtt();

  if (mqttClient.connected()) {
    mqttClient.loop();
    publishAlarmStateIfDirty();
  }
}
