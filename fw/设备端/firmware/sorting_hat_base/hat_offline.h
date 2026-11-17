// ============================================================
// hat_offline.h —— 断网兜底 + 离线按钮模式
//
// 触发：WS 断线超过 OFFLINE_MS，或长按按钮主动离线。
// 离线时灯变黄，唤醒仍进 LISTENING 但不上行（本地说"网络断了"），
// 短按按钮循环四院，网络恢复自动退出。
// ============================================================
#pragma once

#include <Arduino.h>

void offline_begin();
void offline_loop();

// 网络断开/恢复时调
void offline_set_network(bool up);
bool offline_active();          // 当前是否在离线模式

// 离线模式按按钮：切下一个学院并念出来
void offline_next_house();

// 清掉"念完就回"标记（念完回 ARMED）
void offline_clear_narrating();
