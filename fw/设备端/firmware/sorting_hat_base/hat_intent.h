// ============================================================
// hat_intent.h —— 语音识别"意图"层
//
// 两种情况下都会产生"观众说了什么"：
//
//   ① 离线关键词模块（LD3320A）：只能给出词条编号 1..N。
//      这里把编号映射成一句中文，发给云端判学院。
//
//   ② 在线 ASR（以后接）：它自己就产出文字，
//      直接调 hat_intent_from_text() 即可。
//
// 上层（.ino / comm）不需要关心消息从哪儿来，只认文字。
// ============================================================
#pragma once

#include <Arduino.h>

// LD3320A 词条编号 → 中文文本。编号为 0 或超出表范围返回 nullptr。
// ★ 这张表要和模块里烧的词条一一对应，改模块就得改这里。
const char* hat_intent_text_for_id(uint8_t id);

// 词条总数（给串口命令 p 打印用）
uint8_t hat_intent_count();

// 打印整张表
void hat_intent_dump();

// 在线 ASR 接进来以后：拿到文字直接交给这里，
// 内部会走 comm_send_text() 发给上位机。
void hat_intent_from_text(const char* text);

// 最近一次识别的文字（调试用）
const char* hat_intent_last();

// 收到词条编号时调用：查表 → 转成文字 → 发给上位机
void hat_intent_on_word_id(uint8_t id);
