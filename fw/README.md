# 固件（ESP32-WROOM-32D · Arduino）

> 实物固件在 `设备端/firmware/sorting_hat_base/`。**本项目无上游**（不用 xiaozhi），见 `UPSTREAM.md`。
> 第三方库：ArduinoJson、WebSocketsClient（arduinoWebSockets）。

## 1. 硬件与能力

| 模块 | 型号 | 接口 | 能力 |
|---|---|---|---|
| 主控 | ESP32-WROOM-32D | — | Wi-Fi / WebSocket / I2C |
| ASR | 幻尔 LD3320A | Wire SDA16/SCL17 100 kHz | 关键词 → 1 字节编号；**不转文字、不出音频** |
| TTS | 幻尔 XFS5152/CSK4002 | Wire1 SDA19/SCL18 10 kHz | 合成任意 GBK/UTF-8 文本 |
| 麦克风/功放 | 无 | — | 上行只能是全零帧；0x02 下行不外放 |

## 2. 文件

```
sorting_hat_base.ino   setup/loop + 串口命令
hat_config.h           引脚、音频参数、时间、VAD、编译开关、学院命名、唤醒编号
hat_state.*            六态状态机 + 时间戳
hat_hw.*               硬件抽象（各外设编译开关）
hat_comm.*             Wi-Fi + WebSocket + 协议
hat_mic.*              采音节奏 + 能量 VAD（依赖 MIC）
hat_offline.*          断网兜底 + 离线按钮轮换
hat_intent.*           词条编号 → 中文台词（1–4 号）
asr_wonderecho.*       LD3320A 驱动（组长提供）
tts_xfs5152.*          XFS5152 驱动（组长提供）
phrases_gbk.h          由 tools/gen_phrases.py 生成
secrets.h.example      Wi-Fi / 上位机 IP / TOKEN 模板
```

## 3. 编译

Arduino IDE 2.x + esp32 板子包，板型选 **ESP32 Dev Module**，波特率 115200。
宿主侧静态检查（无需板子）：`python 设备端/tools/check_build.py 设备端/firmware/sorting_hat_base`。
编译开关都在 `hat_config.h`：`HAT_ENABLE_MIC/SPK/LED/BTN/OPUS/VAD`（实物全关）、`HAT_HOUSE_ORIGINAL`、`ASR_WAKE_WORD_ID`。

## 4. 协议（以 `host/app/protocol.py` 为准）

- 上行：`listen start`、`vad start/end`、`0x04`（PCM 20 ms/320 样本）、`0x01`（Opus，可选）、`text`（词条文本）、`abort`、`bye{dev_ts}`。
- 下行：`ready{sid,audio,budget_ms}`、`tts{start/stop,text}`、`0x02`（PCM 60 ms/1920 B）、`result{house,reasons,line,scores,announce}`、`error`、`bye`。
- 时间戳：`t_arm/t0/t5a/t5b/t_stop`，通过 `bye.dev_ts` 回传。

## 5. 串口命令

`w` 唤醒、`e` 说完、`b` 打断、`x` 故障、`o` 离线、`k` 能量、`a/1-4` 试听、`p` 词条表、`A-D` 模拟识别 1–4 号。

## 6. 已知限制

- Opus 代码已写、真机未验证；VAD 依赖真麦。
- 词条表必须与模块烧录一致：1–4 号内容，**5 号唤醒**（`ASR_WAKE_WORD_ID`）。
- 无麦时上行是全零帧，上位机 RMS 闸会拦；这属预期行为。
