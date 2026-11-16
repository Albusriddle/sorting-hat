#include <Wire.h>
#include "hat_config.h"
#include "hat_state.h"
#include "hat_hw.h"
#include "hat_comm.h"
#include "hat_mic.h"
#include "hat_offline.h"
#include "hat_intent.h"
#include "asr_wonderecho.h"
#include "tts_xfs5152.h"
#include "phrases_gbk.h"

// 唤醒词编号在 hat_config.h（5 号）；1–4 号是四句内容（S-08）。

TwoWire TtsBus(1);
voice::WonderEcho asr;
voice::XFS5152  tts;

// ---------------- 状态迁移的副作用 ----------------
static void on_enter_state(HatState s, const char*) {
  switch (s) {
    case HatState::LISTENING:
      hw_mic_enable(true);
      mic_set_listening(true);
      break;
    case HatState::THINKING:
      mic_set_listening(false);
      break;
    case HatState::SPEAKING:
      mic_set_listening(false);
      break;
    case HatState::ARMED:
      mic_set_listening(false);
      hw_mic_enable(true);
      break;
    default:
      mic_set_listening(false);
      break;
  }
}

// 让通信模块（收到 tts start/stop）也能走同一套副作用。
// lazy init：回调函数 on_enter_state 定义在上面，这里再注册一次，避免顺序问题。
static bool g_hookReady = false;
static void ensure_state_hook() {
  if (!g_hookReady) { comm_set_state_handler(on_enter_state); g_hookReady = true; }
}

static void go(HatState next, const char* ev) {
  ensure_state_hook();
  comm_go(next, ev);
}

// ---------------- 唤醒 ----------------
static void start_listening(const char* ev) {
  if (hat_state_get() != HatState::OFF_ST && hat_state_get() != HatState::ARMED) return;

  go(HatState::ARMED, "WAKE_WORD");
  if (offline_active()) {
    // 离线模式不联网，只提示
    Serial.println("[OFF] 离线模式，不上行");
    return;
  }
  comm_send_listen_start();
  hat_ts_reset();                              // t_arm = 现在，其余清零
  go(HatState::LISTENING, ev);
}

static void poll_asr() {
  if (!asr.online()) return;
  uint8_t id = asr.poll(millis());
  if (id == 0) return;

  // 合法编号只有 1..5。开机瞬间 I2C 偶发读到垃圾值（实测出现过 242），
  // 不在这里挡掉，会被当成"说了个不存在的词条"往下走。
  if (id > 5) {
    Serial.printf("[ASR] 读到非法编号 %u，忽略\n", id);
    return;
  }

  if (id == ASR_WAKE_WORD_ID) {
    Serial.println("[ASR] 唤醒词");
    if (hat_state_get() == HatState::OFF_ST || hat_state_get() == HatState::ARMED) {
      start_listening("WAKE_WORD");
    }
    return;
  }

  // 观众说的内容：只在 LISTENING 状态下才理，避免 ARMED 待机时误触发
  if (hat_state_get() == HatState::LISTENING) {
    hat_intent_on_word_id(id);

    for (int i = 0; i < 5; ++i) {            // 补 100ms 音频帧，保持与 e 键一致的节奏
      mic_pump_frame();
      delay(20);
    }
    comm_send_vad_end();
    hat_ts_stamp(&HatTs::t0);
    go(HatState::THINKING, "VAD_END");
  } else {
    Serial.printf("[ASR] 编号 %u（非唤醒词，当前不在听，忽略）\n", id);
  }
}

// ---------------- 串口事件 ----------------
static void handle_serial() {
  if (!Serial.available()) return;

  switch (Serial.read()) {
    case 'w': start_listening("LISTEN_START"); break;

    case 'e':                                  // 模拟"说完了"
      if (hat_state_get() == HatState::LISTENING) {
        for (int i = 0; i < 25; ++i) {          // 25 × 20 ms = 0.5 秒
          mic_pump_frame();
          delay(20);
        }
        comm_send_vad_end();
        hat_ts_stamp(&HatTs::t0);
        go(HatState::THINKING, "VAD_END");
      }
      break;

    case 'b':                                  // 模拟按钮短按
      if (offline_active()) {
        offline_next_house();
        break;
      }
      if (hat_state_get() != HatState::OFF_ST && hat_state_get() != HatState::ERROR_ST) {
        comm_send_abort("button");
        hw_speaker_stop();
        tts.stop();
        go(HatState::ARMED, "ABORT");
      }
      break;

    case 'x':
      go(HatState::ERROR_ST, "FORCE");
      hw_led_blink(2, 120);
      delay(800);
      go(HatState::ARMED, "ERR_RECOVER");
      break;

    case 'o':
      Serial.println("[OFF] 手动进入离线模式（模拟断网）");
      offline_set_network(false);
      break;

    case 'k':
      Serial.printf("[VAD] 当前能量=%ld 阈值=%d\n",
                    (long)mic_last_energy(), VAD_ENERGY_THRESH);
      break;

    case 'a': tts.speakGBK(PH_ASK, sizeof(PH_ASK)); break;
    // 1-4 = 试听四院预录句，跟着 HAT_HOUSE_ORIGINAL 走（与 hat_comm.cpp 的 speak_house 一致）
    case '1':
#if HAT_HOUSE_ORIGINAL
      tts.speakGBK(PH_HOUSE_COURAGE_ORIG, sizeof(PH_HOUSE_COURAGE_ORIG)); break;
#else
      tts.speakGBK(PH_HOUSE_COURAGE, sizeof(PH_HOUSE_COURAGE)); break;
#endif
    case '2':
#if HAT_HOUSE_ORIGINAL
      tts.speakGBK(PH_HOUSE_AMBITION_ORIG, sizeof(PH_HOUSE_AMBITION_ORIG)); break;
#else
      tts.speakGBK(PH_HOUSE_AMBITION, sizeof(PH_HOUSE_AMBITION)); break;
#endif
    case '3':
#if HAT_HOUSE_ORIGINAL
      tts.speakGBK(PH_HOUSE_WISDOM_ORIG, sizeof(PH_HOUSE_WISDOM_ORIG)); break;
#else
      tts.speakGBK(PH_HOUSE_WISDOM, sizeof(PH_HOUSE_WISDOM)); break;
#endif
    case '4':
#if HAT_HOUSE_ORIGINAL
      tts.speakGBK(PH_HOUSE_LOYALTY_ORIG, sizeof(PH_HOUSE_LOYALTY_ORIG)); break;
#else
      tts.speakGBK(PH_HOUSE_LOYALTY, sizeof(PH_HOUSE_LOYALTY)); break;
#endif

    case 'p': hat_intent_dump(); break;        // 打印词条表

    case 'P': {
      Serial.println("[ASR] 开始写入词条…");
      if (!asr.eraseWords()) { Serial.println("[ASR] 擦除失败"); break; }
      struct { uint8_t id; const char* py; } words[] = {
        {5, "kai shi"},                      // ← 第一条；先用官方例程验证过的词排除拼音因素
        {1, "wo pa shu"},
        {2, "wo yao de hen da"},
        {3, "wo xi huan chai kai xiang"},
        {4, "wo zai hu shen bian"},
      };
      bool allOk = true;
      for (auto& w : words) {
        if (asr.addWords(w.id, w.py)) Serial.printf("[ASR] +%u %s\n", w.id, w.py);
        else { Serial.printf("[ASR] 写入失败 id=%u\n", w.id); allOk = false; }
      }

      if (allOk && asr.setMode(1)) Serial.println("[ASR] 词条写入完成，模式=1(循环)，第一条=唤醒词");
      else Serial.println("[ASR] 写入未全部成功，请重试");
      break;
    }


    case 'A': hat_intent_on_word_id(1); break;
    case 'B': hat_intent_on_word_id(2); break;
    case 'C': hat_intent_on_word_id(3); break;
    case 'D': hat_intent_on_word_id(4); break;

    default: break;
  }
}

// ---------------- 按钮 ----------------
static void handle_button() {
  if (hw_btn_long_press()) {
    Serial.println("[BTN] 长按 → 重新连接/退出离线");
    offline_set_network(true);
    return;
  }
  if (!hw_btn_pressed()) return;

  if (offline_active()) { offline_next_house(); return; }

  // 短按：OFF/ARMED = 手动开始（无模块也能演）；其他状态 = 打断
  if (hat_state_get() == HatState::OFF_ST || hat_state_get() == HatState::ARMED) {
    start_listening("BTN_START");
    return;
  }

  comm_send_abort("button");
  hw_speaker_stop();
  tts.stop();
  go(HatState::ARMED, "ABORT");
}

// ---------------- setup ----------------
void setup() {
  Serial.begin(115200);
  delay(1200);
  Serial.println("\n===== sorting hat · base =====");

  // 1. 两块幻尔模块（与组长 demo 相同的接法）
  TtsBus.begin(PIN_TTS_SDA, PIN_TTS_SCL, 10000);
  tts.beginI2C(TtsBus);
  asr.begin(Wire, PIN_ASR_SDA, PIN_ASR_SCL, 100000);

  // 2. 其余硬件（按 hat_config.h 的开关决定真实/空实现）
  hw_begin();
  Serial.printf("[BOOT] asr=%s tts=%s %s\n",
                asr.online() ? "ok" : "off",
                tts.ready() ? "ok" : "off",
                hw_status());

  // 3. 兜底模块
  offline_begin();

  // 4. 念开场白
  tts.speakGBK(PH_BOOT, sizeof(PH_BOOT));

  // 5. 连上位机
  comm_begin();

  Serial.println("命令：w 唤醒  e 说完  b 打断  x 故障  o 离线  k VAD  a/1-4 试听  p 词条表  A-D 模拟识别");
}

// ---------------- loop ----------------
void loop() {
  comm_loop();
  poll_asr();
  handle_serial();
  handle_button();

  // 网络状态同步给兜底模块
  static int8_t lastNet = -1;
  int8_t net = comm_up() ? 1 : 0;
  if (net != lastNet) {
    lastNet = net;
    offline_set_network(net == 1);
  }
  offline_loop();

  // VAD：只有真正在听的时候才跑
  {
    bool started = false, ended = false;
    mic_loop(&started, &ended);
    if (started) comm_send_vad_start();
    if (ended && hat_state_get() == HatState::LISTENING) {
      comm_send_vad_end();
      hat_ts_stamp(&HatTs::t0);
      go(HatState::THINKING, "VAD_END");
    }
  }

  // 说话超时
  if (hat_state_get() == HatState::LISTENING &&
      millis() - g_stateAt > LISTEN_TIMEOUT_MS) {
    comm_send_bye("timeout");
    tts.speakGBK(PH_TIMEOUT, sizeof(PH_TIMEOUT));
    go(HatState::ARMED, "TIMEOUT");
  }
}
