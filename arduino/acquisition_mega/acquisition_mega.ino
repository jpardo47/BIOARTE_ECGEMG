// Mega 2560: ADC default reference; A0 ECG, A1 MyoWare RAW, A2 ENV.
// MyoWare VIN -> Mega 3.3V (never Mega VIN); common ground.
#include <Arduino.h>
#include <stdio.h>

constexpr uint32_t SAMPLE_PERIOD_US = 1000;
// Compile with -DACQUISITION_BAUD_RATE=460800UL for the selectable alternative.
// Change AppConfig.baudrate / JSON baudrate to the same value.
#ifndef ACQUISITION_BAUD_RATE
#define ACQUISITION_BAUD_RATE 230400UL
#endif
constexpr unsigned long BAUD_RATE = ACQUISITION_BAUD_RATE;
uint32_t nextSample;
uint32_t sampleIndex = 0;

void setup() {
  Serial.begin(BAUD_RATE);
  Serial.println(F("#fs=1000,columns=n,ecg,emg_raw,emg_env"));
  nextSample = micros();
}

void loop() {
  uint32_t now = micros();
  if (static_cast<int32_t>(now - nextSample) < 0) return;
  // Skip elapsed periods; expose missed sample indices instead of catch-up bursts.
  uint32_t skipped = (now - nextSample) / SAMPLE_PERIOD_US;
  sampleIndex += skipped;
  nextSample += (skipped + 1) * SAMPLE_PERIOD_US;
  int ecg = analogRead(A0);
  int raw = analogRead(A1);
  int env = analogRead(A2);
  char frame[32];
  int length = snprintf(frame, sizeof(frame), "%lu,%d,%d,%d\n",
                        static_cast<unsigned long>(sampleIndex), ecg, raw, env);
  if (length > 0 && length < static_cast<int>(sizeof(frame))) {
    Serial.write(reinterpret_cast<const uint8_t *>(frame), length);
  }
  ++sampleIndex;
}
