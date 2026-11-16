# 硬件与引脚表（实物版，2026-11-16）

> **说明**：这是**现场实物**的引脚表，不是 11-15 设计稿（ESP32-S3 + INMP441 + MAX98357A）。
> 设计稿与实际硬件是两套假设；以本文件为准。签名：`FROZEN G1b 20261116 <SHA>`（A 签字后补）。

## 1. 实物清单

| 模块 | 型号 | 接口 | 能做什么 | 不能做什么 |
|---|---|---|---|---|
| 主控 | **ESP32-WROOM-32D**（普通 ESP32，38 pin） | — | Wi-Fi / WebSocket / I2C | 无 PSRAM；GPIO48 不存在 |
| 语音识别 | 幻尔 **LD3320A** | I2C（Wire）SDA16 / SCL17，100 kHz | 离线关键词识别，回 1 字节词条编号 | 不输出音频流、不转文字 |
| 语音合成 | 幻尔 **CSK4002 / XFS5152** | I2C（Wire1）SDA19 / SCL18，10 kHz | 合成任意 GBK/UNICODE 文本（≤288 B/帧） | — |
| 麦克风 | **无**（INMP441 未采购） | — | — | 无法采音；上行只能是全零帧 |
| 功放/喇叭 | **无** MAX98357A；用 CSK4002 板载喇叭 | — | 出声 | 无法播放 host 下发的 0x02 PCM |

## 2. 引脚

| 信号 | GPIO | 说明 |
|---|---|---|
| ASR_SDA | 16 | Wire，100 kHz |
| ASR_SCL | 17 | Wire，100 kHz |
| TTS_SDA | 19 | Wire1，10 kHz（芯片要求 ≤15 kHz） |
| TTS_SCL | 18 | Wire1，10 kHz |
| BTN | 0 | 板载 BOOT 键；短按=开始/打断，长按 2 s=重连/退出离线 |
| LED | 2 | 板载蓝灯（仅状态提示，不是 WS2812） |

**冲突记录**：设计稿里 `PIN_SPK_LRC = 16` 与 `ASR_SDA = 16` 冲突；实物没有 MAX98357A，`HAT_ENABLE_SPK` 保持关闭，冲突不触发。若以后补功放，LRC 必须改脚。

## 3. 音频参数（与上位机对齐）

| 方向 | 格式 | 说明 |
|---|---|---|
| 上行 0x04 | PCM16 / 16 kHz / 20 ms（320 样本 / 640 B） | 无麦时是**全零帧**；host 用 RMS 闸拦截 |
| 上行 0x01 | Opus / 16 kHz / 20 ms | 需 `HAT_ENABLE_OPUS`，未在真机验证 |
| 下行 0x02 | PCM16 / 16 kHz / 60 ms（1920 B） | 当前 I2S 关闭，host 的桥接句改由 I2C TTS 念 |

## 4. 编译开关（hat_config.h）

```
HAT_ENABLE_MIC / SPK / LED / BTN / OPUS / VAD   全关（实物没有对应外设）
HAT_HOUSE_ORIGINAL  0   # 0=赤翎/玄渊/星枢/穗垣；1=哈利波特原名
ASR_WAKE_WORD_ID    5   # 1–4 号留给四句内容
```
