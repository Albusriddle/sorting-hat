// ============================================================
// hat_opus.h —— Opus 编解码（可选，用 HAT_ENABLE_OPUS 开关）
//
// 为什么单独一个文件：它是整条链路里最容易出问题的一块（库、栈、CPU），
// 出错时要能单独关掉而不影响其它部分。
//
// 上行：16 kHz / 单声道 / 20 ms（320 样本）→ Opus 包 → 0x01 帧
// 下行：0x02 帧里可能是 Opus，也可能是裸 PCM（上位机现在发 PCM），
//       这里做"自动识别"：先试 Opus 解码，失败或结果不合理就当 PCM。
// ============================================================
#pragma once

#include <Arduino.h>

// 初始化编码器/解码器。返回 false 表示库里没有 Opus（例如板子不支持）。
bool opus_init();

// 上行：PCM（320 样本）→ Opus 包。返回包长，0 表示失败。
size_t opus_encode(const int16_t* pcm, size_t samples, uint8_t* out, size_t outCap);

// 下行：一帧 0x02 的载荷（不含 5 字节头）。
// 返回 true = 是 Opus 且解码成功，pcmOut/pcmLen 指向解出的 PCM；
// 返回 false = 不是 Opus，调用者应当把原载荷当 PCM 直接播放。
bool opus_decode_or_passthrough(const uint8_t* payload, size_t len,
                                int16_t* pcmOut, size_t pcmCap, size_t* pcmLen);

// 设置解码器采样率（跟 ready.audio.out 走）。返回是否切换成功。
void opus_set_rate(uint32_t hz);
