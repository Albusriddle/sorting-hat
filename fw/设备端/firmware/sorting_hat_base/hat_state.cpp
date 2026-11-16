// ============================================================
// hat_state.cpp —— 状态机的实现
// ============================================================
#include "hat_state.h"
#include "hat_hw.h"

HatState g_state = HatState::OFF_ST;
uint32_t g_stateAt = 0;

static const char* kNames[] = {"OFF", "ARMED", "LISTENING", "THINKING", "SPEAKING", "ERROR"};
static const char* kLeds[]  = {"暗", "白", "青", "琥珀", "学院色", "红"};

const char* hat_state_name(HatState s) { return kNames[(int)s]; }
const char* hat_state_led(HatState s)  { return kLeds[(int)s]; }
HatState    hat_state_get()            { return g_state; }

bool hat_state_in_listen_or_think() {
  return g_state == HatState::LISTENING || g_state == HatState::THINKING;
}

void hat_go(HatState next, const char* event) {
  if (next == g_state) return;
  Serial.printf("[ST] %s -> %s (ev=%s, t=%lu)\n",
                hat_state_name(g_state), hat_state_name(next), event,
                (unsigned long)millis());
  g_state = next;
  g_stateAt = millis();
  Serial.printf("[LED] %s\n", hat_state_led(next));
  hw_led_set((int)next);

  // 离开 SPEAKING 时立刻停播放（打断、超时、出错都走这里）
  if (next != HatState::SPEAKING) hw_speaker_stop();
}

// ---------------- 时间戳 ----------------
HatTs g_ts = {};

void hat_ts_stamp(uint32_t HatTs::*field) {
  g_ts.*field = millis();
}

void hat_ts_reset() {
  g_ts.tArm = millis();          // 进入 LISTENING 时记录起点
  g_ts.t0 = g_ts.t5a = g_ts.t5b = g_ts.tStop = 0;
}

void hat_ts_dump() {
  uint32_t t0 = g_ts.t0 ? g_ts.t0 : g_ts.tArm;
  Serial.printf("[TS] arm=%lu t0=%lu t5a=%lu t5b=%lu stop=%lu\n",
                (unsigned long)g_ts.tArm, (unsigned long)g_ts.t0,
                (unsigned long)g_ts.t5a, (unsigned long)g_ts.t5b,
                (unsigned long)g_ts.tStop);
  // 设备打点可能早于 t0（WS 发送与下行竞争），无符号相减会变成 2^32-差值
  if (g_ts.t5a && t0) {
    int32_t d = (int32_t)(g_ts.t5a - t0);
    if (d >= 0) Serial.printf("[TS] TTFV=%ld ms\n", (long)d);
    else        Serial.printf("[TS] TTFV=n/a (t5a<t0 by %ld ms)\n", (long)(-d));
  }
  if (g_ts.t5b && t0) {
    int32_t d = (int32_t)(g_ts.t5b - t0);
    if (d >= 0) Serial.printf("[TS] TTFC=%ld ms\n", (long)d);
    else        Serial.printf("[TS] TTFC=n/a (t5b<t0 by %ld ms)\n", (long)(-d));
  }
}
