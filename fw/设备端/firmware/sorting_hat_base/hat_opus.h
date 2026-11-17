// ============================================================
// hat_opus.h —— Opus 编解码（可选，HAT_ENABLE_OPUS 开关）
//
// 单独成文件是因为它最容易出问题（库、栈、CPU），出事能单独关。
// 上行：16 kHz/单声道/20 ms → 0x01 帧。
// 下行：0x02 帧里可能是 Opus 也可能是裸 PCM，这里先试解码再回退。
// ============================================================
#pragma once

#include <Arduino.h>

// 初始化编解码器；返回 false 表示库里没有 Opus
bool opus_init();

// PCM（320 样本）→ Opus 包；返回包长，0 表示失败
size_t opus_encode(const int16_t* pcm, size_t samples, uint8_t* out, size_t outCap);

// 下行一帧 0x02 的载荷（不含 5 字节头）。
// true = 是 Opus 且解码成功；false = 不是，调用者当 PCM 直接播。
bool opus_decode_or_passthrough(const uint8_t* payload, size_t len,
                                int16_t* pcmOut, size_t pcmCap, size_t* pcmLen);

// 设置解码采样率（跟 ready.audio.out 走）
void opus_set_rate(uint32_t hz);
