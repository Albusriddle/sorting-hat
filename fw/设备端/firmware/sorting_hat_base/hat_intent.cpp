// ============================================================
// hat_intent.cpp —— 词条编号 → 中文文本
//
// ★ 这是"没有在线 ASR 时"的替代方案：
//   LD3320A 烧进若干句有性格倾向的话；观众说哪句，
//   模块回哪个编号，这里查表变成文字发给云端。
//   云端照常按文字判学院，判出来的结果和观众说的话真正相关。
//
// 要让这张表生效，必须同步改模块里的词条（见 幻尔模块-词条怎么改.md）。
// 表里写的是"文本"，模块里烧的是"拼音"，两者顺序必须一致。
// ============================================================
#include "hat_intent.h"
#include "hat_comm.h"

// 建议的词条（编号 1 起）。四条覆盖四个性格方向，
// 观众随便挑一条说，判出来的学院就会跟这句的意思对应。
static const char* const kPhrases[] = {
    // 1 —— 偏向勇气
    "我最怕输，但我更怕自己在关键时候退缩。",
    // 2 —— 偏向野心
    "我想要的东西很大，而且我一定会把它拿到手。",
    // 3 —— 偏向智慧
    "我喜欢把一件事拆开想清楚，再决定要不要做。",
    // 4 —— 偏向忠诚
    "我在乎身边的人，他们需要我的时候我不会缺席。",
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
