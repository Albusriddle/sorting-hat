# fw/ 固件交付说明（下位机 · A）

> 2026-11-16 · 对应仓库 `fw/` 目录。把本目录下的 `sorting_hat_base/` 整个复制到 `fw/` 即可。
> 上游锁定见 `UPSTREAM.md`。本项目**不用 xiaozhi 上游**：固件从零写成 Arduino 工程。

---

## 1. 技术栈与范围

| 项 | 选择 |
|---|---|
| 框架 | **Arduino**（Arduino IDE 2.x + esp32 板子包），非 ESP-IDF |
| 板子 | ESP32-S3（最终型号见 `hw/pinmap.md` §6；C3 方案见 §6） |
| 语音输入 | 幻尔 WonderEcho ASR（I2C，唤醒词 = 录"分院帽"） |
| 语音输出 | XFS5152CE TTS（I2C，10 kHz，预录句 GBK） |
| 音频上传 | INMP441（I2S）→ Opus / PCM → WebSocket |
| 音频下放 | WebSocket → 0x02 帧 → MAX98357A（I2S） |
| 状态机 | 6 态：OFF / ARMED / LISTENING / THINKING / SPEAKING / ERROR |

---

## 2. 目录结构

```
fw/
├─ README.md                ← 本文件
├─ UPSTREAM.md              ← 上游锁定（本项目自建，无上游）
└─ sorting_hat_base/
   ├─ sorting_hat_base.ino  只放 setup() / loop() 与串口命令
   ├─ hat_config.h          引脚、音频参数、时间、VAD 阈值、编译开关
   ├─ hat_state.h/.cpp      6 态状态机 + 时间戳（t_arm/t0/t5a/t5b/t_stop）
   ├─ hat_hw.h/.cpp         硬件抽象层（每个硬件一个编译开关）
   ├─ hat_comm.h/.cpp       Wi-Fi + WebSocket + 协议 + Opus 收发
   ├─ hat_opus.h/.cpp       Opus 编解码（HAT_ENABLE_OPUS）
   ├─ hat_mic.h/.cpp        采音节奏 + 能量 VAD
   ├─ hat_offline.h/.cpp    断网兜底 + 离线按钮模式
   ├─ secrets.h.example     Wi-Fi/IP 模板（真实 secrets.h 不进 git）
   ├─ asr_wonderecho.h/.cpp 幻尔 ASR 驱动（组长提供，未改）
   ├─ tts_xfs5152.h/.cpp    XFS5152 驱动（组长提供，未改）
   └─ phrases_gbk.h         12 句预录台词（GBK，由 tools/gen_phrases.py 生成）
```

**为什么 `.ino` 这么小**：Arduino IDE 会在 `.ino` 前面自动插入函数原型，原型出现在所有类型定义之前；函数参数一旦用到自定义类型就会报 `not declared`。官方构建流程文档明确建议把这类代码放进 `.h/.cpp`。所以除 `setup/loop` 外的逻辑全部在 `.cpp` 里。

---

## 3. 编译开关（`hat_config.h`）

板子没到之前所有硬件开关都是注释掉的，代码照样能编译、能跑（走空实现）。
上板后逐个打开，出问题一眼能定位是哪个硬件：

```c
// #define HAT_ENABLE_MIC    // INMP441
// #define HAT_ENABLE_SPK    // MAX98357A
// #define HAT_ENABLE_LED    // WS2812
// #define HAT_ENABLE_BTN    // 按钮
// #define HAT_ENABLE_OPUS   // Opus（需要 arduino-audio-tools）
// #define HAT_ENABLE_VAD    // 能量 VAD（依赖 MIC）
```

---

## 4. 协议实现（以 `host/app/protocol.py` 为准）

### 发往服务端

| 消息 | 时机 |
|---|---|
| `{"type":"listen","state":"start"}` | 唤醒后进入 LISTENING |
| `0x01`/`0x04` + seq(u32 BE) + 音频 | LISTENING 期间，每 20 ms 一帧 320 样本 |
| `{"type":"vad","ev":"speech_start"}` | VAD 起振（仅 `HAT_ENABLE_VAD` 开启时） |
| `{"type":"vad","ev":"speech_end"}` | 判定说完 |
| `{"type":"abort","reason":"button"}` | 按钮打断 |
| `{"type":"bye","reason":"timeout","dev_ts":{...}}` | 10 s 无发言超时，带设备时间戳 |

### 收到

| 消息 | 处理 |
|---|---|
| `ready` | 记录 sid；按 `audio.out` 配解码采样率；开启 Opus（若编译时启用） |
| `tts{start}` | 打 t5a；开喇叭；关麦（半双工）；进 SPEAKING |
| `0x02` 帧 | **自动识别**：先试 Opus 解码，失败或结果不合理就当 PCM 直接播放；否则打 t5b |
| `tts{stop}` | 打 tStop；停喇叭；开麦；回 ARMED |
| `result` | 按 `house` 念本地预录句（**不念 `line`**，里面有【占位】） |
| `error` / `bye` | 打日志 |

### 时间戳（FR-6）

设备只产生单调时钟（`millis()`，上电为 0），UTC 由服务端补。4 个时间戳通过 `bye.dev_ts` 回传：
`t_arm` / `t0` / `t5a` / `t5b`（+ `t_stop`）。TTFV = t5a−t0，TTFC = t5b−t0，串口每个会话末尾打印。

---

## 5. 断网兜底

- WS 断开持续 4 s → 进入离线模式：灯黄，念 `PH_OFFLINE`
- 离线模式下：唤醒仍进 LISTENING 但不上行；**短按按钮轮换 4 个学院**，每按一次念一句
- 长按 2 s → 退出离线、触发重连
- 网络恢复 → 自动退出离线

> 为什么上行 20 ms 而下行 60 ms：方向不同、帧长独立，无需对齐。实测 downlink 一帧 1920 字节 = 960 样本 = 60 ms @ 16 kHz。

---

## 6. 已知限制

| 项 | 状态 | 说明 |
|---|---|---|
| Opus | 代码已写，**未在真机验证** | 依赖 `arduino-audio-tools`；S3 上应可用，C3 未验证 |
| C3 板子 | 未适配 | C3 只有 1 个 I2S 控制器，麦克风和喇叭不能同时工作；Opus 编码在单核 160 MHz 上可能放不下 |
| GPIO16 冲突 | **未解决** | ASR_SDA 与 SPK_LRC 都是 GPIO16（见 `hw/pinmap.md` §6） |
| 12 句预录台词 | 用组长驱动里的哈利波特原名 | 需与 C 确认是否改成赤翎/玄渊/星枢/穗垣 |

---

## 7. 复现命令

```bash
# 编译检查（宿主 g++，不需要板子）
python 检查/check_build.py 固件/sorting_hat_base
# → 硬件全关 / 硬件全开 两套配置都会编一遍
```
