# 分院帽 · 上位机方案 v1.0
## 功能清单 · 对下位机接口与服务 · 技术选型 · 三天计划

> **生成方式**：双盲两版（甲 / 乙，互不可见）→ 第三人复核 → 本文件合并。
> 原文：`sortinghat/host/blind/input-A.md`（乙）、`input-B.md`（甲）；复核：`sortinghat/host/review.md`；四份角度分析：`sortinghat/host/01~04*.md`。
> 基准：`sortinghat/统一准则-通信协议-仓库施工.md`、`sortinghat/工程架构-上位机下位机硬件.md`、`sortinghat/analysis/00-protocol.md`。
> 冲突时以本文件为准，并在 24 小时内回改基准文档。

---

## 0. 一页纸

**定位：上位机是这顶帽子的导演，不是它的脑子。**
它不产生一个字节的音频，只决定三件事——**什么时候该有声音、说什么、错了怎么办**。三个角色：**编排**（谁先谁后）、**法庭**（`house` 由代码算，不由模型给）、**仪表**（8 个时间戳与 `degrade` 证据）。

**形态：一台笔记本、一个容器、一个进程、两个端口。**

| # | 指标 | 值 | 口径 |
|---|---|---|---|
| K1 | TTFC | 预算 **1.24 s**（上位机段 t1→t4 = **800 ms**）／上台 **1.8 s**／Gate **2.5 s** | 末字→真实内容首字，10 次中位，对外只报这个 |
| K2 | TTFV | **≤0.6 s** | 末字→第一声（预录沉吟） |
| K3 | 首句 | `tts.seg=1` **≤12 字**，且 ≥6 字才送合成 | 决定 TTFC 的一刀 |
| K4 | 判决确定 | 同 fixture 重放 `house` **100% 不变**；引原话通过率 **≥90%**；20 条输入 ≥3 院、任一 ≤40% | 可复现 |
| K5 | 可上台 | `make up`→`/readyz` 绿：**热 ≤90 s、冷 ≤180 s**；单次 **¥0.145** | 钱不是约束，时间才是 |

**三个明确不做**：**不做平台**（K8s/服务网格/多区域/IoT Core/MQTT/OTA）；**不做模型**（不训模型、不把判决交给 LLM）；**不做产品面**（账号/App/小程序/排行榜）。

### 0.1 五个必须现在拍板的裁决

| # | 争点 | 裁决 | 理由 |
|---|---|---|---|
| 1 | **宣布学院那句用预录还是实时 TTS** | **预录 8 句**（4 院 × 2 变体），实时 TTS 只做"引用原话的过桥句" | 这是唯一不能失败的一句：音色必须定版、断网按钮模式也要能宣布；实时合成会让"灯先变色、声后到"，自己破自己的时序规则 |
| 2 | 信封键 `t` 还是 `type` | **线上用 `type`**（对齐 xiaozhi，sha `d7cdefb`）；`t` 只留内部日志 | 走路线①不改固件；改键名等于自建固件 |
| 3 | `recv_wall` 逐帧还是两点 | **逐帧**（t1–t4 每帧打点）；两点插值只作断流兜底 | 断流时两点法误差不可控 |
| 4 | 会话内心跳 15 s 还是 500 ms | **15 s 待机心跳**；**1.2 s 断网检测归设备本地**（上行写失败 + 下行静默） | 15 s 心跳物理上做不到 1.2 s；500 ms 应用 ping 会与"半双工静默"打架 |
| 5 | 预热多久、超时多少 | 六步 fail-closed；**热 ≤90 s / 冷 ≤180 s**；**客户端读超时 150 s** | Bedrock 官方要求读超时 ≥120 s，90 s 会把成功判成超时 |

---

## 1. 功能清单（三层）

**结论：三层共 26 项——必须有 20、可降级 5、不做 1。** 后两类就是缓冲垫。

### 1.1 对设备（它要什么）

| # | 功能 | 判定 | 露馅度（不做会怎样） |
|---|---|---|---|
| D1 | WSS 接入 + Bearer + 子协议 + 版本协商 | 必须有 | **致命**：一句不说 |
| D2 | `ready`（`sid` / 下行参数 / `budget_ms` / `server_time`） | 必须有 | **致命**：预缓冲无从定 |
| D3 | 上行 Opus 消费 + 网关解码（解码不进 adapter） | 必须有 | **致命**：听不见 |
| D4 | ASR 流（partial + final） | 必须有 | **致命**：没文本没分院 |
| D5 | 判决（`argmax` + 反集中 ×0.85 + 引原话 ≤2） | 必须有 | **致命**：没有学院 |
| D6 | TTS 下行 + `tts{start/sentence_start/stop}` | 必须有 | **致命**：帽子不响 |
| D7 | `result`（house/reasons/line，**不含 scores**） | 必须有 | **尴尬**：灯不变色、说不出理由 |
| D8 | 时间基准 + 设备 4 戳回收（`bye.dev_ts`） | 必须有 | **尴尬**：TTFC 报不出 |
| D9 | `error{code,degrade}` | 必须有 | **尴尬**：坏了不知为什么 |
| D10 | 服务端 VAD 兜底 | 可降级 | 设备尾点设错没人纠 |
| D11 | `config` 热调（音量 / `lines_rev`） | 可降级 | **尴尬**：调音量要刷固件 |
| D12 | `bye{reason}` | 可降级 | 无感：关连接也能收尾 |

### 1.2 对内部（我们自己要什么）

| # | 功能 | 判定 | 说明 |
|---|---|---|---|
| I1 | `orchestrator`（会话状态机 + 超时 + 降级） | 必须有 | 一条主线 + 三个投机 |
| I2 | 三个 Provider adapter（ASR/LLM/TTS） | 必须有 | 换供应商 = 改一行配置 |
| I3 | `judge`（纯函数，可单测） | 必须有 | `house` 只在这里产生 |
| I4 | `preheat`（六步，fail-closed） | 必须有 | 没跑过不许上台 |
| I5 | `fixtures` 回放（`host.replay`） | 必须有 | 没设备也能开发与回归 |
| I6 | 观测（8 戳 + degrade + 一行 JSONL） | 必须有 | 大屏与复盘都靠它 |
| I7 | 故障注入开关（`/v1/config` 的测试态 `fault`） | 必须有 | 否则"关掉 LLM 还能演完"无法自动验 |
| I8 | 存储（本地 JSONL + 可选 S3 归档） | 可降级 | 不落盘也不影响演示 |

### 1.3 对人（观众、评委、我们自己）

| # | 功能 | 判定 | 说明 |
|---|---|---|---|
| H1 | 大屏 5 元素（字幕 / 三条理由·原话高亮 / 定格 TTFC / 四院分布 / 揭晓层） | 必须有 | 影响观感与投票 |
| H2 | 分院档案页（扫码） | 可降级 | 同时是合规告知二维码的落点，建议回 E 2 h 单文件版 |
| H3 | `halt`（停新 / 强制预设 / 全停） | 必须有 | 现场唯一"刹车" |
| H4 | prompt 与四院权重热更新（会话边界生效 + 回滚） | 必须有 | 不重启发版 |
| H5 | 错误率与 20 词黑名单 | 必须有 | 现场发现问题 |
| H6 | 日报（5 个数） | 可降级 | 主讲每天看 |
| H7 | A/B 面板、权限体系、排行榜 | 不做 | 3 天里纯负收益 |

---

## 2. 对下位机的接口与服务

### 2.1 设备的最小硬依赖（只有 5 条）

> 走路线①（xiaozhi 固件）时，设备**只硬依赖**下面 5 条；其余全是可选。没有这 5 条，帽子一句不说。

| # | 依赖 | 缺了会怎样 |
|---|---|---|
| 1 | WSS 握手 + Bearer + 子协议 | 连不上 |
| 2 | `hello → ready`（`sid`/下行参数/`budget_ms`） | 预缓冲与超时无从定 |
| 3 | `listen{start}` 被受理 | 不进 LISTENING |
| 4 | 上行 Opus 被消费（不要求逐帧 ACK） | ASR 无输入 |
| 5 | 下行 Opus + `tts{start/stop}` | 帽子不响 |

`result` / `error` / `bye` / `config` / 服务端 VAD 在**协议上可选**，但 `result` 在**舞台上按必需对待**（灯色与理由都靠它）。

### 2.2 接口全表

| # | 接口 | 方向 | 触发 | 载荷要点 | 超时 | 幂等 | 失败处理 | 错误码 |
|---|---|---|---|---|---|---|---|---|
| 1 | `WSS /v1/voice` | 设备→云 | 上电/重连 | `Authorization: Bearer`、`Sec-WebSocket-Protocol: sortinghat.voice.v1`、`Protocol-Version` | 5 s | — | 退避重连 1/2/4/8/15 s | `auth_failed` |
| 2 | `hello` | 设备→云 | 连接后 | `caps`（aec/micRate/spkRate/vad）、`fw`、`boot_id`、`ts_mono` | — | 幂等 | 服务端 300 ms 内回 `ready` | `protocol_unsupported` |
| 3 | `ready` | 云→设备 | 收到 hello | `sid`、`audio{in,out}`、`budget_ms`、`server_time`、`vad` 参数 | 300 ms | 同 sid 可重发 | 设备无 `ready` 3 s → 重连 | — |
| 4 | `listen{start/stop/detect}` | 设备→云 | 戴上/按钮/唤醒 | `mode`、`ts_mono` | 5 s 受理 | 设备重发同 `start` 不重复计会话 | 无响应 → 回 ARMED 并闪灯 | `bad_frame` |
| 5 | 上行 Opus 帧 `0x01` | 设备→云 | 60 ms/帧 | `seq` + Opus | — | 不重传 | 跳号 >10 记 `bad_frame` | `bad_frame` |
| 6 | `vad{speech_start/end}` | 双向 | 起振/尾点 | `ev`、`dur_ms` | — | — | 不一致取"更早 start + 更晚 end" | — |
| 7 | `stt{partial/final}` | 云→设备 | 流式 | `text`、`lang` | 600 ms（软） | — | 用稳定 partial 当 final | `asr_timeout` |
| 8 | `llm{delta}` | 云→设备 | 可选 | `text` | 900 ms（软） | — | 模板首句 | `llm_timeout` |
| 9 | `tts{start/sentence_start/stop}` | 云→设备 | 合成开始/句界/结束 | `seg`、`text`（字幕） | 800 ms 首包 | — | 预录音色兜底 | `tts_timeout` |
| 10 | 下行 Opus 帧 `0x02` | 云→设备 | 60 ms/帧 | `seq` + Opus | — | 不重传 | 设备抖动缓冲；丢帧静默 | — |
| 11 | `result{house,reasons,line,latency}` | 云→设备 | 判决完成 | `house` 四值枚举、`reasons[3]` 必引原话、`latency{...}` | 与宣布句同批 **≤100 ms** | 同 `msg_id` 只播一次 | 缺失 → 只播 TTS、灯沿用上一院色 | — |
| 12 | `error{code,degrade,fatal}` | 云→设备 | 异常 | 1xx/2xx 必带 `degrade`；`fatal` 只在 3xx | — | — | 设备记日志并继续 | 见准则 §3.3 |
| 13 | `bye{reason,dev_ts}` | 双向 | 结束 | `done/doff/silence/timeout`；`dev_ts{t_arm,t0,t5a,t5b}` | — | 幂等 | 关连接兜底 | — |
| 14 | `config{...}` | 云→设备 | 运营改参 | `volume`、`lines_rev`、阈值；**仅在会话边界生效** | 5 s | 按 `rev` 幂等 | 失败保留旧值并告警 | `bad_frame` |
| 15 | `ping/pong` | 双向 | 15 s 待机 | — | 30 s 无 pong 重连 | — | 会话内不断连即可 | — |

### 2.3 管理面 API（只给人/工具，不给设备）

全部挂 `X-Admin-Token`；代理只把 `/v1/voice` 暴露给设备，其余只绑回环。

| 方法 | 路径 | 用途 | 谁调 |
|---|---|---|---|
| GET | `/healthz` | 进程活着 | Docker/人 |
| GET | `/readyz` | 依赖全通（ASR/LLM/TTS/预录/配置） | `make ready` |
| POST | `/v1/preheat` | 六步预热（fail-closed，读超时 150 s） | 开场前 |
| POST | `/v1/replay` | 用 fixture 回放一次会话 | 回归/无设备开发 |
| GET | `/v1/sessions/{sid}` | 查一次会话的 8 戳与降级路径 | 排障 |
| GET | `/v1/metrics` | Prometheus 文本格式（或 JSON） | `make watch` |
| GET | `/stats` | 大屏用的一行 JSON | 大屏 |
| POST | `/v1/config` | 热更新 prompt/权重/音量；测试态 `fault` 注入 | 运营/彩排 |
| POST | `/v1/halt` | `halt_new` / `force_preset` / `stop_all` | 现场刹车 |

### 2.4 一次正常会话的时序（t0 = 观众末字）

```
t0    设备 vad{speech_end} → 网关收到末帧（t1 = t0 + 60 ms）
      ↓ 同时：设备立刻播预录沉吟（TTFV ≈ 0.4 s）
t1+20ms   ASR final（t2 = t1 + 200 ms）
t2+350ms  LLM 首 token（t3）
t2+…      代码判决：argmax + 反集中 + 引原话校验
t3+250ms  TTS 首包（t4）→ 下行 Opus
t4+80ms   设备首帧播放（t5b）→ TTFC ≈ 1.24 s
      ↓ 宣布句：预录音频 + result 同批下发（≤100 ms）
t0+90s    bye{done, dev_ts} → 落一行 JSONL
```

### 2.5 三个异常时序

| 异常 | 谁发现 | 动作 | 观众感知 |
|---|---|---|---|
| ASR 超时 | 网关（600 ms 软阈值） | 用稳定 partial 当 final；再无则发提示句 TTS | 「我没听清，再说一次？」 |
| 设备打断 | 设备发 `abort` | 网关取消 LLM/TTS、丢弃下行；本地静音优先 | 立刻安静，灯转青 |
| 拔网 | **设备本地**（上行写失败 + 下行静默） | 1.2 s 内进 OFFLINE，5 s 内按钮模式就绪 | 灯转黄，帽子换方式继续 |

---

## 3. 技术选型

### 3.1 决策矩阵（加权：3 天做成 30 / 延迟 25 / 可控 20 / 成本 15 / 工程叙事 10）

| 方案 | 加权 | 判定 |
|---|---|---|
| **笔记本本地网关（Docker Compose 单容器）+ 模型走云** | **4.80** | **唯一上台形态** |
| EC2 t4g.small（同镜像） | 3.95 | 热备 / 路演 |
| Fargate + ALB | 3.05 | ❌ 比 EC2 贵 2.4 倍，演示期零收益 |
| API GW WebSocket + Lambda | 2.60 | ❌ 有状态长连接反模式 |
| 自建 EMQX / MQTT | 2.35 | ❌ 协议已冻 WSS，换 MQTT 要动固件 |

> 关键判断：本项目不存在"本地 vs 云"的选择——**三个模型本来就是 SaaS**，唯一变量是**网关进程跑在哪**。网关在笔记本，= 延迟最低、断网可控、¥0。

### 3.2 具体选型

| 层 | 选型 | 理由 | 备选 |
|---|---|---|---|
| 语言/运行时 | **Python 3.12**（asyncio + uvloop） | 一门语言覆盖网关/脚本/pytest；AWS 与阿里 SDK 都最全 | Node（WS 更顺，但脚本生态弱） |
| 设备面 | **`websockets`** 库，二进制帧 + 文本 JSON | 低开销、可控背压（`max_queue`） | FastAPI WebSocket（人面用） |
| 人面 | **FastAPI**（HTTP + SSE） | 大屏/档案/管理面 | htmx 直接返回 HTML |
| 进程 | **1 容器 / 1 进程 / N 个 asyncio 任务** | 3 天里每多一个进程，就多一处 22:30 要修的东西 | — |
| 端口 | **8443 WSS（设备面，0.0.0.0）/ 8080 HTTP（人面，127.0.0.1）** | 两个面两个口，大屏不对外 | — |
| 容器 | docker compose + `restart: unless-stopped` | 一条命令起，崩溃自拉 | systemd |
| 存储 | **本地 JSONL**（一行一会话）+ 可选 S3 归档 | 演示不需要数据库 | DynamoDB（赛后） |
| 观测 | structlog JSONL + `/metrics` + `/stats` | 不装 Prometheus 全家桶 | CloudWatch（上云后） |
| 前端 | 单文件 HTML + 内联 CSS + 原生 JS + SSE | 零构建、零 CDN、断网可用 | htmx（16 KB） |
| 二维码 | segno（纯 Python，无依赖，内联 SVG） | 现场可离线生成 | qrcode |

### 3.3 部署与成本

| 形态 | 用途 | 成本 |
|---|---|---|
| 笔记本 + 手机热点 | **上台** | ¥0 |
| EC2 t4g.small（东京） | 热备/路演 | $0.0216/h；演示期 ≈$0.4 |
| 云模型（Transcribe/Bedrock/TTS） | 主链路 | ¥0.145/会话；100 次 ¥10–15 |
| **演示 3 天合计** | | **≈¥18–76** |
| **赛后常驻 1 月** | | **≈$43 ≈ ¥305**（EC2 730 h + 1000 次会话 + 日志） |

---

## 4. 编排与降级

### 4.1 Provider 契约（一种形状，三个实现）

```python
class Provider(Protocol):
    async def open(self, sid: str, cfg: dict) -> AsyncIterator[Event]: ...
    async def push(self, chunk: bytes | str) -> None: ...   # 音频块或文本
    async def abort(self) -> None: ...                      # cancel ≤50 ms，幂等，不抛
    async def health(self) -> bool: ...
    async def warmup(self) -> None: ...
```

- 统一 `Event{kind, sid, seg, t_ms, text, pcm, code, retryable}`；`kind ∈ partial/final/audio/done/error`。
- **adapter 只做协议转换与错误归一**（未知错误统一塌成 `upstream_5xx`）；重试与降级归 orchestrator。
- 换供应商 = `providers.yaml` 一行 + `caps` 驱动；**编排代码里禁止 `if vendor == ...`**。
- **ASR 吃 PCM**：Opus 解码放网关，不放 adapter（adapter 不碰设备格式）。

### 4.2 时序预算（与主报告 1.24 s 对齐）

| 段 | 预算 | 手段 |
|---|---|---|
| VAD 尾点 | 300 ms | 设备侧；按钮强制结束 = 0 |
| 上行 | 60 ms | 60 ms 帧 + 常连接 |
| ASR 尾字 | 200 ms | 流式；**投机启动**：稳定 partial 先喂 LLM |
| LLM 首 token | 350 ms | prompt ≤300 token；关思考；**prompt 缓存**（前缀 ≥600 token 才开） |
| TTS 首包 | 250 ms | 流式；首句 ≤12 字 |
| 下行 + 播放 | 80 ms | 预缓冲 1 帧 |
| **合计** | **1.24 s** | 上位机段 = t1→t4 = **800 ms** |

### 4.3 九格降级矩阵

| 故障 | 检测 | 退到哪 | 观众听到什么 |
|---|---|---|---|
| ASR 超时 | 600 ms 无 final | 稳定 partial 当 final | 正常，可能少半句 |
| ASR 5xx | 一次重试失败 | 同上 | 同上 |
| ASR 限流 | 429 | 同上 + 降采样率 | 同上 |
| LLM 首 token 超时 | 900 ms | **预合成模板首句（同音色）** | 「唔……让我看看。」 |
| LLM 结构化失败 | schema 校验 | 重试 1 次 → 兜底打分 | 理由变通用，仍宣布 |
| LLM 内容拦截 | 安全层 | 安全话术 + 兜底打分 | 「这个帽子不管。」 |
| TTS 首包超时 | 800 ms | **预录音色片段** | 音色不变，语气略平 |
| TTS 连接断 | 断连事件 | 预录宣布句 + Polly 过桥（**Polly 绝不宣布学院**） | 可能换女声，但学院仍宣布 |
| 断网 | 设备本地 | 按钮模式 + esp-tts | 灯转黄，帽子继续 |

### 4.4 宣布句：预录，不合成

- **8 句预录**（4 院 × 2 变体），Opus 16 kbps，共 <20 KB，与 TTS 同一音色一次性合成后固化。
- 与 `result` **同批下发（≤100 ms）**，保证"灯变色"和"宣布"是同一件事。
- 断网按钮模式复用同一批预录。

### 4.5 预热六步（fail-closed）

| # | 步骤 | 失败判据 |
|---|---|---|
| 1 | 载入配置与 persona | 文件缺失/校验不符 |
| 2 | ASR 试连（1 s 静音） | 2 s 无响应 |
| 3 | **Bedrock 结构化输出**（打真 schema，**读超时 150 s**） | 报错或超时 |
| 4 | TTS 建会话并合成首句（校验时长 >0） | 800 ms 无首包 |
| 5 | 载入 8 句预录并校验 sha256 | 校验不符 |
| 6 | 自检 `/readyz` + 写 `preheat.json` | 任一步红 → readyz 红，**禁止上台** |

> 两个坑：**"Schema is too complex"也要等约 90 s 才报**（所以预热要打真 schema）；**Anthropic prompt cache 最小 512 token**，我们 300 字 prompt 命中不了——前缀做不到 600–700 token 就明确写"不启用"。

---

## 5. 加分项：真用 vs 硬凑

| 项 | 真实用法 | 留证 | 工时 | 判断 |
|---|---|---|---|---|
| **AWS** | Transcribe（ASR）+ Bedrock（主判官 + 结构化输出）+ Polly（过桥兜底）+ CloudWatch（日志/指标）+ S3（归档，可选） | 控制台截图、调用日志、架构图 | **0**（主链路本就在跑） | **必做** |
| **Kiro** | 把 Provider 契约与故障注入写成 spec，生成 adapter 骨架与契约测试；**禁止**生成 `judge/` 与 `persona/prompt.md` | `.kiro/specs/*/{requirements,design,tasks}.md` 入库 + 每 task 一 commit（`Refs: G2`）+ `reports/*.md` | **4 h** | **做** |
| **NVIDIA Nemotron** | **只做离线第二判官**：20 条输入 A/B，报裸一致率 + Cohen's κ；**不进热路径** | 对照表 + κ 计算脚本输出 | **2 h** | **做（离线）**；在线分支删除 |
| **TuyaOpen / 涂鸦云** | 只留评估笔记；本期不接 | `docs/eval/tuya.md` + 五条前置条件 | **0.5 h** | **不接** |

**四种"硬凑即扣分"**：① 为加分搬 Fargate（多 8–10 h、贵 2.4 倍）；② 换 TuyaOpen 固件栈（4 h、与 G3 撞车）；③ 把 Nemotron 放进主判决（双倍 token、抢配额、多一次 90 s 预热）；④ 用 Kiro 生成判决代码（判决必须人写、可单测）。

**给评委的一句话**：
> "开发期 Kiro 把 spec 变成代码与契约测试；运行时 AWS 负责听、想、说，Nemotron 在离线做第二判官的一致性对照；帽子里只有一颗 ESP32-S3——它负责听、传、放，不负责思考。"

---

## 6. 三天计划与验收（B：27.5 人时）

| 时段 | 工时 | 交付 | Gate |
|---|---|---|---|
| 11/15 晚 | 5 | 网关骨架 + `hello/ready` + echo + `/healthz` | **G2**：帽子听得见（设备侧配合） |
| 11/16 白天碎片 + 晚 | 8 | ASR + LLM + TTS 三 adapter + 端到端 + `replay` | 真机一条数据落库、TTFC 中位 ≤2.5 s |
| 11/17 白天 | 4 | 降级九格 + judge + 观测 + 大屏 `/stats` | 四类超时各演示一次 |
| 11/17 晚 | 6 | 预热六步 + 档案页 + halt + 日报 | **G5**：提交 v1 |
| 缓冲 | 4.5 | 彩排问题修复 | G8 彩排通过 |
| **合计** | **27.5** | | |

### 8 条可执行验收

| # | 验收 | 命令/判据 |
|---|---|---|
| 1 | 进程与依赖 | `curl -s localhost:8080/healthz` → 200；`/readyz` → `{"ok":true}` |
| 2 | 预热 | `curl -XPOST -H 'X-Admin-Token:…' localhost:8080/v1/preheat` → 200 且 ≤180 s |
| 3 | 回放 | `POST /v1/replay` 三条 fixture → `house` 与 8 戳与基线一致 |
| 4 | 端到端 | 真机 10 次，TTFC 中位 ≤1.8 s、`degrade` 为空 |
| 5 | 降级 | `/v1/config` 打开 `fault` 分别杀 ASR/LLM/TTS → 三条降级各命中一次 |
| 6 | 断网 | 拔网 → 设备 1.2 s 检测、5 s 按钮模式就绪 |
| 7 | 刹车 | `POST /v1/halt` → 新会话拒接、在途会话收到 `bye{timeout}` |
| 8 | 泄漏 | 连跑 10 次后 RSS 增幅 <20%、无文件句柄泄漏 |

---

## 7. 风险与单点

| # | 风险 | 概率 | 影响 | 兜底 |
|---|---|---|---|---|
| 1 | 手机热点 + 防火墙使设备连不上 8443 | 高 | 致命 | 开场前 10 分钟用设备实连一次；备用热点；EC2 第二端点写进 NVS |
| 2 | 没预热就上台 | 中 | 高 | `make ready` 绿灯才允许讲；预热写 `preheat.json` 带时间戳 |
| 3 | **TTS 音色单点**（兜底会换"帽子是谁"） | 中 | 高 | 8 句预录 + 同音色模板句；Polly 只过桥不宣布 |
| 4 | 笔记本睡眠/断电 | 中 | 致命 | 电源常插、禁睡眠、第二台同镜像 |
| 5 | 密钥/配额/限流 | 中 | 中 | 预充值 + 备用 key + 429 退避 |
| 6 | **人单点**（只有 B 会起服务） | 中 | 高 | `make up` 一条命令 + `docs/sop/host.md` 90 秒；C 独立跑过一次 |

---

## 8. 与统一准则 / 架构的冲突裁决

| # | 冲突 | 裁决 | 回改哪里 |
|---|---|---|---|
| 1 | 信封键 `t` vs `type` | **线上 `type`**，内部日志 `t` | 准则 §3.1 加一行"线上键名以路线①为准" |
| 2 | 架构 §4.2 "12 s 无声 → 提示句" | **删**，改 **6.5 s 救场 / 15 s bye** | 已改架构 §4.2 |
| 3 | 甲版"五态" | **六态**（OFF/ARMED/LISTENING/THINKING/SPEAKING/ERROR） | 已对齐准则 §7.5 |
| 4 | `bye` 单向 / `dev_ts` 可选 | **双向 + `dev_ts` 必填**（否则 TTFC 报不出） | 准则 §3.6 表补 |
| 5 | 心跳 500 ms 应用 ping | **删**；15 s 待机 + 设备本地 1.2 s 检测 | 准则 §3.6 |
| 6 | 预热 90 s 全绿 | **热 ≤90 / 冷 ≤180**，读超时 **150 s** | 本文 §4.5 |

---

## 附录 A：8 个时间戳

| 戳 | 产生方 | 含义 |
|---|---|---|
| `t_arm` | 设备 | 戴上（ARMED） |
| `t0` | 设备 | 观众末字（speech_end） |
| `t1` | 网关 | 收到末帧 |
| `t2` | 网关 | ASR final |
| `t3` | 网关 | LLM 首 token |
| `t4` | 网关 | TTS 首包 |
| `t5a` | 设备 | 沉吟首帧 |
| `t5b` | 设备 | 真实内容首帧 |

`TTFV = t5a − t0`；`TTFC = t5b − t0`；对账差 >200 ms 本次作废，>500 ms 记 `clock_skew`。

## 附录 B：环境变量（6 组 44 键）

| 组 | 键（示例） |
|---|---|
| 服务 | `HOST_PORT`、`WS_PORT`、`ADMIN_TOKEN`、`LOG_LEVEL` |
| AWS | `AWS_REGION`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`、`BEDROCK_MODEL_ID`、`BEDROCK_REGION` |
| ASR | `ASR_PROVIDER`、`ASR_LANG`、`ASR_SAMPLE_RATE`、`ASR_TIMEOUT_MS` |
| LLM | `LLM_PROVIDER`、`LLM_MAX_TOKENS`、`LLM_TIMEOUT_MS`、`NEMOTRON_ENABLED` |
| TTS | `TTS_PROVIDER`、`TTS_VOICE_ID`、`TTS_TIMEOUT_MS`、`PREROLL_DIR` |
| 业务 | `HOUSE_WEIGHTS`、`RECENT3_PENALTY`、`MAX_SHARE`、`SILENCE_MS`、`SESSION_MAX_MS` |

## 附录 C：三条不能丢

1. **判决权不进模型**：`house = argmax(scores)` + 连续 3 次同院 ×0.85 + 引原话校验（编辑距离 ≤2）。
2. **宣布只许预录**，且 `result` / `tts{start}` / 首帧同刻（≤100 ms）。
3. **一份账本一条时间轴**：`sid + last_msg_id` 幂等，8 戳齐全，>200 ms 作废、>500 ms 记 `clock_skew`。
