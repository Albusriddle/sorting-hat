// ============================================================
// sorting_hat_base.ino —— 只放 setup() / loop()
//
// Arduino 官方构建流程：.ino 会被 IDE 在前面自动插入函数原型，
// 原型出现在任何类型定义之前。函数参数用到自定义类型就会报 "not declared"。
// 所以除了 setup/loop 之外，所有逻辑都放进了 .h / .cpp。
//
// 文件清单：
//   hat_config.h     引脚、音频参数、时间、VAD 阈值、编译开关
//   hat_state.*      6 态状态机
//   hat_hw.*         硬件抽象（麦克风/喇叭/灯/按钮，各有编译开关）
//   hat_comm.*       Wi-Fi + WebSocket + 协议 + Opus 收发
//   hat_opus.*       Opus 编解码（HAT_ENABLE_OPUS）
//   hat_mic.*        采音节奏 + 能量 VAD（HAT_ENABLE_VAD）
//   hat_offline.*    断网兜底 + 离线按钮模式
//   secrets.h        Wi-Fi 账号、上位机 IP（不要提交）
//   asr_wonderecho.* 组长驱动
//   tts_xfs5152.*    组长驱动
//   phrases_gbk.h    组长台词表
//
// 串口命令（代替真硬件）：
//   w 唤醒   e 说完了   b 打断   x 故障   o 手动进离线
//   a 试听开场白   1-4 试听四院   k 打印 VAD 能量
// ============================================================
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

// 唤醒词是 1 号词条（模块里第一个烧的就是"分院帽"）。
// 其余编号 = 观众说的内容。
#define ASR_WAKE_WORD_ID 1

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

// ---------------- 语音识别（LD3320A）轮询 ----------------
// 模块每识别到一个词条就回一个编号。这里区分两种情况：
//   编号 == 唤醒词 → 进入 ARMED 并开始收音
//   其他编号     → 当成"观众说了这句话"，转成文字发给云端
static void poll_asr() {
  if (!asr.online()) return;
  uint8_t id = asr.poll(millis());
  if (id == 0) return;

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
    case '1': tts.speakGBK(PH_GRYFFINDOR, sizeof(PH_GRYFFINDOR)); break;
    case '2': tts.speakGBK(PH_SLYTHERIN, sizeof(PH_SLYTHERIN)); break;
    case '3': tts.speakGBK(PH_RAVENCLAW, sizeof(PH_RAVENCLAW)); break;
    case '4': tts.speakGBK(PH_HUFFLEPUFF, sizeof(PH_HUFFLEPUFF)); break;

    case 'p': hat_intent_dump(); break;        // 打印词条表

    // 大写 A/B/C/D = 手动模拟"模块识别到第 1/2/3/4 号词条"，
    // 不用真模块也能把"词条 → 文字 → 云端"这条路验通
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

  // 短按：任何状态都可打断；ARMED 下短按 = 手动开始说话（备用入口）
  if (hat_state_get() == HatState::ARMED) { start_listening("BTN_START"); return; }

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
