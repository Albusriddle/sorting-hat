# 协议（现状）

> **线上事实源是 `host/app/protocol.py`**（消息构造与字段校验），本文是它的说明。
> `docs/design/00-protocol.md` 是 **2026-11-15 的设计快照**（用的是 `t` 键、`opus/24k`、`hello/caps`），与现状不同，不要按它实现。

## 1. 传输

- WebSocket，子协议 `sortinghat.voice.v1`
- 鉴权：`Authorization: Bearer <DEVICE_TOKEN>` 或 `?token=...`
- 当前默认明文 `ws://`（现场热点）；`REQUIRE_TLS=1` 时用 `wss://`，缺证书拒绝启动

## 2. 帧

| 类型 | 方向 | 结构 |
|---|---|---|
| `0x01` | 设备→host | Opus（可选，需 `HAT_ENABLE_OPUS`） |
| `0x04` | 设备→host | PCM16 / 16 kHz / 20 ms（320 样本 / 640 B） |
| `0x02` | host→设备 | PCM16 / 16 kHz / 60 ms（1920 B） |

所有二进制帧 = `1 B type + 4 B seq(BE) + payload`。

## 3. 文本消息

| 消息 | 方向 | 关键字段 |
|---|---|---|
| `ready` | host→设备 | `sid`、`audio{in,out}`（`pcm16\|opus/16000/20ms`、`pcm16/16000/60ms`）、`budget_ms`、`server_time`、`vad` |
| `listen` | 设备→host | `state:start/stop` |
| `vad` | 设备→host | `ev:speech_start/speech_end` |
| `text` | 设备→host | `text`（词条映射，≤200 字；host 优先用它，不再调 ASR） |
| `tts` | host→设备 | `state:start/stop`、`seg`、`text`（桥接句，设备用 `speakUTF8` 念） |
| `result` | host→设备 | `house`、`reasons[3]`、`line`（宣布句）、`scores`、`announce{variant,file}`、`latency` |
| `error` | host→设备 | `code`、`degrade`、`fatal` |
| `bye` | 双向 | `reason:done/doff/silence/timeout`、`dev_ts{t_arm,t0,t5a,t5b,t_stop}` |

## 4. 语义

- `house` 只由 `judge.py` 的 `argmax` 产生；模型只给 `evidence/scores`。
- 反集中/配额只在历史 ≥10 次时启用，演示期同句同果。
- 设备发 `text` 时，host 直接用它；没有 `text` 才走 ASR（当前无麦，必失败→追问，不判院）。
- 全零/低能量音频（RMS < `MIN_AUDIO_RMS`）不判院，只回"没听清"。
- **VAD 归属**：由设备判定（能量阈值 + 300 ms 尾点），host 只响应 `vad{speech_end}`，**不自己跑 VAD**。
- `bye{reason:"done"}` 表示本次会话结束但连接继续；host 收到后落库并保留连接。
