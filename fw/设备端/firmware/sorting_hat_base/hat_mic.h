// ============================================================
// hat_mic.h —— 麦克风采音 + 能量 VAD
//
// 没开 HAT_ENABLE_VAD 时只发静音，方便无板开发；开了以后每帧求
// |样本| 平均，超过阈值算说话，连续 VAD_TAIL_MS 低于阈值算说完。
// 自己写 10 行就够，不引 AFE（S3 上还吃内存）。
// ============================================================
#pragma once

#include <Arduino.h>

// 每轮 loop 调一次；vadStarted / vadEnded 表示这轮检测到开口 / 说完
void mic_loop(bool* vadStarted, bool* vadEnded);

// 把一帧麦克风数据交给音频通道发出去
void mic_pump_frame();

// 是否在 LISTENING（由 .ino 在状态迁移时设）
void mic_set_listening(bool on);

// 重置 VAD 状态（进 LISTENING 时调）
void mic_reset_vad();

// 最近一帧能量，0 表示还没数据
int32_t mic_last_energy();
