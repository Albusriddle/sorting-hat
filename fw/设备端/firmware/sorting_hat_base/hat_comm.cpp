// ============================================================
// hat_comm.cpp —— Wi-Fi + WebSocket + 协议编解码
//
// 协议以 host/app/protocol.py 为准（2026-11-16 用 probe.py 实测过）：
//   文本：{"type": ...}       （不是老文档里的 "t"）
//   上行 0x01 Opus / 0x04 PCM16k，后面跟 seq(u32 BE)
//   下行 0x02 + seq(u32 BE) + 载荷（可能是 Opus，也可能是裸 PCM）
//   下行的帧是 60 ms / 960 样本；上行我们发 20 ms / 320 样本
//
// 实测的一个坑：ready.audio.out 报 "24k"，但实际载荷算出来是 16 kHz。
// 所以解码采样率以"算出来的"为准，报的值只做参考 —— 见 guess_out_rate()。
// ============================================================
#include "hat_comm.h"
#include "hat_config.h"
#include "hat_state.h"
#include "hat_hw.h"
#include "hat_opus.h"
// secrets.h 存的是自己热点和电脑 IP，不进 git（见 .gitignore）。
// 没复制 secrets.h 时自动退回模板，保证 clone 下来能直接编译。
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.h.example"
#endif
#include "phrases_gbk.h"
#include "tts_xfs5152.h"

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <string.h>

extern voice::XFS5152 tts;    // 在 .ino 里创建

static WebSocketsClient s_ws;
static bool     s_up = false;
static uint32_t s_lastRx = 0;
static uint32_t s_txSeq = 0;
static uint32_t s_spkRate = AUDIO_HZ;
static bool     s_opusTx = false;

// 下行解码缓冲（60 ms @ 24k = 1440 样本，留余量到 2048）
static int16_t  s_decBuf[2048];

// ---------------- 学院 → 预录句 ----------------
static void speak_house(const char* house) {
  const char* cn = "未知";
  if (strcmp(house, "courage") == 0) {
#if HAT_HOUSE_ORIGINAL
    tts.speakGBK(PH_HOUSE_COURAGE_ORIG, sizeof(PH_HOUSE_COURAGE_ORIG)); cn = "格兰芬多";
#else
    tts.speakGBK(PH_HOUSE_COURAGE, sizeof(PH_HOUSE_COURAGE)); cn = "赤翎";
#endif
  } else if (strcmp(house, "ambition") == 0) {
#if HAT_HOUSE_ORIGINAL
    tts.speakGBK(PH_HOUSE_AMBITION_ORIG, sizeof(PH_HOUSE_AMBITION_ORIG)); cn = "斯莱特林";
#else
    tts.speakGBK(PH_HOUSE_AMBITION, sizeof(PH_HOUSE_AMBITION)); cn = "玄渊";
#endif
  } else if (strcmp(house, "wisdom") == 0) {
#if HAT_HOUSE_ORIGINAL
    tts.speakGBK(PH_HOUSE_WISDOM_ORIG, sizeof(PH_HOUSE_WISDOM_ORIG)); cn = "拉文克劳";
#else
    tts.speakGBK(PH_HOUSE_WISDOM, sizeof(PH_HOUSE_WISDOM)); cn = "星枢";
#endif
  } else if (strcmp(house, "loyalty") == 0) {
#if HAT_HOUSE_ORIGINAL
    tts.speakGBK(PH_HOUSE_LOYALTY_ORIG, sizeof(PH_HOUSE_LOYALTY_ORIG)); cn = "赫奇帕奇";
#else
    tts.speakGBK(PH_HOUSE_LOYALTY, sizeof(PH_HOUSE_LOYALTY)); cn = "穗垣";
#endif
  } else {
    tts.speakGBK(PH_RETRY, sizeof(PH_RETRY));
  }
  Serial.printf("[TTS] house=%s (%s)\n", house, cn);
}

// ---------------- 从 "opus/24k/60ms" 里取出 24000 ----------------
static uint32_t parse_rate(const char* fmt) {
  if (!fmt) return 0;
  const char* p = strchr(fmt, '/');          // 跳过 "opus"
  if (!p) return 0;
  ++p;
  uint32_t v = 0;
  bool any = false;
  while (*p >= '0' && *p <= '9') { v = v * 10 + (uint32_t)(*p - '0'); ++p; any = true; }
  if (!any || *p != 'k') return 0;           // 必须带 k，例如 16k
  return v * 1000;
}

// ---------------- 文本消息 ----------------
static void on_text(uint8_t* payload, size_t len) {
  s_lastRx = millis();

  StaticJsonDocument<768> doc;
  DeserializationError err = deserializeJson(doc, payload, len);
  if (err) {
    Serial.printf("[WS-RX] json err=%s\n", err.c_str());
    return;
  }

  const char* type = doc["type"] | "";
  if (strcmp(type, "ready") == 0) {
    const char* in  = doc["audio"]["in"]  | "?";
    const char* out = doc["audio"]["out"] | "?";
    uint32_t declared = parse_rate(out);
    // 实测：报 24k，实际 16k。先用报的值，后面 play 时会按帧长校正。
    if (declared) { s_spkRate = declared; opus_set_rate(declared); }
    Serial.printf("[NET] sid=%s in=%s out=%s (spk=%lu)\n",
                  (const char*)(doc["sid"] | "?"), in, out, (unsigned long)s_spkRate);
  } else if (strcmp(type, "pong") == 0) {
    Serial.println("[NET] pong");
  } else if (strcmp(type, "tts") == 0) {
    const char* st = doc["state"] | "";
    Serial.printf("[WS-RX] tts %s text=\"%s\"\n", st, (const char*)(doc["text"] | ""));
    if (strcmp(st, "start") == 0) {
      // S-07：把 host 的桥接句交给 CSK4002 念（speakUTF8 内部转 UNICODE）
      const char* txt = doc["text"] | "";
      if (txt[0]) tts.speakUTF8(txt);
      hat_ts_stamp(&HatTs::t5a);
      hw_speaker_open(s_spkRate);
      hw_mic_enable(false);                  // 半双工：帽子说话时关麦
      // 注意：必须走 comm_go() 而不是 hat_go()，否则 .ino 里的 on_enter_state()
      // 不会被调用，麦克风就永远恢复不了（念完一次帽子就再也听不见了）。
      if (hat_state_get() == HatState::THINKING) comm_go(HatState::SPEAKING, "TTS_START");
    } else if (strcmp(st, "stop") == 0) {
      hat_ts_stamp(&HatTs::tStop);
      hat_ts_dump();
      tts.stop();                 // 停 CSK4002（否则桥接句会继续念完）
      hw_speaker_stop();
      hw_mic_enable(true);
      if (hat_state_get() == HatState::SPEAKING) comm_go(HatState::ARMED, "TTS_STOP");
    }
  } else if (strcmp(type, "result") == 0) {
    const char* house = doc["house"] | "";
    Serial.printf("[WS-RX] result house=%s line=\"%s\"\n",
                  house, (const char*)(doc["line"] | ""));
    speak_house(house);                      // 念本地预录句，不念 line（里面有【占位】）
  } else if (strcmp(type, "error") == 0) {
    Serial.printf("[WS-RX] error code=%s degrade=%s fatal=%d\n",
                  (const char*)(doc["code"] | ""),
                  (const char*)(doc["degrade"] | ""),
                  (int)(doc["fatal"] | false));
  } else if (strcmp(type, "bye") == 0) {
    Serial.printf("[WS-RX] bye reason=%s\n", (const char*)(doc["reason"] | ""));
  } else {
    Serial.printf("[WS-RX] ignored type=%s\n", type);
  }
}

// ---------------- 二进制消息 ----------------
static void on_bin(uint8_t* payload, size_t len) {
  s_lastRx = millis();
  if (len < 5) { Serial.printf("[WS-BIN] short %u\n", (unsigned)len); return; }

  uint8_t kind = payload[0];
  if (kind != 0x02) {
    Serial.printf("[WS-BIN] unknown kind=0x%02X len=%u\n", kind, (unsigned)len);
    return;
  }

  const uint8_t* body = payload + 5;
  const size_t   n    = len - 5;

  // ---- 自动识别：先试 Opus，不行就当 PCM ----
  size_t pcmN = 0;
  if (!g_ts.t5b) hat_ts_stamp(&HatTs::t5b);     // 第一帧音频到达 = 真实内容起点
  if (opus_decode_or_passthrough(body, n, s_decBuf, 2048, &pcmN) && pcmN > 0) {
    static uint16_t logCount = 0;
    if (logCount++ < 5) Serial.printf("[WS-BIN] opus -> %u samples\n", (unsigned)pcmN);
    hw_speaker_play((const uint8_t*)s_decBuf, pcmN * sizeof(int16_t));
  } else {
    // 裸 PCM。用帧长反推采样率并校正（实测 1920 字节 = 960 样本 = 16 kHz / 60 ms）
    size_t samples = n / sizeof(int16_t);
    static uint16_t pcmLogCount = 0;
    if (pcmLogCount < 5) {
      pcmLogCount++;
      Serial.printf("[WS-BIN] 0x02 pcm %u B -> %u samples @%luHz\n",
                    (unsigned)n, (unsigned)samples, (unsigned long)s_spkRate);
    }
    static bool rateChecked = false;
    if (!rateChecked && samples > 0) {
      rateChecked = true;
      uint32_t guess = (uint32_t)(samples * 1000UL / 60UL);   // 上位机固定 60 ms 一帧
      if (guess >= 8000 && guess <= 48000 && guess != s_spkRate) {
        Serial.printf("[SPK] 帧长推算 %lu Hz（ready 报的是 %lu Hz），按实测值走\n",
                      (unsigned long)guess, (unsigned long)s_spkRate);
        s_spkRate = guess;
        hw_speaker_open(s_spkRate);
      }
    }
    hw_speaker_play(body, n);
  }
}

// ---------------- 事件 ----------------
static void on_ws_event(WStype_t type, uint8_t* payload, size_t len) {
  switch (type) {
    case WStype_CONNECTED:
      s_up = true;
      s_lastRx = millis();
      Serial.println("[NET] connected");
      break;
    case WStype_DISCONNECTED:
      s_up = false;
      Serial.println("[NET] disconnected");
      break;
    case WStype_TEXT: on_text(payload, len); break;
    case WStype_BIN:  on_bin(payload, len);  break;
    case WStype_ERROR: Serial.println("[NET] ws error"); break;
    default: break;
  }
}

// ---------------- 对外接口 ----------------
void comm_begin() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[NET] wifi");
  uint32_t t = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t < 15000UL) {
    delay(300);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf(" ok ip=%s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println(" FAIL（继续跑，串口命令照样能用）");
  }

  // 顺序很重要：回调要在 begin 之前注册，否则上位机连上立刻发的 ready 会丢
  s_ws.onEvent(on_ws_event);
  s_ws.setReconnectInterval(RECONNECT_MS);
  s_ws.setAuthorization("Bearer " TOKEN);
  s_ws.enableHeartbeat(HEARTBEAT_MS, 3000, 2);
  // token 同时走 query 参数：实测上位机对 Authorization 头判成 403，
  // 但 device_app.py 的 _authorized() 也认 ?token=...，这条路一定通。
  static char s_path[96];
  snprintf(s_path, sizeof(s_path), "/v1/voice?token=%s", TOKEN);
  s_ws.begin(HOST_IP, HOST_PORT, s_path, "sortinghat.voice.v1");

  s_lastRx = millis();
  s_opusTx = opus_init();
  Serial.printf("[NET] ws begin %s:%d%s（上行 %s）\n", HOST_IP, HOST_PORT, s_path,
                s_opusTx ? "Opus 0x01" : "PCM 0x04");
}

void comm_loop() {
  s_ws.loop();
}

// ---------------- 状态切换回调 ----------------
static void (*s_stateHooks)(HatState, const char*) = nullptr;

void comm_set_state_handler(void (*fn)(HatState, const char*)) { s_stateHooks = fn; }

void comm_go(HatState next, const char* event) {
  bool changed = (next != hat_state_get());
  hat_go(next, event);
  if (changed && s_stateHooks) s_stateHooks(next, event);
}

bool comm_up() { return s_up; }
uint32_t comm_last_rx_at() { return s_lastRx; }
bool comm_opus_tx() { return s_opusTx; }

void comm_send_listen_start() {
  if (!s_up) return;
  s_ws.sendTXT("{\"type\":\"listen\",\"state\":\"start\"}");
  Serial.println("[WS-TX] listen start");
}

void comm_send_vad_end() {
  if (!s_up) return;
  s_ws.sendTXT("{\"type\":\"vad\",\"ev\":\"speech_end\"}");
  Serial.println("[WS-TX] vad speech_end");
}

void comm_send_vad_start() {
  if (!s_up) return;
  s_ws.sendTXT("{\"type\":\"vad\",\"ev\":\"speech_start\"}");
  Serial.println("[WS-TX] vad speech_start");
}

static void send_json2(const char* type, const char* key, const char* val) {
  if (!s_up) return;
  char buf[96];
  int n = snprintf(buf, sizeof(buf), "{\"type\":\"%s\",\"%s\":\"%s\"}", type, key, val);
  if (n > 0) s_ws.sendTXT((uint8_t*)buf, (size_t)n);
  Serial.printf("[WS-TX] %s %s\n", type, val);
}

void comm_send_abort(const char* reason) { send_json2("abort", "reason", reason); }

// 把观众说的话发给上位机。上位机收到后存进 last_text，
// speech_end 时 ENGINE.run(..., last_text, ...) 就有了内容，不再依赖云端 ASR。
// JSON 转义：只处理会破坏 JSON 的两个字符（" 和 \），中文原样保留（UTF-8）。
void comm_send_text(const char* text) {
  if (!s_up || !text) return;

  char esc[256];
  size_t j = 0;
  for (size_t i = 0; text[i] && j + 2 < sizeof(esc); ++i) {
    char c = text[i];
    if (c == 34 || c == 92) {        // 34 = 双引号, 92 = 反斜杠，都需要转义
      esc[j++] = 92;
    }
    esc[j++] = c;
  }
  esc[j] = '\0';

  char buf[320];
  // 分开拼，避免 JSON 的花括号干扰源码括号检查
  int n = snprintf(buf, sizeof(buf), "{\"type\":\"text\",\"text\":\"%s\"}", esc);
  if (n > 0) s_ws.sendTXT((uint8_t*)buf, (size_t)n);    // NOLINT
  Serial.printf("[WS-TX] text \"%s\"\n", text);
}

void comm_send_bye(const char* reason) {
  if (!s_up) return;
  // 带 dev_ts：上位机靠它算 TTFC = t5b − t0（PROGRESS 待办）
  char buf[256];
  int n = snprintf(buf, sizeof(buf),
                   "{\"type\":\"bye\",\"reason\":\"%s\",\"dev_ts\":{\"t_arm\":%lu,\"t0\":%lu,"
                   "\"t5a\":%lu,\"t5b\":%lu,\"t_stop\":%lu}}",
                   reason, (unsigned long)g_ts.tArm, (unsigned long)g_ts.t0,
                   (unsigned long)g_ts.t5a, (unsigned long)g_ts.t5b,
                   (unsigned long)g_ts.tStop);
  if (n > 0) s_ws.sendTXT((uint8_t*)buf, (size_t)n);
  Serial.printf("[WS-TX] bye %s (dev_ts t0=%lu t5b=%lu)\n",
                reason, (unsigned long)g_ts.t0, (unsigned long)g_ts.t5b);
}

void comm_send_audio(const int16_t* samples, size_t count) {
  if (!s_up || !samples || count == 0) return;

  uint8_t frame[5 + (size_t)sizeof(int16_t) * AUDIO_SAMPLES];
  memcpy(frame + 5, samples, count * sizeof(int16_t));

  if (s_opusTx) {
    static uint8_t opusBuf[512];
    size_t plen = opus_encode(samples, count, opusBuf, sizeof(opusBuf));
    if (plen > 0) {
      frame[0] = 0x01;
      frame[1] = (uint8_t)(s_txSeq >> 24); frame[2] = (uint8_t)(s_txSeq >> 16);
      frame[3] = (uint8_t)(s_txSeq >> 8);  frame[4] = (uint8_t)(s_txSeq);
      ++s_txSeq;
      memcpy(frame + 5, opusBuf, plen);
      s_ws.sendBIN(frame, 5 + plen);
      return;
    }
    // 编码失败 → 本次退回 PCM，不要丢帧
  }

  frame[0] = 0x04;
  frame[1] = (uint8_t)(s_txSeq >> 24); frame[2] = (uint8_t)(s_txSeq >> 16);
  frame[3] = (uint8_t)(s_txSeq >> 8);  frame[4] = (uint8_t)(s_txSeq);
  ++s_txSeq;
  s_ws.sendBIN(frame, 5 + count * sizeof(int16_t));
}
