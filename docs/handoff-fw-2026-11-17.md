# 给下位机 / 硬件的交接清单（2026-11-17）

> 基线：仓库 `main = 8052276`；上位机 **52 passed**；板上当前仍是 `5d845bb`。
> 目的：把"仓库改了什么、你要烧什么、烧完怎么验、硬件要注意什么"一次说清。
> 本清单取代 `docs/handoff-fw.md` 的旧版本（旧文保留作历史）。

---

## 0. 一句话

**板上固件比仓库旧三处**（`t0` 打点、`vad_start`、30 s 超时），另有时间戳打印无符号；仓库这三处已修，需要你**重烧 main**。硬件不用改线，但要按"慢说、唤醒后停顿、短句"重排演示词条与主持脚本。

---

## 1. 仓库相对 `5d845bb` 到底改了什么（固件 3 个文件）

| 文件 | 改动 | 为什么 |
|---|---|---|
| `hat_config.h` | `LISTEN_TIMEOUT_MS 25000 → 30000` | 晚于 host 的 20 s 收尾，避免双 bye 竞态 |
| `sorting_hat_base.ino` | `poll_asr()` 在 `hat_intent_on_word_id()` 后补 `comm_send_vad_start()`；`hat_ts_stamp(&HatTs::t0)` 移到 `comm_send_vad_end()` **之前**（3 处：ASR / 串口 `e` / VAD） | `vad_start` = "听到了"，host 停静音计时；`t0` 提前避免 `t5b < t0` |
| `hat_state.cpp` | `TTFV/TTFC` 改有符号打印；`t5b<t0` 打 `n/a` | 不再出现 `4294966xxx` |

**没有变的**：词条 1–4、5 号唤醒、`tts{stop}` 不硬停、`PIN_SPK_LRC=21`、学院名双套、串口命令。

---

## 2. 烧板前检查（硬件）

| # | 项 | 要求 | 确认 |
|---|---|---|---|
| H1 | 板型 | **ESP32-WROOM-32D**，Arduino IDE 选 `ESP32 Dev Module`；不要用 S3 | ☐ |
| H2 | 供电 | 两块模块都接 **5V**，共地；S3 5V 带不动已停用 | ☐ |
| H3 | I2C | LD3320A：SDA16/SCL17，**0x79**；CSK4002：SDA19/SCL18，**0x40**；各 100 kHz / 10 kHz | ☐ |
| H4 | 烧录 | 上传速率 **115200**（921600 会 `chip stopped responding`） | ☐ |
| H5 | 麦克风 | 模块板载麦；说话距离 **10–20 cm**，慢说，环境噪声低 | ☐ |
| H6 | 功放/灯/按钮 | 都没有，编译开关保持关闭；`[LED]` 只是打印 | ☐ |
| H7 | 安全 | `secrets.h` 不提交、不外发；**Wi-Fi 密码 / DEVICE_TOKEN / HOST_IP 全部轮换**（zip 已外流） | ☐ |

---

## 3. 烧板后必须回传的 5 条证据

```
[BOOT] asr=ok tts=ok mic=off spk=off led=off btn=off opus=off
[NET] sid=... in=pcm16|opus/16k/20ms out=pcm16/16k/60ms (spk=16000)
[INTENT] 识别到 1 号 → "我最怕输，但我更怕自己在关键时候退缩。"
[WS-TX] vad speech_start          ← 新增，旧固件没有
[TS] TTFC=137 ms                   ← 必须是正数；不能是 4294966xxx
```

再加一条主机侧：`/v1/sessions?n=1` 的 `ttfc_ms` 非空、`clock_skew` 为空。

> **版本追溯问题**：当前固件没有版本横幅，日志无法证明烧的是哪一版。建议在 `setup()` 打印一行
> `[BOOT] fw=<git短hash> listen_timeout=30000`。这是新增一行日志，不是新功能；你确认后我加进仓库。

---

## 4. 验收步骤（照做即可）

### 4.1 写词条（只有换词条/换模块才需要）

串口发**大写 `P`**，期望：

```
[ASR] 开始写入词条…
[ASR] +5 kai shi
[ASR] +1 wo pa shu
[ASR] +2 wo yao de hen da
[ASR] +3 wo xi huan chai kai xiang
[ASR] +4 wo zai hu shen bian
[ASR] 词条写入完成，模式=1(循环)，第一条=唤醒词
```

### 4.2 一次完整判院

1. 说 **"开始"**（唤醒），**停 1–2 秒**；
2. **慢说**："我怕输"；
3. 期望串口：

```
[ASR] 唤醒词
[ST] ARMED -> LISTENING
[INTENT] 识别到 1 号 → "我最怕输…"
[WS-TX] text "我最怕输…"
[WS-TX] vad speech_start
[WS-TX] vad speech_end
[ST] LISTENING -> THINKING
[WS-RX] tts start text="唔……让我看看。"
[WS-RX] result house=courage
[TTS] house=courage (赤翎)
[TS] TTFC=…（正数）
[WS-TX] bye done (dev_ts …)
```

4. 主机：`/v1/sessions?n=1` 应看到 `house=courage`、`ttfc_ms` 非空。

### 4.3 静音救场

只唤醒、不说话：
- 约 **12 s** 出 `tts start text="唔……你在想什么呢？"`；
- 约 **20 s** host 发 `bye{silence}` 并断开；
- 设备 30 s 兜底不应先触发；
- 重新唤醒能继续（新 sid 可接受）。

### 4.4 识别率（必须做）

每个词条 **20 次**，记录成功次数；目标 ≥90%。不达标就：
- 缩短词条（3–4 音节）；
- 放慢语速、加大停顿；
- 检查麦克风距离/供电噪声。

---

## 5. 主机侧这轮改了什么（影响你的观感）

| 改动 | 对设备的影响 |
|---|---|
| `text` 优先，零音频也能判 | 旧固件也能用；不再需要给静音帧填底噪 |
| 静音默认 **12 s / 20 s** | 12 s 才救场，20 s 收尾；设备 30 s 不应先触发 |
| 任何 `bye` 都不断连 | 设备 `bye{done/timeout}` 后连接复用，sid 可能不变 |
| `vad speech_start` 即停表 | 你补发后，识别成功不会再被插嘴 |
| TTS 帧按 60 ms 节拍 | 桥接句能完整念完；`tts{stop}` 不硬停 |
| TTFC 只接受 `0–120 s` | 旧固件 `t5b<t0` 会记 `clock_skew`，不再负数 |

---

## 6. 需要你确认的 6 件事

1. 词条 1–4 **保持不动**（已验 6/6），只把 5 号唤醒统一为 **"开始 / kai shi"** —— 确认？
2. 是否同意加一行开机版本日志（`fw` 短 hash + `listen_timeout`）？
3. `LISTEN_TIMEOUT_MS=30000` 是否合适（host 20 s 收尾，设备 30 s 兜底）？
4. 12 s 静音值在真机上是否够（按"慢说 + 停顿"实测）？
5. 学院名默认用**原创**（赤翎/玄渊/星枢/穗垣）还是切 HP 原名？——默认原创，若要改告诉我。
6. 现场是否加一颗 LED/提示音做"可以说了"的反馈？（当前没有，观众只能靠主持提示）

---

## 7. 风险与依赖

| 风险 | 说明 | 处置 |
|---|---|---|
| 半双工是假的 | 帽子说话时 LD3320A 仍在听，可能自触发 | 主持脚本：帽子说话时观众不说话 |
| 旧固件未烧 | 板上 5d845bb，`vad_start`/t0/30 s 都没有 | 烧 main，回传版本行 |
| 识别率未知 | 灵敏度低、长句差 | 20 次/句测试；不达标缩词条 |
| 12 s 未真机验证 | 依赖语速/停顿 | 按 4.3 实测，必要时调 15 s |
| 无麦/无功放 | 上行全零、0x02 忽略 | 已接受，文档写明 |

---

## 8. 交付物与安全

- **用仓库 `fw/设备端/` 的 main**，不要再用 `设备端(2).zip`（它等于 `5d845bb`，比 main 旧）。
- **不要**把 `secrets.h` 提交或外发；已外流的密码/令牌全部轮换。
- 回传：5 条启动/识别日志 + 1 条 `/v1/sessions` 行 + 识别率表（20×4）。
