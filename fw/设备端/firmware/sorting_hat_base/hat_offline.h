// ============================================================
// hat_offline.h —— 断网兜底 + 离线按钮模式
//
// 两种情况都会走这里：
//   ① WS 断了超过 OFFLINE_MS（hat_comm 判断）
//   ② 用户主动进入离线模式（长按按钮）
//
// 离线模式下：
//   * 灯变黄
//   * 听到唤醒词仍然进 LISTENING，但不上行（本地说"网络断了"）
//   * 短按按钮循环 4 个学院，每按一次念一个
//   * 网络恢复后自动退出
// ============================================================
#pragma once

#include <Arduino.h>

void offline_begin();
void offline_loop();

// 网络断开/恢复时由 hat_comm 或 .ino 调用
void offline_set_network(bool up);
bool offline_active();          // 当前是否处于离线模式

// 离线模式下按按钮：切到下一个学院并念出来
void offline_next_house();

// 是否处于离线"念完就回"的状态（念完要回到 ARMED）
void offline_clear_narrating();
