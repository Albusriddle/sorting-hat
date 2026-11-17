// ============================================================
// hat_opus.cpp —— Opus 编解码实现
//
// 用 arduino-audio-tools 的 OpusAudioEncoder / Decoder，底层是 esp-opus。
// 关掉 HAT_ENABLE_OPUS 时全部返回失败，上层自动退回 PCM。
// ============================================================
#include "hat_opus.h"
#include "hat_config.h"

#ifdef HAT_ENABLE_OPUS

#include "AudioTools.h"
#include "AudioTools/AudioCodecs/CodecOpus.h"

// 发送侧/接收侧各一个缓冲，放在静态区避免栈溢出
static uint8_t s_encOut[512];

static audio_tools::OpusAudioEncoder s_enc;
static audio_tools::OpusAudioDecoder s_dec;

static bool     s_encOk = false;
static bool     s_decOk = false;
static uint32_t s_decHz = AUDIO_HZ;

bool opus_init() {
  // ---- 编码器：16 kHz / 单声道 / 20 ms ----
  audio_tools::AudioInfo encInfo(AUDIO_HZ, 1, 16);
  s_encOk = s_enc.begin(encInfo);

  // ---- 解码器：默认 16 kHz（上位机现在发 16k PCM）----
  audio_tools::AudioInfo decInfo(s_decHz, 1, 16);
  s_decOk = s_dec.begin(decInfo);

  Serial.printf("[OPUS] encoder=%s decoder=%s rate=%lu complexity=%d\n",
                s_encOk ? "ok" : "FAIL", s_decOk ? "ok" : "FAIL",
                (unsigned long)s_decHz, OPUS_COMPLEXITY);
  return s_encOk && s_decOk;
}

size_t opus_encode(const int16_t* pcm, size_t samples, uint8_t* out, size_t outCap) {
  if (!s_encOk || !pcm || !out) return 0;
  if (samples != AUDIO_SAMPLES) return 0;                 // 必须正好 320 样本

  const uint8_t* in = (const uint8_t*)pcm;
  size_t inLeft = samples * sizeof(int16_t);

  // write 返回吃进去的字节数，编码结果用 readBytes 取
  size_t wrote = s_enc.write((const uint8_t*)in, inLeft);
  if (wrote != inLeft) return 0;

  size_t avail = s_enc.available();
  if (avail == 0) return 0;
  if (avail > outCap) avail = outCap;
  return s_enc.readBytes(out, avail);
}

void opus_set_rate(uint32_t hz) {
  if (!hz || hz == s_decHz) return;
  s_decHz = hz;
  if (s_decOk) {
    s_dec.end();
    audio_tools::AudioInfo info(s_decHz, 1, 16);
    s_decOk = s_dec.begin(info);
    Serial.printf("[OPUS] decoder rate -> %lu Hz (%s)\n",
                  (unsigned long)s_decHz, s_decOk ? "ok" : "FAIL");
  }
}

// 解码结果像不像真语音：全零或幅度几乎不变，就当不是 Opus
static bool plausible_pcm(const int16_t* pcm, size_t n) {
  if (n < 64) return false;
  int32_t minV = 32767, maxV = -32768;
  int32_t energy = 0;
  for (size_t i = 0; i < n; ++i) {
    int32_t v = pcm[i];
    if (v < minV) minV = v;
    if (v > maxV) maxV = v;
    energy += (v < 0 ? -v : v);
  }
  energy /= (int32_t)n;
  if (energy == 0 && minV == maxV) return false;           // 全零或没起伏，不可信
  return true;
}

bool opus_decode_or_passthrough(const uint8_t* payload, size_t len,
                                int16_t* pcmOut, size_t pcmCap, size_t* pcmLen) {
  *pcmLen = 0;
  if (!s_decOk || !payload || len == 0) return false;

  s_dec.write(payload, len);
  size_t avail = s_dec.available();
  if (avail < sizeof(int16_t) * 32) return false;          // 太短，多半是误判
  size_t bytes = avail;
  if (bytes > pcmCap * sizeof(int16_t)) bytes = pcmCap * sizeof(int16_t);

  size_t got = s_dec.readBytes((uint8_t*)pcmOut, bytes);
  if (got < sizeof(int16_t) * 32) return false;

  size_t n = got / sizeof(int16_t);
  if (!plausible_pcm(pcmOut, n)) return false;

  *pcmLen = n;
  return true;
}

#else  // ---- 没有开启 Opus：全部空实现 ----

bool opus_init() { return false; }

size_t opus_encode(const int16_t* pcm, size_t samples, uint8_t* out, size_t outCap) {
  (void)pcm; (void)samples; (void)out; (void)outCap;
  return 0;
}

bool opus_decode_or_passthrough(const uint8_t* payload, size_t len,
                                int16_t* pcmOut, size_t pcmCap, size_t* pcmLen) {
  (void)payload; (void)len; (void)pcmOut; (void)pcmCap;
  *pcmLen = 0;
  return false;
}

void opus_set_rate(uint32_t hz) { (void)hz; }

#endif
