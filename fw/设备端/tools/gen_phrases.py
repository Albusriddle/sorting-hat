#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate phrases_gbk.h (GBK byte arrays) for the XFS5152 TTS module.

Two house-name sets are emitted:
  PH_HOUSE_*      -> IP-downgraded names (赤翎/玄渊/星枢/穗垣)   [default]
  PH_HOUSE_*_ORIG -> original names (格兰芬多/...)              [switch only]

Compile switch in hat_config.h:
  #define HAT_HOUSE_ORIGINAL 0   // 0 = downgraded, 1 = original
"""
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parents[1] / "firmware" / "sorting_hat_base" / "phrases_gbk.h"

BASE = [
    ("PH_BOOT", "分院帽醒了。靠近一点，让我看看你。"),
    ("PH_ASK", "说吧，孩子。"),
    ("PH_WAIT", "我在听。"),
    ("PH_RETRY", "没听清，再说一次。"),
    ("PH_THINK", "嗯，有意思。"),
    ("PH_TIMEOUT", "想好了再来找我。"),
    ("PH_BYE", "去吧，孩子。"),
    ("PH_OFFLINE", "网络断了，我们本地来。"),
]

HOUSE_NEW = [
    ("PH_HOUSE_COURAGE", "赤翎！"),
    ("PH_HOUSE_AMBITION", "玄渊！"),
    ("PH_HOUSE_WISDOM", "星枢！"),
    ("PH_HOUSE_LOYALTY", "穗垣！"),
]

HOUSE_ORIG = [
    ("PH_HOUSE_COURAGE_ORIG", "格兰芬多！"),
    ("PH_HOUSE_AMBITION_ORIG", "斯莱特林！"),
    ("PH_HOUSE_WISDOM_ORIG", "拉文克劳！"),
    ("PH_HOUSE_LOYALTY_ORIG", "赫奇帕奇！"),
]


def fmt(name: str, text: str) -> str:
    data = text.encode("gbk")
    body = ", ".join(f"0x{b:02X}" for b in data)
    return (f'// "{text}"  ({len(data)} bytes GBK)\n'
            f"static const uint8_t {name}[] = {{\n    {body}\n}};\n")


def main() -> int:
    parts = ["// ============================================================",
             "// phrases_gbk.h  —— 由 tools/gen_phrases.py 自动生成，请勿手改",
             "// 所有字符串均已转成 GBK 字节，直接喂给 XFS5152CE，运行期不做转码",
             "// ============================================================",
             "#pragma once", "#include <stdint.h>", "",
             f"#define PHRASE_COUNT {len(BASE) + len(HOUSE_NEW)}", ""]
    for name, text in BASE + HOUSE_NEW + HOUSE_ORIG:
        parts.append(fmt(name, text))
    parts.append("typedef struct { const char* name; const uint8_t* data; uint16_t len; } Phrase;")
    parts.append("")
    parts.append("// 默认使用原创学院名（IP 降级）；原名只保留给 HAT_HOUSE_ORIGINAL=1")
    parts.append("static const Phrase PHRASE_TABLE[PHRASE_COUNT] = {")
    for name, text in BASE:
        parts.append(f'  {{ "{text}", {name}, (uint16_t)sizeof({name}) }},')
    for name, text in HOUSE_NEW:
        parts.append(f'  {{ "{text}", {name}, (uint16_t)sizeof({name}) }},')
    parts.append("};")
    parts.append("")
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
