// ============================================================
// hat_mic.h —— 麦克风采音 + VAD（能量法）
//
// 设计原则：
//   * 不开 HAT_ENABLE_VAD 时，只有"假音频"模式（发静音），用于无板子开发；
//   * 开了之后，音频帧由 hw_mic_read() 提供，能量判断用最朴素的方法：
//     每一帧求 |样本| 平均，超过阈值算"有人在说话"，连续 VAD_TAIL_MS 低于阈值
//     算"说完了"。
//
// 为什么不用库：VAD 在演示现场最多只需要"判个大概"，自己算 10 行代码，
// 出问题能改，比引入 AFE 好维护很多（S3 上 AFE 还要额外内存）。
// ============================================================
#pragma once

#include <Arduino.h>

// 每轮 loop 调一次。返回 true 表示"这一轮有事情要通知状态机"。
// vadStarted / vadEnded 分别表示这一轮检测到"开始说话"/"说完了"。
void mic_loop(bool* vadStarted, bool* vadEnded);

// 把一帧麦克风数据交给音频通道去发（VAD 前后都用它）
void mic_pump_frame();

// 当前是否在 LISTENING（由 .ino 在状态迁移时设置）
void mic_set_listening(bool on);

// 重置 VAD 状态（每次进入 LISTENING 时调）
void mic_reset_vad();

// 最近一帧的能量值（调试用），0 表示还没数据
int32_t mic_last_energy();
