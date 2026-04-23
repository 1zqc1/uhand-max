/*
I2C 地址扫描器
扫描并打印所有找到的 I2C 设备地址
*/

#include <Wire.h>

void setup() {
  Serial.begin(9600);
  while (!Serial);

  Serial.println("=== I2C Scanner ===");
  Wire.begin();

  int devices = 0;

  for (byte address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    byte error = Wire.endTransmission();

    if (error == 0) {
      Serial.print("找到设备: 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
      devices++;
    }
    else if (error == 4) {
      Serial.print("未知错误 @ 地址: 0x");
      if (address < 16) Serial.print("0");
      Serial.println(address, HEX);
    }
  }

  if (devices == 0) {
    Serial.println("未找到任何 I2C 设备");
  } else {
    Serial.print("共找到 ");
    Serial.print(devices);
    Serial.println(" 个设备");
  }
}

void loop() {
  delay(100);
}