// ============================================================
// Step1_TTS_SMOKE.ino  ——  第 2 步：驱动冒烟测试（只有一个目标：念出声）
//
// 用之前：
//   1. 和 asr_wonderecho.h/.cpp、tts_xfs5152.h/.cpp、phrases_gbk.h 放在同一个文件夹
//   2. 板子选好型号，串口监视器 115200
//   3. 上传后两秒内应该听到"分院帽醒了…"
//
// 接线（以组长驱动为准）：
//   ASR  Wire   SDA16 / SCL17   100 kHz   5V + 共地
//   TTS  Wire1  SDA19 / SCL18    10 kHz   5V + 共地
// ============================================================
#include <Wire.h>
#include "asr_wonderecho.h"
#include "tts_xfs5152.h"
#include "phrases_gbk.h"

#define PIN_ASR_SDA 16
#define PIN_ASR_SCL 17
#define PIN_TTS_SDA 19
#define PIN_TTS_SCL 18

TwoWire TtsBus(1);          // 第二条 I2C 总线（Wire1）

voice::WonderEcho asr;
voice::XFS5152  tts;

void say(const uint8_t* d, uint16_t n, const char* name) {
  bool ok = tts.speakGBK(d, n);
  Serial.printf("[TTS] %s -> %s\n", name, ok ? "sent" : "FAIL");
  tts.waitDone();           // 等它念完，串口命令才不会互相打断
  Serial.println("[TTS] ---");
}

void setup() {
  Serial.begin(115200);
  delay(1500);                       // 等 USB 串口准备好，不然开机日志会丢
  Serial.println("\n===== TTS SMOKE TEST =====");

  // ---- 1. TTS 总线 ----
  TtsBus.begin(PIN_TTS_SDA, PIN_TTS_SCL, 10000);
  tts.beginI2C(TtsBus);
  Serial.printf("[BOOT] tts ready=%d\n", tts.ready());

  // 扫一遍 I2C，看 0x40 在不在（在 = 模块供电和接线都对）
  Serial.print("[I2C] TTS bus scan: ");
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    TtsBus.beginTransmission(a);
    if (TtsBus.endTransmission() == 0) { Serial.printf("0x%02X ", a); found++; }
  }
  Serial.printf("(%d found)\n", found);

  // ---- 2. ASR 总线（今晚不接也能跑，只是会显示 fail）----
  asr.begin(Wire, PIN_ASR_SDA, PIN_ASR_SCL, 100000);
  Serial.printf("[BOOT] asr online=%d addr=0x%02X\n", asr.online(), asr.address());

  // ---- 3. 念第一句 ----
  say(PH_BOOT, sizeof(PH_BOOT), "BOOT");

  Serial.println("命令：a=开场白  1=格兰芬多  2=斯莱特林  3=拉文克劳  4=赫奇帕奇  t=超时句  o=断网句  u=念任意文字");
}

void loop() {
  // ASR 有词就打印（方便明天验证模块通不通）
  uint8_t id = asr.poll(millis());
  if (id) Serial.printf("[ASR] 词条 ID = %d\n", id);

  if (!Serial.available()) return;
  switch (Serial.read()) {
    case 'a': say(PH_ASK, sizeof(PH_ASK), "ASK"); break;
    case '1': say(PH_GRYFFINDOR, sizeof(PH_GRYFFINDOR), "GRYFFINDOR"); break;
    case '2': say(PH_SLYTHERIN, sizeof(PH_SLYTHERIN), "SLYTHERIN"); break;
    case '3': say(PH_RAVENCLAW, sizeof(PH_RAVENCLAW), "RAVENCLAW"); break;
    case '4': say(PH_HUFFLEPUFF, sizeof(PH_HUFFLEPUFF), "HUFFLEPUFF"); break;
    case 't': say(PH_TIMEOUT, sizeof(PH_TIMEOUT), "TIMEOUT"); break;
    case 'o': say(PH_OFFLINE, sizeof(PH_OFFLINE), "OFFLINE"); break;

    // u = 测试"现场转码念任意文字"（speakUTF8）。
    // 这条通了，帽子就能念云端 LLM 写的话，不只是预录句。
    case 'u': {
      const char* t1 = "玄渊。你想要的东西不小，那就去拿。";
      bool ok = tts.speakUTF8(t1);
      Serial.printf("[TTS] UTF8 -> %s\n", ok ? "sent" : "FAIL");
      tts.waitDone();

      const char* t2 = "赤翎。你怕的不是输，是还没开始就退。";
      ok = tts.speakUTF8(t2);
      Serial.printf("[TTS] UTF8 -> %s\n", ok ? "sent" : "FAIL");
      tts.waitDone();
      Serial.println("[TTS] ---");
      break;
    }
  }
}
