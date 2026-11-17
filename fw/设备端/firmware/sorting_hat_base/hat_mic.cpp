// ============================================================
// hat_mic.cpp —— 麦克风采音 + 能量 VAD
// ============================================================
#include "hat_mic.h"
#include "hat_config.h"
#include "hat_hw.h"
#include "hat_comm.h"

static bool     s_listening = false;
static int32_t  s_lastEnergy = 0;

// VAD 状态
static bool     s_speechActive = false;
static uint32_t s_speechStartAt = 0;
static uint32_t s_silenceSince  = 0;
static uint32_t s_voiceSince    = 0;

// 每 20 ms 一帧，用 millis() 卡节奏，防读太快抽干 DMA
static uint32_t s_nextFrameAt = 0;

static int32_t frame_energy(const int16_t* pcm, size_t n) {
  if (!n) return 0;
  int64_t sum = 0;
  for (size_t i = 0; i < n; ++i) {
    int32_t v = pcm[i];
    sum += (v < 0 ? -v : v);
  }
  return (int32_t)(sum / (int64_t)n);
}

void mic_reset_vad() {
  s_speechActive  = false;
  s_speechStartAt = 0;
  s_silenceSince  = 0;
  s_voiceSince    = 0;
  s_nextFrameAt   = 0;
  s_lastEnergy    = 0;
}

void mic_set_listening(bool on) {
  s_listening = on;
  if (on) mic_reset_vad();
}

int32_t mic_last_energy() { return s_lastEnergy; }

void mic_pump_frame() {
  int16_t buf[AUDIO_SAMPLES];
  size_t n = hw_mic_read(buf, AUDIO_SAMPLES);

  // 没开 VAD 时真实麦克风数据照发，由服务端判 VAD
  if (n > 0) comm_send_audio(buf, n);

#ifndef HAT_ENABLE_VAD
  s_lastEnergy = frame_energy(buf, n);
  (void)s_speechActive; (void)s_speechStartAt;
  (void)s_silenceSince; (void)s_voiceSince;
#endif
}

void mic_loop(bool* vadStarted, bool* vadEnded) {
  *vadStarted = false;
  *vadEnded   = false;

  if (!s_listening) { s_nextFrameAt = 0; return; }

  uint32_t now = millis();
  if (s_nextFrameAt && (int32_t)(now - s_nextFrameAt) < 0) return;
  s_nextFrameAt = now + 20;                    // 20 ms 一帧

  int16_t buf[AUDIO_SAMPLES];
  size_t n = hw_mic_read(buf, AUDIO_SAMPLES);
  if (n == 0) return;

  comm_send_audio(buf, n);

  int32_t e = frame_energy(buf, n);
  s_lastEnergy = e;

#ifdef HAT_ENABLE_VAD
  bool loud = (e > VAD_ENERGY_THRESH);

  if (!s_speechActive) {
    // 起振：连续 VAD_DEBOUNCE_MS 超阈值才算
    if (loud) {
      if (!s_voiceSince) s_voiceSince = now;
      if (now - s_voiceSince >= VAD_DEBOUNCE_MS) {
        s_speechActive  = true;
        s_speechStartAt = now;
        s_silenceSince  = 0;
        *vadStarted = true;
        Serial.printf("[VAD] start (e=%ld)\n", (long)e);
      }
    } else {
      s_voiceSince = 0;
    }
  } else {
    // 已开口：连续 VAD_TAIL_MS 静音就算说完
    if (loud) {
      s_silenceSince = 0;
    } else {
      if (!s_silenceSince) s_silenceSince = now;
      if (now - s_silenceSince >= VAD_TAIL_MS) {
        uint32_t spoke = s_silenceSince - s_speechStartAt;
        s_speechActive = false;
        s_silenceSince = 0;
        if (spoke >= VAD_MIN_SPEECH_MS) {
          *vadEnded = true;
          Serial.printf("[VAD] end (spoke %lu ms)\n", (unsigned long)spoke);
        } else {
          Serial.printf("[VAD] too short (%lu ms), ignore\n", (unsigned long)spoke);
        }
      }
    }
  }
#endif
}
