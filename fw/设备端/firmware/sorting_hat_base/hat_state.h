// ============================================================
// hat_state.h —— 6 态定义 + 状态迁移声明
//
// 不放 .ino 里：Arduino IDE 自动插函数原型，会插到自定义类型之前，
// 参数用到 HatState 时报 "not declared"。
// ============================================================
#pragma once

#include <Arduino.h>

// enum class 名字只在 HatState:: 里，不会和 Arduino 的宏撞；
// OFF / ERROR 加 _ST 后缀防撞
enum class HatState : uint8_t {
  OFF_ST = 0,
  ARMED,
  LISTENING,
  THINKING,
  SPEAKING,
  ERROR_ST
};

extern HatState g_state;
extern uint32_t g_stateAt;          // 进入当前状态的时间（millis）

const char* hat_state_name(HatState s);
const char* hat_state_led(HatState s);
HatState    hat_state_get();
bool        hat_state_in_listen_or_think();

// 状态迁移：打印日志、改灯、做进出动作
void hat_go(HatState next, const char* event);

// ---------------- 时间戳（TTFC = t5b - t0）----------------
// 全是单调时钟 millis()，上电为 0；UTC 由服务端补，设备不做 NTP
struct HatTs {
  uint32_t tArm;    // 进 ARMED（唤醒词 / 按钮）
  uint32_t t0;      // 判定"说完了"
  uint32_t t5a;     // 收到 tts{start}
  uint32_t t5b;     // 第一帧下行音频开始播放
  uint32_t tStop;   // 收到 tts{stop}
};
extern HatTs g_ts;
void hat_ts_stamp(uint32_t HatTs::*field);   // 打一个时间戳
void hat_ts_reset();                          // 进 LISTENING 时清空
void hat_ts_dump();                           // 串口打印 ttfc 等
