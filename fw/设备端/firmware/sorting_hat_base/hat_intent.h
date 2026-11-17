// ============================================================
// hat_intent.h —— 语音识别"意图"层
//
// 语识来源只有两种：LD3320A 给编号（查表转文字），
// 或者以后的在线 ASR 直接给文字。上层只认文字。
// ============================================================
#pragma once

#include <Arduino.h>

// 词条编号 → 中文文本。编号为 0 或超出表范围返回 nullptr。
// ★ 这张表要和模块里烧的词条一一对应，改模块就得改这里。
const char* hat_intent_text_for_id(uint8_t id);

// 词条总数（串口命令 p 打印用）
uint8_t hat_intent_count();

// 打印整张表
void hat_intent_dump();

// 在线 ASR 用：拿到文字直接发出去
void hat_intent_from_text(const char* text);

// 最近一次识别的文字（调试用）
const char* hat_intent_last();

// 收到词条编号：查表 → 转文字 → 发给上位机
void hat_intent_on_word_id(uint8_t id);
