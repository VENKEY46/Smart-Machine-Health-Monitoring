#include <Wire.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "LSM6DS3.h"

#include "config.h"

const char* ssid = WIFI_SSID;
const char* password = WIFI_PASSWORD;
const char* mqtt_server = MQTT_SERVER;

LSM6DS3 myIMU(I2C_MODE, 0x6A);
WiFiClient espClient;
PubSubClient client(espClient);

unsigned long lastSample = 0;
const unsigned long sampleIntervalMs = 10; // ~100 Hz

unsigned long lastPrint = 0;
const unsigned long printIntervalMs = 1000; // print to Serial once per second

void setup_wifi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi connected, IP: ");
  Serial.println(WiFi.localIP());
}

void reconnect_mqtt() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
    if (client.connect("esp32-fan1")) {
      Serial.println("Connected to MQTT broker");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 2s");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  if (myIMU.begin() != 0) {
    Serial.println("IMU error: check wiring; sampling stopped.");
    while (true) { delay(1000); }
  } else {
    Serial.println("IMU OK");
  }
  setup_wifi();
  WiFi.setSleep(false);
  client.setServer(mqtt_server, MQTT_SERVER_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    setup_wifi();
  }
  if (!client.connected()) {
    reconnect_mqtt();
  }
  client.loop();

  unsigned long now = millis();
  if (now - lastSample >= sampleIntervalMs) {
    lastSample = now;
    float ax = myIMU.readFloatAccelX();
    float ay = myIMU.readFloatAccelY();
    float az = myIMU.readFloatAccelZ();

    char payload[128];
    snprintf(payload, sizeof(payload),
      "{\"ts\":%lu,\"ax\":%.4f,\"ay\":%.4f,\"az\":%.4f}",
      now, ax, ay, az);
    client.publish("sensors/fan1/vibration", payload);

    if (now - lastPrint >= printIntervalMs) {
      lastPrint = now;
      Serial.println(payload);
    }
  }
}
