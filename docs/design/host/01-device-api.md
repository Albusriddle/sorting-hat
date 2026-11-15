# 分院帽 · 上位机对下位机提供的接口与服务

> **基线**：`统一准则-通信协议-仓库施工.md` v1.0（2026-11-15）为最高事实源；`analysis/00-protocol.md` 为协议唯一事实源。
> **本文定位**：`00-protocol.md` 的**服务面投影**——回答"云端要给帽子什么"，不是第二个事实源。字段名、错误码、时间戳一律照抄准则；本文新增项全部标 `需 RFC`。
> **owner**：B（设备实现方 A 复签）；**冻结**：G2 帧与字段、G4 完全冻结（11/17 12:00）。
> **外部核实**：xiaozhi 线协议取自官方 `docs/websocket.md`（commit `d7cdefb`，见 §8）。

---

## 0. 结论先行

| 问题 | 答案 |
|---|---|
| 设备硬依赖几样 | **5 样**：一次 WSS 握手 + `ready` + `listen` + 上行 Opus + 下行 Opus/`tts` |
| 最重要的三个接口 | ① `ready`（300 ms 内回，决定能不能预缓冲）② 下行 `0x02`+`tts{start}`（决定 TTFC）③ `result`（决定灯色与"宣布"是否同一件事） |
| 最容易漏的服务 | **时间基准（`recv_wall` 回写）+ 设备侧 4 个时间戳的回传载体**——漏了 TTFC 算不出来，DoD 第 4 条直接红 |
| 最大风险 | 准则写 `bye{reason}`/信封 `t`，xiaozhi 固件只有 `type` 且无 `bye`；不改就只能在路线②里自建固件 |

**五个数（本文所有超时都以它为准）**：TTFV = `t5a−t0` ≤ 0.6 s；TTFC = `t5b−t0`，预算 1.24 s / 上台线 1.8 s / 内部 Gate 2.5 s；心跳 15 s；断网检测 1.2 s、按钮模式就绪 5 s；单会话上限 120 s。

---

## 1. 设备视角的最小依赖集

**结论**：设备只硬依赖**一条连接、一条上行、一条下行，外加三个必须被受理的语义（会话号、开录、开播）**；其余全部可选，缺了只是降级。但 `result` 要按 D0 对待——技术上可选，舞台上缺了就露馅。

### 1.1 没有它设备就演不了（硬依赖，5 项）

| # | 依赖 | 缺了会怎样 | 不可退让的判据 |
|---|---|---|---|
| H1 | `wss://<host>/v1/voice` + `Authorization: Bearer` + 子协议 `sortinghat.voice.v1` | 连不上，帽子一句不说 | TLS 1.2+；MAJOR≠1 拒握手 |
| H2 | 服务端 `ready`（含 `sid`） | 不知道开几帧预缓冲，`tts` 无法对齐；无 `sid` 不能续期 | **≤300 ms** 回（验收 1），3 s 未到即重连 |
| H3 | `listen{state:"start"}` 被受理 | 服务端不知何时开录，`t1` 无锚点 | 5 s 无任何下行 → 设备回 ARMED |
| H4 | 上行二进制 `0x01` 被消费 | 没声音进来，ASR 永远空 | 不重传；跳号 >10 记 `bad_frame` |
| H5 | 下行二进制 `0x02` + `tts{state:"start"/"stop"}` | 帽子不会说话 | 首帧 800 ms 预算 / 2 000 ms 硬超时 |

### 1.2 没有它只是降级（可选，按影响排序）

| 等级 | 接口 | 缺失后的表现 | 谁来兜 |
|---|---|---|---|
| **D0 露馅** | `result{house,reasons,line}` | 还能说话，但灯不变学院色、说不出理由 | 设备只播 TTS；JSONL 标 `no_result` |
| **D0 露馅** | `recv_wall` 时间基准 + `bye.dev_ts` | TTFC 算不出，验收指标作废 | 降级为 `t5b−t1` 近似，标 `incomplete`，不进统计 |
| D1 音色变 | `stt{final}` / `llm{delta}` | 字幕与调试看不见；判决仍成立 | 设备不依赖（准则 §3.6）；只给 console 用 |
| D1 音色变 | `tts` 之外的服务端 VAD 兜底 | 设备 VAD 阈值失准时无人纠偏 | 取"更早 start + 更晚 end" |
| D2 无感 | `error`、`ping/pong`、`config`、`bye` | 排障变难、现场调参要重刷固件 | 设备本地默认值 + 300 ms 本地静音 |

**一条纪律**：可选接口的缺省语义必须写进 schema（准则 §3.4"新增必 optional 且写缺省语义"），否则 CI 的协议 lint 关不过。

**3 天/3 人的现实取舍**：§1.1 那 5 项就是今晚 A2 汇合点必须联调完的范围；§1.2 里只有两个 D0 允许进彩排前补齐，其余（`llm` 字幕、`config` 热更新）**默认不做**，砍的顺序按准则 §5.3。

---

## 2. 接口全表（核心）

**结论**：18 个接口，其中 6 个构成硬依赖链路；**另有 4 处需 RFC**（信封 `type`、`config`、`bye.dev_ts`、`abort.reason:"mute"`），见 §8。**信封统一 `{"t":…,"ts":…}`，`ts` 是设备单调时钟 ms；服务端在每个下行文本帧补 `recv_wall`（UTC ms）**——这就是"时间基准服务"，不新增消息类型。

> 本文所有 JSON 片段按准则现值写 `t`。若 C1（`t`→`type`）在 G4 前通过 RFC，全文机械替换即可，**字段集合不变**。

| # | 接口/消息 | 方向 | 触发 | 载荷要点 | 超时 | 幂等 | 错误码 | 设备失败时怎么办 |
|---|---|---|---|---|---|---|---|---|
| 1 | WSS 握手 | 设备→云 | 上电/戴上/重连 | Header：`Authorization: Bearer`、`Protocol-Version:1`、`Device-Id`(MAC)、`Client-Id`；子协议 `sortinghat.voice.v1` | 3 s | 是 | `auth_failed`/`protocol_unsupported`/`rate_limited` | 退避 1/2/4/8/15 s；3 次失败→按钮模式 |
| 2 | `hello` | 设备→云 | 握手后首帧 | `dev`、`fw`、`caps{aec,opus,vad,max_frame_ms}`、`audio_params{format,sample_rate,channels,frame_duration}` | — | 重发忽略 | `protocol_unsupported`（MAJOR≠1 拒） | — |
| 3 | `ready` | 云→设备 | 收到 `hello` | `sid`、`vad{tail_ms,min_speech_ms}`、`audio_params`（下行）、`budget_ms`、`recv_wall` | **300 ms 实测 / 3 s 上限** | 是 | — | 3 s 未到→重连；不计入会话 |
| 4 | 时间基准（`recv_wall`） | 云→设备 | 随每个下行文本帧 | 服务端 UTC ms；设备算 `Δ=recv_wall−ts` 并随帧更新 | — | 只读 | `clock_skew`（相对首帧漂移 >500 ms） | 记 `clock_skew`，本次指标作废 |
| 5 | `listen{state:"start"\|"stop"\|"detect"}` | 设备→云 | 戴上/按钮/摘下 | `state`、`mode`(可选)、`ts` | **5 s 无下行响应** | 重发同 `state` 幂等 | — | 回 **ARMED** 并闪一次灯（六态无 IDLE，见准则 §7.5） |
| 6 | 上行 Opus `0x01` | 设备→云 | LISTENING 每 60 ms | 1 B `type=0x01` + 4 B `seq`(u32 BE) + Opus ≤200 B | 不重传 | 非幂等（`seq` 单调） | `bad_frame` | 丢弃并计数，**不断连** |
| 7 | 下行 Opus `0x02` | 云→设备 | `tts{start}` 之后每 60 ms | 同帧头；24 kHz | 首帧 800 ms / 硬 2 000 ms | 非幂等 | `tts_timeout` | 播预录 A3，**不回 error** |
| 8 | `vad{ev}` | 双向 | 设备优先，服务端兜底 | `ev:"speech_start"\|"speech_end"`、`dur_ms` | 服务端 1 200 ms 无 `speech_end` 即用自身 VAD | 是（取并集：更早 start + 更晚 end） | — | 设备不发 → 服务端 VAD 接管，流程不变 |
| 9 | `stt{state:"partial"\|"final"}` | 云→设备 | ASR 流 | `text`、`lang` | 软 600 ms（不降级）/ **硬 2 000 ms** | 是（同文本可重发） | `asr_timeout` | 播「我没听清，再说一次？」，`degrade:"prompt_again"` |
| 10 | `llm{delta}` | 云→设备 | 首 token / 增量 | `text` | 软 900 ms / 硬 3 000 ms | 否 | `llm_timeout` | 模板首句 + 兜底打分，`degrade:"template_line"` |
| 11 | `tts{state:"start"\|"sentence_start"\|"stop"}` | 云→设备 | TTS 流 | `seg`、`text`（首句 ≤12 字） | 800 ms / 硬 2 000 ms | 是 | `tts_timeout` | Polly / 预录音，`degrade:"polly"` |
| 12 | `result{house,reasons,line,latency}` | 云→设备 | 判决完成 | `house` 四枚举；`reasons` ≤3；`line`；`latency{asr_ms,llm_first_ms,tts_first_ms,total_ms}`；**不带 `scores`** | 会话末 3 s | **是**（设备按 `last_msg_id` 去重，只播一次） | `upstream_5xx` | 缺 `result`→只播 TTS、灯不变色 |
| 13 | `abort{reason}` | 设备→云 | 按钮 / 摘下 / 长按静音 | `reason:"button"\|"doff"`（`mute` 需 RFC） | 立即 | 重复忽略 | — | **本地先静音（≤300 ms）**，忽略上行失败 |
| 14 | `ping`/`pong` | 双向 | 每 15 s | `ts` | 30 s 无 `pong`→重连 | 是 | — | 重连；**不承担 1.2 s 断网检测** |
| 15 | `error{code,msg,fatal,degrade}` | 双向 | 异常 | `fatal` 只 3xx；1xx/2xx **必带** `degrade` | — | 同 code 60 s 内去重 | 码表 10 个 | 3xx→ERROR 红闪 2 次；2xx→继续演完 |
| 16 | `bye{reason}` | 双向 | 收尾 | `reason:"done"\|"doff"\|"silence"\|"timeout"` | 120 s 会话上限 | 是 | — | 收不到→服务端强断；设备本地回 OFF |
| 17 | `config{volume,tail_ms,house_colors,lines_rev,version}` | 云→设备 | 管理面 `/v1/config` | `volume` 0–100（默认 70）；`version` 单调 | 2 s | 是（按 `version` 丢弃旧包） | `protocol_unsupported` | 忽略并保留旧配置，**需 RFC** |
| 18 | 会话续期 | 设备→云 | 断连后重连 | 同握手 + `sid` | **30 s** | 是 | `session_expired` | 超 30 s→新会话（观众无感） |

**三个关键片段**

```json
{"t":"ready","ts":0,"sid":"s-7f3a9c","budget_ms":1800,
 "vad":{"tail_ms":300,"min_speech_ms":200},
 "audio_params":{"format":"opus","sample_rate":24000,"channels":1,"frame_duration":60},
 "recv_wall":1763212345678}
```

```json
{"t":"result","ts":41000,"last_msg_id":"s-7f3a9c:1","house":"courage",
 "reasons":["你说「不想被人看见努力」，但描述目标时用了三次「赢」"],
 "line":"那就……去那里吧。",
 "latency":{"asr_ms":210,"llm_first_ms":340,"tts_first_ms":260,"total_ms":1720}}
```

```json
{"t":"bye","ts":42000,"reason":"done","dev_ts":{"t_arm":900,"t0":15200,"t5a":15600,"t5b":16900}}
```

**四条横贯规则**（表外的契约，比表内更容易违约）：
1. **`result` 必须与宣布句的 `tts{start}` 同时或略早（同一 100 ms 内）到达**，否则"灯变色"与"宣布学院"变成两件事，舞台上像 bug。
2. **未知 `t`/字段静默丢弃并计数，不许回 `error`**（准则 §3.4，要有单测）。
3. **1xx/2xx 必带 `degrade`**，`fatal` 只出现在 3xx——"断了怎么办"就查这个字段的统计。
4. **静音不上行**：长按 2 s 是设备本地动作，上位机只通过 `config.volume` 干预；`abort{reason:"mute"}` 属新增枚举，需 RFC。

### 2.1 三个最容易被误读的边界

| 边界 | 正确做法 | 常见误做 |
|---|---|---|
| **预热点有两处** | 上游预热走 `POST /v1/preheat`（schema/TTS 连接/TLS）；设备侧预热 = **把握手提前到戴上之前 ≤30 s**，不产生新消息 | 让设备自己在会话开始时才建链——冷 TLS 0.78–1.76 s，TTFC 必崩 |
| **日志回传只回时间戳** | 设备只回 `dev_ts` 四个数与错误计数；日志正文、音频、`stt` 明文不上行 | 把 `stt.text` 或 PCM 回传——既违合规又抢带宽 |
| **健康检查分两层** | `/healthz` 查进程、`/readyz` 查上游；设备侧"健康"由 `ping`/`pong`（15 s/30 s）表达 | 用 `/readyz` 当断网判据——它测的是服务端，不是链路 |

---

## 3. 管理面 API（给人、给工具，永远不给设备）

**结论**：8 个端点，全部挂 `X-Admin-Token`，反向代理只对外暴露 `/v1/voice`；设备侧网络路径里**根本看不到这些 URL**。演示时它们只由 `make preflight`、CI 和 console 调用。

| 方法/路径 | 请求 | 响应 | 谁调用 | 幂等/超时 |
|---|---|---|---|---|
| `GET /healthz` | 无 | `200 "ok"`（进程活着，不查上游） | docker/systemd healthcheck、冒烟第 1 步 | 幂等 / 200 ms |
| `GET /readyz` | 无 | `200`；`{"providers":{"asr":true,"llm":true,"tts":true},"preheat_age_ms":42,"sessions":{"active":0},"build":"git7"}`；未就绪 `503` | 开场前 10 min 预检、`make preflight` | 幂等 / 500 ms |
| `POST /v1/preheat` | `{"warm":["asr","llm_schema","tts","tls"],"budget_ms":90000}` | `{"ok":true,"ms":61234,"detail":{"llm_schema_ms":58000,"tts_voice":"cosyvoice-v3.5-flash","asr_region":"ap-northeast-1"}}` | 开场前脚本、CI | 幂等（重复只刷新缓存）/ **90 s**（schema 首编译上限） |
| `POST /v1/replay` | `{"fixture":"fixtures/session-hat01-20261115-2312.ndjson","assert":{"house":"courage"}}` | `{"sid":"s-replay-1","house":"courage","timestamps":{…},"diff_ms":{"max":31},"ok":true}` | CI 七关第 7 关、B 改协议自查、A 复验 | 幂等 / 30 s |
| `GET /v1/sessions/{sid}` | 路径参数 | `{"sid","dev","state","t_arm","t0","t1","t2","t3","t4","t5a","t5b","house","reasons","errors":[],"fixture","aborted"}` | 大屏 console、排障、A 查断网 | 幂等 / 200 ms |
| `GET /v1/metrics` | 无 | Prometheus 文本：`ttfc_ms` 直方图、`ttfv_ms`、`sessions_total{result}`、`errors_total{code}`、`ws_active` | console、PPT 取数、CI 对账 | 幂等 / 200 ms |
| `POST /v1/kill` | `{"drain_ms":3000,"reason":"stage-reset"}` | `{"closed_sessions":1,"draining":true}` | 主讲/设备手紧急复位、彩排 | **非幂等** / 5 s |
| `POST /v1/config` | `{"version":12,"volume":70,"tail_ms":300,"min_speech_ms":200,"house_colors":{…},"lines_rev":"g3"}` | `{"applied":["volume"],"rejected":[],"version":12}` | C 改灯色/台词、B 调 VAD、现场调音量 | 幂等（按 `version`）/ 2 s |

**`/v1/kill` 的语义要写死**：先给在线会话发 `bye{reason:"timeout"}`（复用现有枚举，**不新增 `idle`**），再拒绝新握手，`drain_ms` 后退出。它是"停服"不是"重启固件"——设备侧只感知到一次正常收尾。

---

## 4. 时序

### 4.1 正常一次会话（60–90 s，设备与服务端各自打点）

| # | 动作 | 设备打点 | 服务端打点 | 预算 |
|---|---|---|---|---|
| 1 | 预连接 + 握手 + `hello` | — | 抄 `recv_wall` | 冷 TLS 0.78–1.76 s，**因此必须提前建链** |
| 2 | `ready{sid,audio_params,budget_ms}` | 定预缓冲帧数 | — | ≤300 ms |
| 3 | 戴上（200 ms 消抖）→ ARMED 白呼吸 | **`t_arm`** | — | — |
| 4 | `listen{state:"start"}` → LISTENING 青 | — | 建会话上下文 | ≤50 ms |
| 5 | 上行 `0x01` × N（60 ms/帧） | — | 边收边转 | 30–80 ms |
| 6 | 末字 + 300 ms 尾点 → `vad{speech_end}`，**立即播预录沉吟** | **`t0`**；+≈400 ms 记 **`t5a`**（沉吟首帧） | **`t1`** 末帧到达 | TTFV ≤0.6 s |
| 7 | 服务端 ASR final → `stt{state:"final"}` | 可选显示 | **`t2`** | 软 600 ms |
| 8 | LLM 首 token → `llm{delta}` | — | **`t3`** | 软 900 ms |
| 9 | 判决（`argmax` + 反集中 ×0.85） | — | — | 纯函数，<10 ms |
| 10 | TTS 首包 → `tts{start,seg:1}` + `0x02` | **`t5b`**（真实内容首帧） | **`t4`** | 800 ms |
| 11 | `result` 与宣布句 `tts{start}` 同批下发 → 灯转学院色 | 校 `last_msg_id` | — | 同 100 ms 内 |
| 12 | `tts{stop}` … `bye{reason:"done"}` + `dev_ts` | 回 OFF | 落一行 JSONL | 120 s 上限 |

**对账**：`t5b−t0` 与秒表差 >200 ms ⇒ 本次指标作废；>500 ms ⇒ 同时记 `clock_skew`（前者是验收，后者是错误码）。

### 4.2 异常一：ASR 超时

`t0` → 沉吟播完（0.4 s）→ 600 ms 无 `partial`（软目标，继续等）→ **2 000 ms 无 `final`** → 服务端发 `error{code:"asr_timeout",fatal:false,degrade:"prompt_again"}` + `tts{start}`「我没听清，再说一次？」→ 设备 THINKING→SPEAKING→ARMED，允许重说一次；**会话不结束**。连续 2 次 → `bye{reason:"timeout"}`。设备若连 `error` 都收不到（链路已断）→ 1 800 ms 无 TTS 首帧 → 播 A3 降级句 → 切 LOCAL 流程（`02-edge.md` §6.2）。

### 4.3 异常二：设备打断（按钮）

SPEAKING 中按下 → **设备本地 300 ms 内静音（先于任何上行）** → `abort{reason:"button"}` → 服务端停 TTS、取消 LLM、清下行队列 → 回 `tts{stop}`（在途帧由设备丢弃）。服务端**不判错、不计 `tts_timeout`**；`result` 若已生成仍照发（灯色仍要变），但不再播。重复 `abort` 忽略。本次会话 `aborted=true`，**不进 TTFC 统计**。

### 4.4 异常三：拔网

| 时刻 | 设备 | 服务端 |
|---|---|---|
| T+0 | 上行发送失败 + 下行 1.2 s 全静默 | 无感知（TCP 半开） |
| T+1.2 s | **判 OFFLINE**（复用 ARMED 黄常亮），关 WS | — |
| T+5 s | **按钮模式就绪**：4 题 + 预录/esp-tts，演完 | — |
| T+30 s | 后台退避重连（1/2/4/8/15 s）；`sid` 仍可续 | `ping` 30 s 无 `pong` → 标 `ws_close` |
| T+120 s | — | 会话上限，清资源；`/v1/sessions/{sid}` 保留最后状态 |

**接口层对拔网不做任何事**——这是设计意图：断网兜底在设备，上位机不要试图救 Wi-Fi（`工程架构` §6"谁离故障近谁检测"）。

---

## 5. 契约的"不可协商项"（改一条就重测全链路）

| # | 项 | 现值 | 改了必须重测 |
|---|---|---|---|
| 1 | 二进制帧头 | 1 B `type`（0x01/0x02）+ 4 B `seq`(u32 BE) + Opus ≤200 B | 固件编解码、`lost` 统计、fixture 回放三关 |
| 2 | 音频参数交换 | `audio_params{format,sample_rate,channels,frame_duration}`，上行 16 k / 下行 24 k / 60 ms | 重采样、预缓冲帧数、TTFV、声压实测 |
| 3 | 消息名 | `stt`（不是 `asr`）、`abort`（不是 `interrupt`）、`listen{state}`、`tts{state}` | `fw/net/proto.c` 分发、`host/app/proto/schema.py`、CI 三处集合相等 |
| 4 | 错误码集合 | 10 个；`fatal` 只 3xx；1xx/2xx 必带 `degrade` | 三处登记（协议码表 / `errors.h` / `errors.py`）、四类超时降级用例 |
| 5 | `result` 语义 | `house` 四枚举、`reasons` ≤3、`line`、不含 `scores`；判决由代码出 | 判决纯函数单测、反集中、四院分布 ≤40%、灯色映射 |
| 6 | 时间戳 | `t_arm/t0/t1/t2/t3/t4/t5a/t5b`；设备只产生单调时钟，UTC 由服务端补 | 6 时间戳齐全性与 <200 ms 误差、TTFC 口径、JSONL 落库 |
| 7 | 子协议与版本 | `sortinghat.voice.v1`；MAJOR≠1 拒握手，MINOR 不拒 | 握手用例、`protocol_unsupported` 降级路径 |
| 8 | `bye.reason` 枚举 + `sid` 续期窗口 | `done/doff/silence/timeout`；30 s 可续 | 摘下 2 s 收尾、换人 20 秒流程、断网重连用例 |

---

## 6. 明确不做的接口

| 不做 | 为什么 | 我们改成 |
|---|---|---|
| 设备直连 AWS（SigV4/STS） | 设备无 RTC、无安全存储，密钥进固件＝`gitleaks` 直红；跨境多两跳冷连接 +1.5–3.5 s，直接打穿上台线 | 设备只连我们的 WSS；AWS 在服务端背后 |
| 设备上传音频到 S3 | 违反"音频不落盘"的合规承诺；上行是实时流，落盘只会加延迟 | 只走内存流；`stt.text` 存哈希 |
| 设备侧换 token / OAuth refresh | 需要 NTP + 安全存储 + 失效处理，3 天负收益；演示期固定 token 走 NVS 首配 | token 由人换，失败即 `auth_failed` 人介入 |
| 设备 NTP 对时 | 铁律：设备只产生单调时钟，UTC 由服务端补；漂移会把 TTFC 算成负数 | `recv_wall` 回写 + `clock_skew` 错误码 |
| 设备直连 ASR/TTS 厂商 WS | 密钥泄漏 + 无法降级 + 拿不到 `t2/t3/t4`（涂鸦云即此类教训） | 三个 adapter 在服务端，可单跑可替换 |
| 用 IoT Core / MQTT 传音频 | 为小消息设计（单条 ≤128 KB），实时音频在抖动上吃亏 | WSS + 二进制 Opus |
| 设备侧 OTA / 固件下发 | 赛期不 `git pull`；半砖风险高于收益，重刷靠 USB 90 s SOP | 拔插重刷，30 s 换备帽 |
| 下发 `scores` / 判决分数给设备 | `scores` 只用于内部排序与调试，不设备显示、不对外展示 | 设备只收 `house/reasons/line` |

---

## 7. 验收（8 条，curl/脚本即可）

| # | 命令 | 通过判据 |
|---|---|---|
| 1 | `curl -fsS localhost:8080/healthz && curl -fsS localhost:8080/readyz \| jq -e '.providers\|to_entries\|all(.value)'` | 两个 200；`build` 为当日 git7 |
| 2 | `wscat -c wss://host/v1/voice -H "Authorization: Bearer BAD"`；再换正确 token 并计时到 `ready` | 错 token 关闭码 1008/401；正确 token **≤300 ms** 收到 `ready` |
| 3 | `curl -sS -X POST localhost:8080/v1/preheat -d '{"warm":["asr","llm_schema","tts","tls"]}' \| jq .ms` | ≤90 000，且 `readyz.preheat_age_ms` 小于 600 000 |
| 4 | `curl -sS -X POST localhost:8080/v1/replay -d '{"fixture":"fixtures/session-hat01-20261115-2312.ndjson"}' \| jq '.ok and (.diff_ms.max<50)'` | `house` 与记录一致、6 时间戳相对误差 <50 ms |
| 5 | `curl -sS -X POST localhost:8080/v1/config -d '{"version":99,"fault":{"llm":"off"}}'`（`fault` 仅测试环境开关，不进线协议）后跑一次完整会话 | 仍出 `result`；`error.code=="llm_timeout"` 且 `degrade=="template_line"` |
| 6 | `python tools/abort_test.py`（SPEAKING 中发 `abort`，量最后一帧 `0x02` 到静音的时间） | **<300 ms** 无下行帧；会话 `aborted=true` |
| 7 | `iptables -A OUTPUT -p tcp --dport 443 -j DROP`，秒表读灯 | **1.2 s** 转黄（OFFLINE）、**5 s** 内按钮模式能开口；恢复后 `GET /v1/sessions/{sid}` 有 `ws_close` 与 `last_frame_age_ms` |
| 8 | `curl -sS localhost:8080/v1/metrics \| grep -E 'ttfc_ms\{|errors_total'`（10 次会话后） | `ttfc_ms` p50 ≤1.8 s；人为丢 5 帧后 `errors_total{code="bad_frame"}` 有计数且 `sessions_total{result="done"}` 仍增长 |

---

## 8. 与统一准则的冲突/缺口（今日必须决，否则 G2 过不去）

| # | 冲突 | 事实 | 建议 |
|---|---|---|---|
| C1 | 信封键 | 准则用 `t`；xiaozhi 固件按 `type` 分发 | 改 `type`（RFC-001）：路线①不改固件，只是枚举一个大字段名 |
| C2 | `ready` 的名字与 `caps` | 准则 `hello/ready` + `caps`；xiaozhi 双向都叫 `hello`，能力字段叫 `features` | 抽象层保留 `ready`/`caps`，路线①映射为 `{"type":"hello","transport":"websocket"}`，`sid`↔`session_id`、`caps`↔`features` |
| C3 | 无 `bye` 载体 | xiaozhi 无 `bye`；摘帽只表现为关连接 | `abort{reason:"doff"}` 承担收尾语义，`bye` 退化为 close；`doff` 收尾靠服务端推断 |
| C4 | `hello` 超时 | 准则 3 s；xiaozhi 固件默认等 10 s | 服务端一律 ≤300 ms 回；3 s 作验收上限，固件常量**需核实** |
| C5 | camelCase 残留 | `00-protocol` 有 `budgetMs/maxFrameMs/micRate/tailMs/minSpeechMs/latency.asrMs` | 全改 snake_case（`budget_ms`…`latency.asr_ms`）；**与 xiaozhi 一致，反向兼容** |
| C6 | 设备侧 4 个时间戳无载体 | 准则只说"必记"，未说"必报"；DoD 要求 6 时间戳齐全 | 加 `bye.dev_ts`（optional，需 RFC）；缺失则该次标 `incomplete` |
| C7 | 静音超时口径 | `00-protocol` 6.5 s 救场 /15 s `bye`；`工程架构` §4.2 写 12 s | 以 6.5/15 为准，删 12 s |
| C8 | 四院映射 | `00-protocol` 用 `courage/ambition/wisdom/loyalty`；主报告用赤翎/玄渊/星枢/穗垣 | G3 由 `host/persona/houses.yaml` 出映射表，否则 `result.house` 与灯色对不上 |

> xiaozhi 线协议出处：`https://github.com/78/xiaozhi-esp32/blob/main/docs/websocket.md`（本机直取 `api.github.com` contents，`sha d7cdefb4`，2026-11-15）。其中"设备侧 `ping/pong` 帧"与"`bye` 帧"官方文档**未定义**，标注为 `需核实`；如走路线①，二者只能靠 WebSocket 层或 `custom` 帧。
