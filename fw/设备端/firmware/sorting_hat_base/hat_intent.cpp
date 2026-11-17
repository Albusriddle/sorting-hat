// ============================================================
// hat_intent.cpp —— 词条编号 → 中文文本
//
// LD3320A 只回编号。查表变成文字发给上位机，判院靠这段文字。
// ★ 这张表必须和模块里烧的词条（.ino 的 'P'）一一对应。
// ============================================================
#include "hat_intent.h"
#include "hat_comm.h"

// 四条覆盖四个性格方向，观众挑一条说，判出来的学院跟这句话对应。
// 短句要同时满足：好发音、上位机 mock 关键词能命中、四句语音差别够大。
// "怕输"→courage，"第一"→ambition，"为什么"→wisdom，"照顾家人"→loyalty
static const char* const kPhrases[] = {
    "我最怕输。",
    "我要拿第一。",
    "我想知道为什么。",
    "我想照顾家人。",
};

static const uint8_t kPhraseCount = sizeof(kPhrases) / sizeof(kPhrases[0]);
static char s_last[128];

const char* hat_intent_text_for_id(uint8_t id) {
  if (id == 0 || id > kPhraseCount) return nullptr;
  return kPhrases[id - 1];
}

uint8_t hat_intent_count() { return kPhraseCount; }

void hat_intent_dump() {
  Serial.printf("[INTENT] 词条表 %u 条（编号必须和模块里烧的一致）\n", kPhraseCount);
  for (uint8_t i = 0; i < kPhraseCount; ++i) {
    Serial.printf("  %u. %s\n", i + 1, kPhrases[i]);
  }
}

void hat_intent_from_text(const char* text) {
  if (!text || !text[0]) return;
  strncpy(s_last, text, sizeof(s_last) - 1);
  s_last[sizeof(s_last) - 1] = '\0';
  comm_send_text(text);
}

const char* hat_intent_last() { return s_last; }

// ---- 给 .ino 用：收到词条编号就转成文字发出去 ----
// 放在 .cpp 里避免 .ino 自动原型问题
void hat_intent_on_word_id(uint8_t id) {
  if (id == 0) return;
  const char* t = hat_intent_text_for_id(id);
  if (!t) {
    Serial.printf("[INTENT] 编号 %u 不在表里（表只有 %u 条）\n", id, kPhraseCount);
    return;
  }
  Serial.printf("[INTENT] 识别到 %u 号 → \"%s\"\n", id, t);
  hat_intent_from_text(t);
}
