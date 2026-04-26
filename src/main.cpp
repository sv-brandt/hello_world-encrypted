#include <Arduino.h>

void setup() {
    Serial.begin(115200);
    Serial.println("Hello World v1.0");
}

void loop() {
    Serial.println("running...");
    delay(5000);
}
