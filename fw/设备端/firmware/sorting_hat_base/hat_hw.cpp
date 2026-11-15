// ============================================================
// hat_hw.cpp —— 硬件抽象层的实现
//
// 每个硬件都被 #ifdef 包着：开关没开时是空实现，代码能编、能跑、不出声。
// 板上验证一个就打开一个开关，出错时很容易知道是哪个硬件的问题。
// ============================================================
#include "hat_hw.h"
#include "hat_config.h"

// 条件编译里用到的库，只在需要时 include
#ifdef HAT_ENABLE_MIC
#include <driver/i2s.h>
#endif
#ifdef HAT_ENABLE_SPK
#include <driver/i2s.h>
#endif
#ifdef HAT_ENABLE_LED
#include <Adafruit_NeoPixel.h>
#endif

// ============================================================
// 状态串
// ============================================================
static char s_status[96];

const char* hw_status() {
  snprintf(s_status, sizeof(s_status),
           "mic=%s spk=%s led=%s btn=%s opus=%s",
           hw_mic_ok() ? "ok" : "off",
           hw_speaker_ok() ? "ok" : "off",
#ifdef HAT_ENABLE_LED
           "on",
#else
           "off",
#endif
           hw_btn_ok() ? "ok" : "off",
#ifdef HAT_ENABLE_OPUS
           "on"
#else
           "off"
#endif
  );
  return s_status;
}

// ============================================================
// 喇叭（MAX98357A / I2S_NUM_1 输出）
// ============================================================
static bool     s_spkOk  = false;
static uint32_t s_spkHz  = AUDIO_HZ;
static volatile size_t s_spkPending = 0;

#ifdef HAT_ENABLE_SPK

static void spk_configure(uint32_t hz) {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = hz;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 6;
  cfg.dma_buf_len = 320;          // 6 × 320 = 1920 样本 ≈ 120 ms 缓冲
  cfg.use_apll = false;
  cfg.tx_desc_auto_clear = true;

  i2s_pin_config_t pins = {};
  pins.mck_io_num   = I2S_PIN_NO_CHANGE;
  pins.bck_io_num   = PIN_SPK_BCLK;
  pins.ws_io_num    = PIN_SPK_LRC;
  pins.data_out_num = PIN_SPK_DIN;
  pins.data_in_num  = I2S_PIN_NO_CHANGE;

  i2s_driver_install(I2S_NUM_1, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_1, &pins);
  i2s_zero_dma_buffer(I2S_NUM_1);
}

#else  // 没有喇叭

static void spk_configure(uint32_t hz) { (void)hz; }

#endif

bool hw_speaker_ok() { return s_spkOk; }

void hw_speaker_open(uint32_t hz) {
  s_spkHz = hz ? hz : AUDIO_HZ;
  s_spkPending = 0;
#ifdef HAT_ENABLE_SPK
  // 采样率变了就要重装驱动（ready 里的采样率可能是 16k 或 24k）
  static bool installed = false;
  static uint32_t installedHz = 0;
  if (installed && installedHz == s_spkHz) return;
  if (installed) { i2s_driver_uninstall(I2S_NUM_1); installed = false; }
  spk_configure(s_spkHz);
  installed = true;
  installedHz = s_spkHz;
  s_spkOk = true;
  Serial.printf("[SPK] open %lu Hz\n", (unsigned long)s_spkHz);
#else
  s_spkOk = false;
#endif
}

void hw_speaker_play(const uint8_t* pcm, size_t bytes) {
#ifdef HAT_ENABLE_SPK
  if (!s_spkOk || !pcm || bytes == 0) { s_spkPending = 0; return; }
  size_t written = 0;
  // 注意：这里会阻塞到 DMA 吃下数据。一帧 60 ms 的音频最多阻塞 60 ms，
  // 而 WS 接收在本线程里，所以要保证 dma_buf 足够大，避免丢包。
  esp_err_t err = i2s_write(I2S_NUM_1, pcm, bytes, &written, pdMS_TO_TICKS(100));
  if (err != ESP_OK || written < bytes) {
    Serial.printf("[SPK] write drop %u/%u bytes\n", (unsigned)(bytes - written), (unsigned)bytes);
  }
  s_spkPending = 0;
#else
  (void)pcm;
  // 没有喇叭时只统计，不逐帧打印（否则一秒几十行刷屏）
  static uint32_t total = 0;
  static uint32_t lastLog = 0;
  total += bytes;
  if (millis() - lastLog > 1000) {
    lastLog = millis();
    Serial.printf("[SPK] fake playback %lu bytes so far\n", (unsigned long)total);
  }
#endif
}

void hw_speaker_stop() {
#ifdef HAT_ENABLE_SPK
  if (s_spkOk) {
    i2s_zero_dma_buffer(I2S_NUM_1);
    Serial.println("[SPK] stop (flush)");
  }
#endif
  s_spkPending = 0;
}

size_t hw_speaker_backlog() { return s_spkPending; }

// ============================================================
// 麦克风（INMP441 / I2S_NUM_0 输入）
// ============================================================
#ifdef HAT_ENABLE_MIC

static bool s_micOk = false;
static bool s_micOn = true;
static int32_t  s_micRaw[AUDIO_SAMPLES];      // INMP441 是 24 bit 装在 32 bit 里
static bool     s_micStarted = false;

static void mic_configure() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
  cfg.sample_rate = AUDIO_HZ;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;   // INMP441 固定 32 bit 读
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;    // L/R 脚接地 = 左声道
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 4;
  cfg.dma_buf_len = 160;
  cfg.use_apll = false;

  i2s_pin_config_t pins = {};
  pins.mck_io_num   = I2S_PIN_NO_CHANGE;
  pins.bck_io_num   = PIN_MIC_BCLK;
  pins.ws_io_num    = PIN_MIC_WS;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num  = PIN_MIC_SD;

  i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pins);
  i2s_zero_dma_buffer(I2S_NUM_0);
}

#endif

bool hw_mic_ok() {
#ifdef HAT_ENABLE_MIC
  return s_micOk;
#else
  return false;
#endif
}

void hw_mic_enable(bool on) {
#ifdef HAT_ENABLE_MIC
  // 半双工：喇叭响的时候关麦，否则帽子会"听见自己"
  if (!s_micStarted) return;
  if (on && !s_micOn)  { i2s_start(I2S_NUM_0); s_micOn = true; }
  if (!on && s_micOn)  { i2s_stop(I2S_NUM_0);  s_micOn = false; }
  s_micOn = on;
#else
  (void)on;
#endif
}

size_t hw_mic_read(int16_t* buf, size_t samples) {
  if (!buf || samples == 0) return 0;

#ifdef HAT_ENABLE_MIC
  // 麦克风没起来 / 当前关麦：返回 0，让上层跳过这一帧，
  // 不要返回一整帧静音——那会被当成"真的在收音"，烧板时会严重误导。
  if (!s_micOk || !s_micOn) return 0;
  size_t want = samples;
  size_t got  = 0;
  // INMP441 输出 32 bit 左对齐的 24 bit 数据：取高 16 bit 就是 16 bit PCM
  while (got < want) {
    size_t need = (want - got) * sizeof(int32_t);
    size_t n = 0;
    if (i2s_read(I2S_NUM_0, (void*)(s_micRaw + got), need, &n, pdMS_TO_TICKS(200)) != ESP_OK) break;
    size_t cnt = n / sizeof(int32_t);
    if (cnt == 0) continue;
    for (size_t i = 0; i < cnt; ++i) {
      buf[got + i] = (int16_t)(s_micRaw[got + i] >> 16);
    }
    got += cnt;
  }
  return got;
#else
  memset(buf, 0, samples * sizeof(int16_t));
  return samples;
#endif
}

// ============================================================
// 灯（WS2812 ×8）
// ============================================================
#ifdef HAT_ENABLE_LED
#define LED_COUNT 8
static Adafruit_NeoPixel s_strip(LED_COUNT, PIN_LED, NEO_GRB + NEO_KHZ800);
#endif

void hw_led_set(int state_index) {
#ifdef HAT_ENABLE_LED
  // 颜色与 persona/houses.yaml 一致；亮度限制 30%，别把帽子烤了
  uint32_t c;
  switch (state_index) {
    case 0: c = 0x000000; break;   // OFF      灭
    case 1: c = 0xFFFFFF; break;   // ARMED    白
    case 2: c = 0x00FFFF; break;   // LISTENING 青
    case 3: c = 0xFFAA00; break;   // THINKING  琥珀
    case 4: c = 0xC0392B; break;   // SPEAKING  学院色（默认赤翎红，收到 result 后覆盖）
    case 5: c = 0xFF0000; break;   // ERROR     红
    default: c = 0x000000; break;
  }
  s_strip.setBrightness(77);        // 255 × 30%
  for (int i = 0; i < LED_COUNT; ++i) s_strip.setPixelColor(i, c);
  s_strip.show();
#else
  (void)state_index;
#endif
}

void hw_led_blink(int times, uint16_t on_ms) {
#ifdef HAT_ENABLE_LED
  for (int i = 0; i < times; ++i) {
    for (int j = 0; j < LED_COUNT; ++j) s_strip.setPixelColor(j, 0xFF0000);
    s_strip.show();
    delay(on_ms);
    for (int j = 0; j < LED_COUNT; ++j) s_strip.setPixelColor(j, 0x000000);
    s_strip.show();
    delay(on_ms);
  }
#else
  (void)times; (void)on_ms;
#endif
}

// ============================================================
// 按钮（GPIO0，低电平按下）
// ============================================================
#ifdef HAT_ENABLE_BTN

static bool     s_btnLastStable = true;      // true = 松开
static bool     s_btnLastRead   = true;
static uint32_t s_btnLastChange = 0;
static uint32_t s_btnPressAt    = 0;
static bool     s_btnPressedFlag = false;
static bool     s_btnLongFlag    = false;

static void btn_poll() {
  bool raw = digitalRead(PIN_BTN);           // 未按下 = HIGH
  if (raw != s_btnLastRead) { s_btnLastRead = raw; s_btnLastChange = millis(); return; }

  if (millis() - s_btnLastChange < 30) return;          // 30 ms 消抖
  if (raw == s_btnLastStable) return;

  bool old = s_btnLastStable;
  s_btnLastStable = raw;

  if (!old && raw) {                                    // 松开
    uint32_t held = millis() - s_btnPressAt;
    if (held < 2000) s_btnPressedFlag = true;           // 短按
    else             s_btnLongFlag    = true;           // 长按
  }
  if (old && !raw) s_btnPressAt = millis();             // 按下
}

#endif

bool hw_btn_ok() {
#ifdef HAT_ENABLE_BTN
  return true;
#else
  return false;
#endif
}

bool hw_btn_pressed() {
#ifdef HAT_ENABLE_BTN
  btn_poll();
  if (s_btnPressedFlag) { s_btnPressedFlag = false; return true; }
#endif
  return false;
}

bool hw_btn_long_press() {
#ifdef HAT_ENABLE_BTN
  btn_poll();
  if (s_btnLongFlag) { s_btnLongFlag = false; return true; }
#endif
  return false;
}

// ============================================================
// 初始化
// ============================================================
void hw_begin() {
  Serial.println("[HW] begin");

#ifdef HAT_ENABLE_SPK
  hw_speaker_open(AUDIO_HZ);
#endif

#ifdef HAT_ENABLE_MIC
  mic_configure();
  s_micStarted = true;
  s_micOn = true;
  s_micOk  = true;
  // 自检：读 100 ms，正常应该读到非全零（INMP441 有底噪）
  {
    int32_t probe[160];
    size_t n = 0;
    i2s_read(I2S_NUM_0, probe, sizeof(probe), &n, pdMS_TO_TICKS(300));
    bool nonzero = false;
    for (size_t i = 0; i < n / sizeof(int32_t); ++i) if (probe[i] != 0) { nonzero = true; break; }
    if (!nonzero) {
      Serial.println("[HW] mic reads all zero — check INMP441 接线/供电/L-R 引脚接地");
      s_micOk = false;
    }
  }
  Serial.printf("[HW] mic %s\n", s_micOk ? "ok" : "NO SIGNAL");
#endif

#ifdef HAT_ENABLE_LED
  s_strip.begin();
  s_strip.clear();
  s_strip.show();
  Serial.println("[HW] led ok");
#endif

#ifdef HAT_ENABLE_BTN
  pinMode(PIN_BTN, INPUT_PULLUP);
  s_btnLastStable = s_btnLastRead = digitalRead(PIN_BTN);
  Serial.println("[HW] btn ok");
#endif

  Serial.printf("[HW] %s\n", hw_status());
}
