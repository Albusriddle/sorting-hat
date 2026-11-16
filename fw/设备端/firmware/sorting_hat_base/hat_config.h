// ============================================================
// hat_config.h —— 所有"可调的东西"集中在这一个文件
//
// 引脚以组长驱动代码为准（不是 pinmap.md）：
//   ASR  Wire   SDA 16 / SCL 17   100 kHz
//   TTS  Wire1  SDA 19 / SCL 18    10 kHz（芯片要求 ≤15 kHz）
// 麦克风/喇叭/灯/按钮来自仓库 hw/pinmap.md（FROZEN G1 PENDING）
// ============================================================
#pragma once

#include <Arduino.h>

// ============================================================
// 编译开关：板子没到之前先关掉，代码照样能编译
// 板上验证通过后再逐个打开
// ============================================================
// #define HAT_ENABLE_MIC      // INMP441 麦克风（I2S 输入）
// #define HAT_ENABLE_SPK      // MAX98357A 喇叭（I2S 输出）
// #define HAT_ENABLE_LED      // WS2812 灯环
// #define HAT_ENABLE_BTN      // 按钮
// #define HAT_ENABLE_OPUS     // Opus 编解码（需要 arduino-audio-tools）
// #define HAT_ENABLE_VAD      // 麦克风能量 VAD（依赖 HAT_ENABLE_MIC）

// ---------------- 学院命名（S-05）----------------
// 0 = 原创名（赤翎/玄渊/星枢/穗垣，IP 安全）
// 1 = 哈利波特原名（格兰芬多/...，辨识度高但有版权风险）
#define HAT_HOUSE_ORIGINAL   0

// 唤醒词占用 5 号词条；1–4 号留给四句内容（S-08）
#define ASR_WAKE_WORD_ID     5

// ---------------- I2C 模块（组长驱动，已可用）----------------
#define PIN_ASR_SDA      16
#define PIN_ASR_SCL      17
#define PIN_TTS_SDA      19
#define PIN_TTS_SCL      18

// ---------------- I2S / 外设引脚（来自 hw/pinmap.md）----------------
#define PIN_MIC_BCLK     4      // INMP441 SCK
#define PIN_MIC_WS       5      // INMP441 WS
#define PIN_MIC_SD       6      // INMP441 SD
#define PIN_SPK_BCLK     15     // MAX98357A BCLK
#define PIN_SPK_LRC      21     // MAX98357A LRC（原 16 与 ASR SDA 冲突，改 21）
#define PIN_SPK_DIN      7      // MAX98357A DIN
#define PIN_LED          48     // WS2812 ×8
#define PIN_BTN          0      // 按钮（短按=打断，长按 2 s=静音）

// 已废弃：GPIO10 = 原"戴上帽子"传感器，动作取消，不用了
// 本项目不接：GPIO1(电池 ADC) / GPIO2(马达) / GPIO3(电源使能)

// ---------------- 音频参数（和上位机对齐，别改）----------------
#define AUDIO_HZ          16000   // 上行 16 kHz
#define AUDIO_SAMPLES     320     // 上行 20 ms = 320 样本
#define AUDIO_FRAME_BYTES (AUDIO_SAMPLES * 2)
#define OPUS_FRAME_MS     20      // Opus 帧长（必须与样本数对应）
#define OPUS_COMPLEXITY   5       // 0–10，S3 上 5 大约占 30–50% CPU；C3 要降到 1

// ---------------- 时间参数 ----------------
#define LISTEN_TIMEOUT_MS   10000UL  // 进 LISTENING 后多久没说完算超时
#define OFFLINE_MS          4000UL   // WS 断线多久提示"断网"
#define RECONNECT_MS        1500UL   // 重连间隔
#define HEARTBEAT_MS        15000UL  // ping 间隔

// ---------------- VAD 参数 ----------------
#define VAD_TAIL_MS         300       // 连续静音多久算"说完了"（与 ready.vad.tail_ms 对齐）
#define VAD_MIN_SPEECH_MS   200       // 至少说了多久才算一次有效发言（与 ready.vad.min_speech_ms 对齐）
#define VAD_ENERGY_THRESH   600       // 能量阈值（16 bit PCM，绝对值平均）。安静时约 20–200，说话 1000+
#define VAD_DEBOUNCE_MS     40        // 防抖：连续多久超过阈值才认定"开始说话"
