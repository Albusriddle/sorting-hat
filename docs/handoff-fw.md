# 给下位机 / 硬件侧的工作报告（host → fw，2026-11-16）

> 目的：把上位机这一轮改了什么、固件要配合什么、烧板后怎么验收，一次说清。
> 对应提交：`9243f94`。所有条目都可回滚，回滚方式是 `git revert` + 重烧上一版固件。

## 1. 上位机改了什么（影响固件的部分）

| # | 改动 | 对固件的影响 |
|---|---|---|
| 1 | **`text` 通路正式启用**：`{"type":"text","text":"…"}` 存为本次会话文本，判决优先用它，不再调 ASR | 你的 `hat_intent` 已经在发，保持不变；文本上限 200 字 |
| 2 | **零音频闸**：PCM 全零或 RMS < 50 时不判院，只回"没听清" | 无麦时上行全零是**预期**；不要把 RMS 闸当故障 |
| 3 | **`bye{done}` 不断连**：host 收到 `reason=done` 只落库、保留连接 | 固件在 `result` 后补发 `comm_send_bye("done")`（已改），**不要删**；删了就没有 `ttfc_ms` |
| 4 | **`ready.audio` 改 `pcm16\|opus/16k/20ms`、`pcm16/16k/60ms`** | 你的 `parse_rate()` 能正确解析 `16k`（默认值仍是 16000） |
| 5 | **鉴权改等值比较**（header 或 `?token=` 均可） | `secrets.h` 的 `TOKEN` 必须等于 host 的 `DEVICE_TOKEN`，否则 4401 |
| 6 | **`tts{start}` 带 `text`（桥接句）**，host 限制 ≤40 字 | 你已改为 `tts.speakUTF8(text)`；`tts{stop}` 要 `tts.stop()`（已改） |
| 7 | **watchdog/静音救场**：120 s 会话上限、6.5 s 救场、15 s `bye{silence}` | 设备的 10 s LISTEN 超时仍保留；两套不冲突，先到先触发 |

## 2. 固件这一轮必须做的（烧板清单）

| # | 项 | 文件 | 验收 |
|---|---|---|---|
| F1 | 学院名双套 + 默认原创 | `phrases_gbk.h`（已由 `tools/gen_phrases.py` 重新生成）、`hat_config.h` 的 `HAT_HOUSE_ORIGINAL 0` | 串口 `[TTS] house=courage (赤翎)`，耳朵听到"赤翎" |
| F2 | 桥接句出声 | `hat_comm.cpp` 的 `tts{start}` → `tts.speakUTF8(text)` | 1 m 处听到"唔……让我看看。"这类整句 |
| F3 | 唤醒改 5 号 | `hat_config.h` 的 `ASR_WAKE_WORD_ID 5`；模块烧 5 条（1–4 内容，5 唤醒） | 串口 `A` 打印 `[INTENT] 识别到 1 号`；说"分院帽"（5 号）能唤醒 |
| F4 | `result` 后补 `bye{done}` | `hat_comm.cpp` 的 `result` 分支（已加） | 串口 `[WS-TX] bye done (dev_ts …)`；host `/v1/sessions` 的 `ttfc_ms` 非空 |
| F5 | `tts{stop}` **不要**硬停合成 | `hat_comm.cpp` 的 stop 分支去掉 `tts.stop()`；只在 `abort`/按钮里停 | 桥接句能念完；按 `b` 能立刻打断 |
| F6 | 功放 LRC 改 21 | `hat_config.h` 的 `PIN_SPK_LRC 21`（无 SPK，仅防冲突） | 编译通过；接线时不要再接 16 |

## 3. 硬件侧需要确认的

| # | 项 | 说明 |
|---|---|---|
| H1 | 模块词条最终文案 | 1–4 句内容必须与 `hat_intent.cpp` 的四句**逐字一致**（模块里烧拼音，编号对应） |
| H2 | 5 号唤醒词 | 模块里第 5 条烧"分院帽"；`ASR_WAKE_WORD_ID` 与之一致 |
| H3 | 学院名选型 | 默认原创（IP 安全）；若要原名，改 `HAT_HOUSE_ORIGINAL 1` 重烧，host 不用改 |
| H4 | 麦克风 | 没有就是全零帧；若今天能加 INMP441/USB 声卡，告诉我，host 的 `MIN_AUDIO_RMS` 与 Transcribe 可直接启用 |
| H5 | 喇叭音量 | CSK4002 板载喇叭；1 m 处能否听清请实测，必要时加外置音箱（host 不控制音量） |

## 4. 烧板后请回传这 5 条日志

```
[BOOT] asr=ok tts=ok ...
[NET] sid=... in=pcm16|opus/16k/20ms out=pcm16/16k/60ms (spk=16000)
[INTENT] 识别到 1 号 → "我最怕输，但我更怕自己在关键时候退缩。"
[TTS] house=courage (赤翎)
[WS-TX] bye done (dev_ts t0=... t5b=...)
```

host 侧对应检查：`/stats` 有 `last.text`；`/v1/sessions` 有 `ttfc_ms`；`/stats.audio.rms` > 0 仅当有真麦。

## 5. 上位机保证给固件的契约

| 项 | 值 |
|---|---|
| `ready` 时延 | ≤300 ms（连上即发，不等 hello） |
| `text` 上限 | 200 字（超出截断） |
| 桥接句上限 | 40 字 |
| 音频下行 | PCM16 / 16 kHz / 60 ms / 1920 B（`0x02`） |
| 会话上限 | 120 s（watchdog） |
| 静音 | 6.5 s 救场、15 s `bye{silence}` |
| `bye{done}` | 不关连接，只落库 |
| 判决 | 只由代码 argmax 产生；模型只给证据/分数 |

## 6. 还没解决的（不在本轮）

- 真实 ASR（无麦，已接受）。
- Opus/VAD 真机验证。
- 明文 ws（现场内网，TLS 留 `REQUIRE_TLS` 开关）。
- 12 句预录（改为可选；设备 TTS 直接念院名）。

---

## 7. 2026-11-17 联调后的变更（host 侧已改，固件只需重烧 F5）

| # | 联调问题 | host 修法 | 固件要做什么 |
|---|---|---|---|
| 1 | 零音频闸挡住 `text` | 有 `text` 直接进引擎；无 `text` 且 provider=mock 时不再凭 pcm 判院 | 无；**请删掉 ±121 底噪绕过** |
| 2 | 第二次 `tts start` 像"没念" | `0x02` 帧按 60 ms/帧节拍发，`t4` 取首帧；`result` 在桥接句播完后才到 | 重烧 F5：`tts{stop}` 不硬停，只有 `abort`/按钮才停 |
| 3 | 会话结束后静音计时还在跑 | 计时按"轮"：`vad` 即取消，失败不重挂，`bye` 取消 | 无；不会再收到莫名的 `bye{silence}` |

**验收**：`w`→`A`→`e`（全零 PCM）应出 `result`；静音 6.5 s 的救场句能完整念完；失败一轮后等 20 s 不应收到 `bye`。
