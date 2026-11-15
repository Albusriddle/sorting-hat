// ============================================================
// I2C_SCAN.ino —— 两条 I2C 总线全扫一遍
//
// 目的：搞清楚 16/17（Wire，ASR）和 19/18（Wire1，TTS）上
//       到底挂了哪些地址。板子说 asr=off 时用它定位。
//
// 烧完打开串口监视器 115200，每 3 秒自动扫一次。
// ============================================================
#include <Wire.h>

#define PIN_ASR_SDA 16
#define PIN_ASR_SCL 17
#define PIN_TTS_SDA 19
#define PIN_TTS_SCL 18

TwoWire TtsBus(1);   // ESP32 的第二条 I2C

static void scan(TwoWire& bus, const char* name) {
  Serial.printf("\n[%s] 扫描中...\n", name);
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    bus.beginTransmission(a);
    if (bus.endTransmission() == 0) {
      Serial.printf("[%s] 找到设备  0x%02X\n", name, a);
      found++;
    }
  }
  if (found == 0) Serial.printf("[%s] 一个都没有 ← 线没接好 / 没供电 / 接反了\n", name);
  else            Serial.printf("[%s] 共 %d 个\n", name, found);
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n===== I2C SCAN =====");
  Serial.println("ASR: SDA=16 SCL=17   TTS: SDA=19 SCL=18");

  Wire.begin(PIN_ASR_SDA, PIN_ASR_SCL, 100000);
  TtsBus.begin(PIN_TTS_SDA, PIN_TTS_SCL, 10000);
  delay(50);
}

void loop() {
  scan(Wire,   "ASR 16/17");
  scan(TtsBus, "TTS 19/18");
  Serial.println("\n---- 3 秒后再扫 ----");
  delay(3000);
}
