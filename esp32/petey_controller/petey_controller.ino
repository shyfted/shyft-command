#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoOTA.h>

#include "secrets.h"

const char* otaHostname = "petey-esp32";

const int LCD_CONTROL_PIN = 25;
const int C4001_RX_PIN = 16;
const int C4001_TX_PIN = 17;
const int C4001_BAUD = 9600;
const size_t C4001_MAX_FRAME_LENGTH = 160;
const size_t C4001_RAW_FRAME_COUNT = 12;

WebServer server(80);
HardwareSerial c4001Serial(2);

String c4001FrameBuffer;
String c4001RawFrames[C4001_RAW_FRAME_COUNT];
unsigned long c4001RawFrameMs[C4001_RAW_FRAME_COUNT] = {};
size_t c4001RawNext = 0;
size_t c4001RawStored = 0;
unsigned long c4001FrameCount = 0;
unsigned long c4001ByteCount = 0;
unsigned long c4001LastFrameMs = 0;
bool c4001PresenceValid = false;
bool c4001Present = false;
unsigned long c4001LastSeenMs = 0;
unsigned long c4001LastChangeMs = 0;
bool c4001DistanceValid = false;
float c4001Distance = 0.0f;
bool c4001SpeedValid = false;
float c4001Speed = 0.0f;
String c4001FrameType = "unknown";

String jsonEscape(const String& value) {
  String escaped;
  escaped.reserve(value.length() + 8);
  for (size_t i = 0; i < value.length(); ++i) {
    char c = value.charAt(i);
    if (c == '\\' || c == '"') {
      escaped += '\\';
      escaped += c;
    } else if (c == '\n') {
      escaped += "\\n";
    } else if (c == '\r') {
      escaped += "\\r";
    } else if (static_cast<uint8_t>(c) < 0x20) {
      char encoded[7];
      snprintf(encoded, sizeof(encoded), "\\u%04x", static_cast<uint8_t>(c));
      escaped += encoded;
    } else {
      escaped += c;
    }
  }
  return escaped;
}

void updateC4001Presence(bool present) {
  if (!c4001PresenceValid || present != c4001Present) {
    c4001LastChangeMs = millis();
  }
  c4001PresenceValid = true;
  c4001Present = present;
  if (present) {
    c4001LastSeenMs = millis();
  }
}

void interpretC4001Frame(const String& frame) {
  int presentValue = -1;
  if (sscanf(frame.c_str(), "$DFHPD,%d", &presentValue) == 1
      && (presentValue == 0 || presentValue == 1)) {
    updateC4001Presence(presentValue == 1);
    c4001DistanceValid = false;
    c4001SpeedValid = false;
    c4001FrameType = "DFHPD";
    return;
  }

  int targetCount = -1;
  int targetNumber = -1;
  float distance = 0.0f;
  float speed = 0.0f;
  unsigned long energy = 0;
  if (sscanf(
          frame.c_str(),
          "$DFDMD,%d,%d,%f,%f,%lu",
          &targetCount,
          &targetNumber,
          &distance,
          &speed,
          &energy
      ) == 5 && targetCount >= 0) {
    updateC4001Presence(targetCount > 0);
    c4001DistanceValid = c4001Present && targetNumber > 0 && distance >= 0.0f;
    c4001Distance = distance;
    c4001SpeedValid = c4001Present && targetNumber > 0;
    c4001Speed = speed;
    c4001FrameType = "DFDMD";
  }
}

void recordC4001Frame(String frame) {
  frame.trim();
  if (frame.length() == 0) {
    return;
  }

  c4001RawFrames[c4001RawNext] = frame;
  c4001RawFrameMs[c4001RawNext] = millis();
  c4001RawNext = (c4001RawNext + 1) % C4001_RAW_FRAME_COUNT;
  if (c4001RawStored < C4001_RAW_FRAME_COUNT) {
    ++c4001RawStored;
  }
  ++c4001FrameCount;
  c4001LastFrameMs = millis();
  interpretC4001Frame(frame);
  Serial.print("[C4001 RAW] ");
  Serial.println(frame);
}

void readC4001() {
  while (c4001Serial.available() > 0) {
    char c = static_cast<char>(c4001Serial.read());
    ++c4001ByteCount;

    if (c == '\r' || c == '\n') {
      recordC4001Frame(c4001FrameBuffer);
      c4001FrameBuffer = "";
      continue;
    }

    c4001FrameBuffer += c;
    if (c == '*' || c4001FrameBuffer.length() >= C4001_MAX_FRAME_LENGTH) {
      recordC4001Frame(c4001FrameBuffer);
      c4001FrameBuffer = "";
    }
  }
}

void handlePing() {
  server.send(200, "text/plain", "pong");
}

void handleStatus() {
  String json = "{";
  json += "\"ok\":true,";
  json += "\"uptime_ms\":" + String(millis()) + ",";
  json += "\"ip\":\"" + WiFi.localIP().toString() + "\",";
  json += "\"rssi\":" + String(WiFi.RSSI()) + ",";
  json += "\"lcd_pin\":" + String(digitalRead(LCD_CONTROL_PIN)) + ",";
  json += "\"c4001_uart_bytes\":" + String(c4001ByteCount) + ",";
  json += "\"c4001_frame_count\":" + String(c4001FrameCount) + ",";
  json += "\"c4001_last_frame_ms\":" + String(c4001LastFrameMs) + ",";
  json += "\"c4001_frame_type\":\"" + jsonEscape(c4001FrameType) + "\"";
  if (c4001PresenceValid) {
    json += ",\"c4001_present\":" + String(c4001Present ? "true" : "false");
    json += ",\"c4001_last_seen_ms\":" + String(c4001LastSeenMs);
    json += ",\"c4001_last_change_ms\":" + String(c4001LastChangeMs);
  }
  if (c4001DistanceValid) {
    json += ",\"c4001_distance_m\":" + String(c4001Distance, 3);
  }
  if (c4001SpeedValid) {
    json += ",\"c4001_speed_mps\":" + String(c4001Speed, 3);
  }
  json += "}";

  server.send(200, "application/json", json);
}

void handleC4001Raw() {
  String json = "{\"ok\":true,\"frames\":[";
  size_t oldest = (c4001RawNext + C4001_RAW_FRAME_COUNT - c4001RawStored)
      % C4001_RAW_FRAME_COUNT;
  for (size_t i = 0; i < c4001RawStored; ++i) {
    size_t index = (oldest + i) % C4001_RAW_FRAME_COUNT;
    if (i > 0) {
      json += ",";
    }
    json += "{\"at_ms\":" + String(c4001RawFrameMs[index]);
    json += ",\"raw\":\"" + jsonEscape(c4001RawFrames[index]) + "\"}";
  }
  json += "]}";
  server.send(200, "application/json", json);
}

void handleLcdOn() {
  digitalWrite(LCD_CONTROL_PIN, HIGH);
  server.send(200, "application/json", "{\"ok\":true,\"lcd\":\"on\"}");
}

void handleLcdOff() {
  digitalWrite(LCD_CONTROL_PIN, LOW);
  server.send(200, "application/json", "{\"ok\":true,\"lcd\":\"off\"}");
}

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("Petey ESP32 starting...");

  pinMode(LCD_CONTROL_PIN, OUTPUT);

  // Safe boot default: LCD ON.
  digitalWrite(LCD_CONTROL_PIN, HIGH);

  c4001Serial.begin(C4001_BAUD, SERIAL_8N1, C4001_RX_PIN, C4001_TX_PIN);
  c4001FrameBuffer.reserve(C4001_MAX_FRAME_LENGTH);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to Wi-Fi");

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("Wi-Fi connected.");
  Serial.print("ESP32 IP address: ");
  Serial.println(WiFi.localIP());

  server.on("/ping", HTTP_GET, handlePing);
  server.on("/status", HTTP_GET, handleStatus);
  server.on("/c4001/raw", HTTP_GET, handleC4001Raw);

  server.on("/lcd/on", HTTP_GET, handleLcdOn);
  server.on("/lcd/off", HTTP_GET, handleLcdOff);

  server.on("/lcd/on", HTTP_POST, handleLcdOn);
  server.on("/lcd/off", HTTP_POST, handleLcdOff);

  server.begin();

  ArduinoOTA.setHostname(otaHostname);
  ArduinoOTA.setPassword(otaPassword);

  ArduinoOTA.onStart([]() {
    Serial.println("OTA update starting...");
  });

  ArduinoOTA.onEnd([]() {
    Serial.println("\nOTA update complete.");
  });

  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("OTA Progress: %u%%\r", (progress * 100) / total);
  });

  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("OTA Error [%u]\n", error);
  });

  ArduinoOTA.begin();

  Serial.println("HTTP server started.");
  Serial.println("Arduino OTA ready.");
}

void loop() {
  readC4001();
  server.handleClient();
  ArduinoOTA.handle();
}
