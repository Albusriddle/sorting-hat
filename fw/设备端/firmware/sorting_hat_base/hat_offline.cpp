// ============================================================
// hat_offline.cpp —— 断网兜底 + 离线按钮模式
// ============================================================
#include "hat_offline.h"
#include "hat_config.h"
#include "hat_hw.h"
#include "hat_state.h"
#include "phrases_gbk.h"
#include "tts_xfs5152.h"

extern voice::XFS5152 tts;

static bool     s_netUp    = true;    // 上电默认假设有网，避免一直连不上时立刻进入离线
static bool     s_active   = false;
static bool     s_announced = false;
static uint8_t  s_houseIdx = 0;
static uint32_t s_offlineSince = 0;

// 与 persona/houses.yaml 同序：courage / ambition / wisdom / loyalty
static const uint8_t* HOUSE_PHRASE[4]  = { PH_GRYFFINDOR, PH_SLYTHERIN, PH_RAVENCLAW, PH_HUFFLEPUFF };
static const size_t   HOUSE_SIZE[4]    = { sizeof(PH_GRYFFINDOR), sizeof(PH_SLYTHERIN),
                                           sizeof(PH_RAVENCLAW), sizeof(PH_HUFFLEPUFF) };
static const char*    HOUSE_NAME[4]    = { "赤翎", "玄渊", "星枢", "穗垣" };

void offline_begin() {
  s_netUp = true;
  s_active = false;
  s_announced = false;
  s_houseIdx = 0;
  s_offlineSince = 0;
}

bool offline_active() { return s_active; }

void offline_set_network(bool up) {
  if (up == s_netUp) return;
  s_netUp = up;
  if (up) {
    s_offlineSince = 0;
    if (s_active) {
      s_active = false;
      s_announced = false;
      Serial.println("[OFF] 网络恢复，退出离线模式");
      hw_led_set((int)HatState::ARMED);
    }
  } else {
    s_offlineSince = millis();
  }
}

void offline_loop() {
  if (s_netUp) return;
  if (s_active) return;
  // 断网持续 OFFLINE_MS 才进入离线模式（瞬时抖动不触发）
  if (!s_offlineSince) s_offlineSince = millis();
  if (millis() - s_offlineSince < OFFLINE_MS) return;

  s_active = true;
  Serial.println("[OFF] 进入离线模式（网络断了）");
  if (!s_announced) {
    s_announced = true;
    hw_led_set(3);                 // 琥珀/黄 = 离线
    tts.speakGBK(PH_OFFLINE, sizeof(PH_OFFLINE));
  }
}

void offline_next_house() {
  s_houseIdx = (uint8_t)((s_houseIdx + 1) & 0x03);
  Serial.printf("[OFF] 学院 %u = %s\n", s_houseIdx, HOUSE_NAME[s_houseIdx]);
  tts.speakGBK(HOUSE_PHRASE[s_houseIdx], HOUSE_SIZE[s_houseIdx]);
}

void offline_clear_narrating() {
  // 目前离线模式不占用状态机，这里保留接口给以后扩展
}
