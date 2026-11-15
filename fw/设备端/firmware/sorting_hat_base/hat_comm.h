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

// 从通信模块里切状态。必须用这个而不是直接 hat_go()：
// .ino 的 go() 会在进入新状态时做副作用（开麦/关麦等），
// 绕开它的话麦克风恢复不了。
void comm_set_state_handler(void (*fn)(HatState, const char*));
void comm_go(HatState next, const char* event);

void comm_send_listen_start();
void comm_send_vad_start();
void comm_send_vad_end();
void comm_send_abort(const char* reason);
void comm_send_bye(const char* reason);

// 把"观众说了什么"的文字发给上位机。
// 在线 ASR（或 LD3320A 词条映射）拿到文字后走这条路，云端就不用再自己做 ASR。
// 字段名用 text，对应 device_app.py 里的 last_text。
void comm_send_text(const char* text);

// 发一帧上行音频。4096 字节以内直接发；调用者负责凑满 AUDIO_SAMPLES(=320) 个样本。
void comm_send_audio(const int16_t* samples, size_t count);
