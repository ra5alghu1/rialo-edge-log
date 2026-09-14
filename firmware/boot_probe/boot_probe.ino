#include <Arduino.h>

// Temporary startup diagnostic, not telemetry firmware.
// Uses the ESP8266 boot ROM baud rate so one monitor captures both stages.
// Does not access the sensor, device key, built-in LED, or network.
void setup() {
  Serial.begin(74880);
  Serial.println("RIALO_BOOT_PROBE: setup entered");
  Serial.flush();
}

void loop() {
  Serial.printf("RIALO_BOOT_PROBE: alive uptime_ms=%lu\n",
                static_cast<unsigned long>(millis()));
  Serial.flush();
  delay(1000);
}
