// ============================================================
// hat_hw.h —— 硬件抽象层（HAL）
//
// 原则：上层（状态机、网络）永远不出现引脚号，只调这些函数。
// 每个函数都有"编译开关"版本：开关没打开时是安全的空实现。
// ============================================================
#pragma once

#include <Arduino.h>

void   hw_begin();                                   // setup 里调一次
const char* hw_status();                             // 一行状态串，给 [BOOT] 用

// ---- 麦克风 ----
bool   hw_mic_ok();
size_t hw_mic_read(int16_t* buf, size_t samples);    // 读满 samples 个样本返回 samples，否则返回实际数
void   hw_mic_enable(bool on);                       // 半双工：说话时关麦

// ---- 喇叭 ----
bool   hw_speaker_ok();
void   hw_speaker_open(uint32_t hz);                 // 打开 I2S 输出（采样率跟 ready 走）
void   hw_speaker_play(const uint8_t* pcm, size_t bytes);
void   hw_speaker_stop();
size_t hw_speaker_backlog();                         // 还剩多少字节没播完

// ---- 灯 ----
void   hw_led_set(int state_index);
void   hw_led_blink(int times, uint16_t on_ms);

// ---- 按钮 ----
bool   hw_btn_ok();
bool   hw_btn_pressed();                             // 按下沿（消抖后，按一次返回一次 true）
bool   hw_btn_long_press();                          // 长按 2 s 抬起，返回一次 true
