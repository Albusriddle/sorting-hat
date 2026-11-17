// ============================================================
// hat_comm.h —— 和上位机的通信
// ============================================================
#pragma once

#include <Arduino.h>
#include "hat_state.h"

void comm_begin();                 // setup 里调一次（Wi-Fi + WebSocket + Opus）
void comm_loop();                  // loop 里每轮调一次
bool comm_up();                    // 当前是否连着
bool comm_opus_tx();               // 上行是否在用 Opus（否则是 PCM）
uint32_t comm_last_rx_at();        // 最后一次收到消息的时间

// 从通信模块切状态。必须用它，不要直接 hat_go()——
// 绕开会跳过 .ino 的 go() 副作用（开麦/关麦），麦克风就恢复不了。
void comm_set_state_handler(void (*fn)(HatState, const char*));
void comm_go(HatState next, const char* event);

void comm_send_listen_start();
void comm_send_vad_start();
void comm_send_vad_end();
void comm_send_abort(const char* reason);
void comm_send_bye(const char* reason);

// 把"观众说了什么"发给上位机，有它就不走云端 ASR。
// 字段名 text，对应上位机的 last_text。
void comm_send_text(const char* text);

// 发一帧上行音频；调用者负责凑满 AUDIO_SAMPLES 个样本。
void comm_send_audio(const int16_t* samples, size_t count);
