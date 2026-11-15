# 分院帽 · 会话协议 v1（帽子 ↔ 云端实时语音）

> 状态：草案 v1.0，可直接照此实现。
> 适用：ESP32-S3（或树莓派）端侧 + 云端流式语音服务（ASR→LLM→TTS）。
> 设计前提：60–90 秒单人会话、半双工为主、弱网、现场在上海；首字延迟 ≤2.0 s 是硬指标。
> 相关文档：`01-acoustic.md`、`02-edge.md`、`03-cloud.md`、`04-experience.md`、`05-exec.md`。

---

## 0 一句话结论

**用「WSS + 二进制 Opus 音频帧 + 文本 JSON 控制帧」这一套，不要用 AWS IoT Core 传音频。**
IoT Core 是为小消息设计的（单条 ≤128 KB、QoS 0/1），拿它传 16 kHz 实时音频会在延迟和抖动上吃亏；而 WebSocket 是双向长连接，二进制帧天然适合音频，且能被任何反向代理/云主机承载。
**控制面与音频面分开发**：音频走二进制（省带宽、省解析），状态走文本 JSON（可读、好排障）。

---

## 1 分层

| 层 | 链路 | 格式 | 说明 |
|---|---|---|---|
| L0 | 麦克风 → MCU | I2S，16 kHz / 16 bit / 单声道 | 硬件 |
| L1 | MCU → 云 | WSS，二进制帧，Opus 60 ms | 单向流，16–24 kbps |
| L2 | 云 → 帽子 | WSS，二进制帧，Opus 60 ms | 24 kHz 或 16 kHz |
| L3 | 双向控制 | WSS 文本帧，JSON | 会话状态、VAD、ASR、结果、错误 |
| L4 | 云内 | ASR 流 → LLM 流 → TTS 流 | 服务内部，不暴露给设备 |

**为什么音频不用 JSON+base64**：base64 会让体积涨 33%，且每帧都要解析字符串，ESP32-S3 的 CPU 花在这上面不值得。二进制帧头只有 5 字节。

---

## 2 连接与鉴权

| 项 | 值 |
|---|---|
| 端点 | `wss://<host>/v1/voice` |
| TLS | 1.2+，必须 |
| 鉴权 | `Authorization: Bearer <deviceToken>`（演示期固定 token；量产换一机一证 + 短期 JWT） |
| 子协议 | `subprotocol: "sortinghat.voice.v1"` |
| 心跳 | 客户端每 15 s 发 `ping`（文本），服务端回 `pong`；30 s 无响应则重连 |
| 重连 | 指数退避 1/2/4/8/15 s；`sessionId` 在 30 s 内可续 |
| 单会话上限 | 120 s（超时服务端主动 `bye`，防挂死） |

---

## 3 帧格式

### 3.1 二进制帧（音频）

```
+------+------------------+-------------------+
| type | seq (u32 BE)     | payload           |
| 1 B  | 4 B              | Opus 包（≤ 200 B） |
+------+------------------+-------------------+
```

| type | 方向 | 含义 |
|---|---|---|
| `0x01` | 帽子 → 云 | 上行麦克风音频（16 kHz，60 ms/帧） |
| `0x02` | 云 → 帽子 | 下行 TTS 音频（24 kHz，60 ms/帧） |
| `0x03` | 帽子 → 云 | 预录提示音上行确认（可选） |

- `seq` 每方向独立，从 0 递增；服务端按 `seq` 检测丢包（跳号 >3 记一次 `lost`）。
- 每帧一个 Opus 包，**不要**把多帧打包进一个 WebSocket 消息。
- 帧率：60 ms → 16.7 帧/s；16 kbps 时每帧约 120 B。

### 3.2 文本帧（控制，JSON）

统一信封：`{"t": "<类型>", "ts": <毫秒>, ...}`。`ts` 为设备本地单调时钟（ms），用于算延迟。

---

## 4 会话状态机

```
        ┌────────┐  hello/ready   ┌────────┐
        │  IDLE  │───────────────▶│ READY  │
        └────────┘                └────┬───┘
              ▲                       │ start（按钮/唤醒词）
              │ bye                   ▼
        ┌─────┴──────┐   speech_end  ┌──────────┐
        │  SPEAKING  │◀──────────────│LISTENING │
        └─────┬──────┘   tts_start   └────┬─────┘
              │ interrupt                  │ asr_final
              ▼                            ▼
        ┌──────────┐   result       ┌──────────┐
        │INTERRUPT │───────────────▶│THINKING  │
        └──────────┘                └──────────┘
```

设备侧只认四个状态：`IDLE / LISTENING / THINKING / SPEAKING`。灯环颜色与状态一一对应（这是给观众看的，比日志重要）。

---

## 5 消息定义

### 5.1 `hello`（帽子 → 云）

```json
{"t":"hello","ts":0,"dev":"hat-01","fw":"0.3.1","caps":{"aec":true,"opus":true,"micRate":16000,"spkRate":24000,"vad":"device","maxFrameMs":60}}
```

### 5.2 `ready`（云 → 帽子）

```json
{"t":"ready","ts":0,"sid":"s-7f3a9c","vad":{"tailMs":300,"minSpeechMs":200},"audio":{"in":"opus/16k/60ms","out":"opus/24k/60ms"},"budgetMs":2000}
```

### 5.3 `start`（帽子 → 云）

```json
{"t":"start","ts":12400,"mode":"button"}
```
`mode`: `button`（按下开始）/ `wake`（唤醒词）/ `auto`（VAD 自动）。

### 5.4 `vad`（双向）

```json
{"t":"vad","ts":15800,"ev":"speech_start"}
{"t":"vad","ts":18900,"ev":"speech_end","durMs":3100}
```
设备侧优先判定（省上行、省延迟）；服务端同时跑一个 VAD 作兜底，两边不一致时以「更早的 speech_start + 更晚的 speech_end」为准。

### 5.5 `asr`（云 → 帽子，可选）

```json
{"t":"asr","ts":19300,"ev":"partial","text":"我最想要的是……"}
{"t":"asr","ts":20100,"ev":"final","text":"我最想要的是被认可，但我又不想说出来。","lang":"zh"}
```
`partial` 只用于调试/字幕，设备不必显示（会分心）。

### 5.6 `llm`（云 → 帽子，可选）

```json
{"t":"llm","ts":20600,"ev":"first_token"}
{"t":"llm","ts":21200,"ev":"delta","text":"唔……"}
```

### 5.7 `tts`（云 → 帽子）

```json
{"t":"tts","ts":21400,"ev":"start","seg":1,"text":"唔……让我看看。"}
{"t":"tts","ts":23900,"ev":"end","seg":1}
```
- 按句切分，每句一个 `seg`；第一句必须 ≤12 字，用来最快出声。
- 音频帧在 `start` 与 `end` 之间到达；设备收到第一帧即开始播放（预缓冲 1 帧）。

### 5.8 `result`（云 → 帽子）

```json
{"t":"result","ts":41000,"house":"courage","scores":{"courage":82,"ambition":61,"wisdom":55,"loyalty":70},"reasons":["你说「不想被人看见努力」，但你描述目标时用了三次「赢」","你回答第一个问题时停顿了 2.3 秒，答案却最具体","你提到朋友时语速慢了下来"],"line":"那就……去那里吧。","latency":{"asrMs":210,"llmFirstMs":340,"ttsFirstMs":260,"totalMs":1720}}
```
`scores` **只用于内部排序与调试**，不设备显示、不对外展示（对外只讲 `reasons`）。

### 5.9 `interrupt`（帽子 → 云）

```json
{"t":"interrupt","ts":30000,"reason":"button"}
```
服务端收到后立即停止 TTS 合成与下行、取消未完成的 LLM 请求；已发出的音频帧由设备本地丢弃。

### 5.10 `bye` / `error`

```json
{"t":"bye","ts":42000,"reason":"done"}
{"t":"error","ts":0,"code":"asr_timeout","msg":"ASR 超时，已降级为模板台词","fatal":false}
```

错误码：`auth_failed` / `asr_timeout` / `llm_timeout` / `tts_timeout` / `rate_limited` / `bad_frame` / `session_expired`。

---

## 6 可靠性

| 问题 | 策略 |
|---|---|
| 丢包 | 音频帧不重传（实时性优先）；跳号 >3 记一次，超过 10 次触发一次 `error{code:"bad_frame"}` 并建议重连 |
| 断连 | 30 s 内可带 `sid` 重连续话；超过则新会话（观众无感，因为一次会话只有 90 s） |
| 服务端超时 | ASR 2 s 无结果 → 模板句「我没听清，再说一次？」；LLM 3 s 无首 token → 模板句；TTS 2 s 无首包 → 预录音 |
| 并发 | 单帽单会话；服务端按 `dev` 限流（1 会话/设备，10 会话/分钟/IP） |
| 静音 | **6.5 s 无语音 → 帽子主动救场**（预录「唔……你在想什么呢？」，不是判死）；**15 s 仍无语音 → `bye{reason:"silence"}`**，帽灯转黄，提示「再说一句？」 |

---

## 7 延迟预算（目标：说完到出声 ≤2.0 s）

| 阶段 | 目标 | 手段 |
|---|---|---|
| VAD 尾点判定 | 300 ms | 设备侧 VAD，按钮可强制结束 |
| 上行传输 | 30–80 ms | 就近接入；60 ms 帧，不做重传 |
| ASR 尾字 | 200–400 ms | 流式 ASR，边听边转；`speech_end` 后只等尾巴 |
| LLM 首 token | 300–900 ms | prompt ≤800 token；结构化输出；温度 0.8 |
| TTS 首包 | 200–500 ms | 流式合成；首句 ≤12 字 |
| 下行 + 播放启动 | 60–120 ms | 预缓冲 1 帧；双缓冲 |
| **合计** | **1.1–2.4 s** | |

**关键技巧（不是作弊，是角色设计）**：`speech_end` 到达时立刻播一段 **200–400 ms 的预录沉吟**（「唔……」/「有意思……」），把 LLM + TTS 的真实延迟藏进帽子的「思考」里。分院帽本来就该慢条斯理。

---

## 8 端侧状态与灯语

| 状态 | 灯环 | 帽子行为 |
|---|---|---|
| IDLE | 呼吸白 | 待机，麦克风只听唤醒词/按钮 |
| LISTENING | 青色常亮 | 录音，上行音频帧 |
| THINKING | 琥珀色缓慢呼吸 | 已收到 `speech_end`，播放沉吟预录 |
| SPEAKING | 学院色 | 播放 TTS，麦克风静音（半双工） |
| ERROR | 红色闪 2 次 | 播「让我再想想」，回 IDLE |

---

## 9 与云服务的映射（AWS 版）

```
ESP32-S3 ──WSS──▶ EC2 / Fargate 上的 Node 或 Python WS 服务
                     ├──▶ Transcribe Streaming（或第三方流式 ASR）
                     ├──▶ Bedrock（Nova / Claude / Nemotron，流式）
                     └──▶ Polly / CosyVoice（流式 TTS）
                          │
                          └──▶ DynamoDB（会话结果、延迟指标）
```

**为什么不用 API Gateway WebSocket + Lambda**：API Gateway WebSocket 的帧是文本/二进制消息，能转发，但 Lambda 每次调用有冷启动与超时限制，不适合「一路流式合成 20 秒音频」这种长连接场景。3 天内最稳的是**一台 EC2 或 Fargate 任务跑常驻 WS 服务**（t4g.small 足够，约 $0.017/h）。

---

## 10 验收清单（10 条，逐条打勾才算协议跑通）

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 连接与鉴权 | 错误 token 被拒；正确 token 300 ms 内 `ready` |
| 2 | 一次完整会话 | 说 3 句 → 8 s 内听到完整宣布 |
| 3 | 首字延迟 | 10 次采样，≥8 次 ≤2.5 s |
| 4 | 打断 | 播放中按按钮，300 ms 内静音 |
| 5 | 断网 | 拔网 5 s 重插，能重新开始一次会话（不要求续话） |
| 6 | 静音 | 6.5 s 不说话，帽子主动开口救场；15 s 仍无语音才收到 `bye{silence}` 并回 IDLE |
| 7 | 丢包 | 人为丢 5 帧，不崩、不卡死 |
| 8 | 超时降级 | 关掉 LLM，仍能用模板句演完 |
| 9 | 指标 | `result.latency` 四段齐全，且与秒表误差 <200 ms |
| 10 | 并发 | 两顶帽子同时连，互不串音 |

---

## 12 与 xiaozhi-esp32 既有线协议的映射

如果走「官方固件 + 开源 `xiaozhi-esp32-server`」这条最快路线（§5.4 路线①），你实际看到的是它自己的协议，而不是本文件的字段名。两者语义一一对应，**不要把两套混用**：

| 本协议 | xiaozhi 协议（[docs/websocket.md](https://github.com/78/xiaozhi-esp32/blob/main/docs/websocket.md)） |
|---|---|
| `hello` / `ready` | `{"type":"hello","version":1,"transport":"websocket","audio_params":{"format":"opus","sample_rate":16000,"channels":1,"frame_duration":60}}`（双向各发一次） |
| `start{mode}` | `{"type":"listen","state":"start"}`；唤醒词触发时 `{"type":"listen","state":"detect"}` |
| 按钮结束/打断 | `{"type":"listen","state":"stop"}`；播放中打断用 `{"type":"abort","reason":"..."}` |
| 上行音频 `0x01` | **二进制 Opus 帧**（v1 无额外头；v2/v3 带 `uint16 type(0=OPUS,1=JSON)` 头） |
| `asr{final}` | `{"type":"stt","text":"..."}` |
| `llm{delta}` | `{"type":"llm","emotion":"...","text":"..."}` |
| `tts{start/end}` | `{"type":"tts","state":"start"|"stop"}`；字幕用 `{"type":"tts","state":"sentence_start","text":"..."}` |
| 下行音频 `0x02` | 同二进制 Opus 帧 |
| `result{house,...}` | **没有对应帧**——这是我们要加的扩展：自建服务端时直接加；用官方服务端时走 MCP（`{"type":"mcp","payload":{...}}`）或另开一条文本消息 |

**两条路线怎么选**：
- 路线①（今晚出声）：用它的协议，**本文件当对照表**，不要改固件字段；
- 路线②（完全可控）：用本文件，固件里把 `hello/listen/abort` 的字段改成自己的。

**共同点必须一致**：16 kHz 单声道、Opus、60 ms 帧、文本帧走 JSON、二进制帧走 Opus——这四条两边相同，所以从 ① 迁到 ② 时音频链路不用重写。

---

## 13 待确认

1. **音频帧长 60 ms 还是 20 ms**：60 ms 省包但不耐抖动；若现场 Wi-Fi 差，降到 20 ms（3 倍包数，延迟更平滑）。
2. **下行 24 kHz 还是 16 kHz**：24 kHz 音质好，但 ESP32-S3 要做重采样；如果 TTS 能直接出 16 kHz，省一步。
3. **是否保留 `llm` 流式字幕**：调试期保留，正式演示关掉（字幕会抢戏）。
