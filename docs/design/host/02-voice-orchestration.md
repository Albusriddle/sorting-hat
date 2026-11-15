# 02 · 语音 / AI 编排层与供应商适配（上位机评审 · B 组）

> 依据：`统一准则-通信协议-仓库施工.md`（下称「准则」）、`analysis/03-cloud.md`、`SORTINGHAT-可行性与实施方案.md` §7–§8、`工程架构-上位机下位机硬件.md` §4。
> 核对方式：本会话 `web_search` 仍 401，以下标「官方」处均用 `curl` / `web_fetch` 直取页面。价格沿用 `03-cloud.md` 已核实值，汇率 ¥7.1/$ 是**假设**。
> 与准则冲突一律以准则为准：**判决 house 由代码 `argmax(scores)` + 反集中 ×0.85 + 引原话校验（编辑距离 ≤2）产出**，本文件不重定义，只引用。

---

## 0. 一页纸

| # | 结论 | 落在哪节 |
|---|---|---|
| 1 | 三个 adapter 共用一个 `Provider` 契约：**三个动词 `open` / `push` / `abort`，两个附属 `health` / `warmup`**；业务代码只认事件与错误码，换供应商改一行配置 | §1 |
| 2 | 首句不靠「等完整 JSON」：`hook` 字段排 schema 第一位，网关流式切句，首句一到就 `push` 给 TTS；宣布句严格等 judge | §2 |
| 3 | 降级第一原则：**已收到的 partial 就是结果**（ASR）、**已预热的模板句就是内容**（LLM）、**已预录的 8 句就是音色**（TTS）。三处都不「等」 | §3 |
| 4 | 预热里唯一能打穿演示的是 **Bedrock schema 首编译（官方：最长约 90 s，缓存 24 h）**；prompt cache 有 **512 token 下限**，我们 300 字 prompt 大概率命中不了 | §4 |
| 5 | Nemotron 只在「低置信 + 预算有余」时在线，**永不阻塞宣布**；主力产出是离线抽样一致性率 | §5 |
| 6 | 涂鸦 / TuyaOpen **本期不接**（拿不到 t2/t3/t4 就没有 TTFC），只留评估笔记 | §7 |

---

## 1. 三个 adapter 的统一 Provider 契约

**结论**：一种契约、三种 `TIn/TOut`、一套事件与错误码。adapter 内**只准做协议转换 + 错误归类**，重试与降级由 orchestrator 决策——否则三个 provider 会各自长出一套超时，降级矩阵就不可测了。

```python
# host/providers/base.py（伪代码，仅签名）
class Caps(TypedDict):
    streaming_in: bool; streaming_out: bool; cancel: bool
    accept: Literal["pcm16k", "text", "sentence"]
    emit:   Literal["partial", "token", "sentence", "audio"]
    max_inflight: int

class Event(TypedDict):                       # 唯一出口，三 provider 共用
    kind: Literal["partial","final","token","sentence","audio","done","error"]
    sid: str; seg: int; t_ms: int             # t_ms = 本机单调时钟
    text: str | None; pcm: bytes | None
    code: ErrorCode | None; retryable: bool; vendor: dict

class Provider(Protocol):
    name: str; caps: Caps
    async def open(self, ctx: TurnCtx) -> str                  # 返回 sid；优先复用连接池里的热连接
    async def push(self, sid: str, item: TIn) -> None          # 流式入；不返回结果
    def events(self, sid: str) -> AsyncIterator[Event]         # 流式出
    async def abort(self, sid: str, why: str) -> None          # 取消：幂等、≤50 ms、不抛异常
    async def health(self) -> Health                           # 读缓存 + 可选 1-token 探针
    async def warmup(self) -> WarmReport                        # 只给 make preheat 用
```

| 项 | ASR | LLM | TTS |
|---|---|---|---|
| 实现 | Transcribe Streaming（zh-CN，东京） | Bedrock Claude Haiku 5.5（`anthropic.claude-haiku-5-5`，结构化输出） | CosyVoice-v3.5-flash（北京）/ v3-flash（新加坡） |
| `push` 的 item | **16 kHz/16 bit PCM 帧（60 ms）**；Opus 解码放网关，不放 adapter | 整段 text（final，或投机用的 stable 前缀） | 一句 text（≥6 字，`seg` 单调递增） |
| `events` 出什么 | `partial`（带 `Stable`）/ `final` | `token` / `done` | `sentence`（音频块，天然对应一句） / `done` |
| 取消怎么做 | close 上行输入流 | abort 流式响应 | `finish-task` 或断流 |
| 官方硬约束 | `IsPartial`/`Stable`/`ResultId` 是官方字段；稳定度用 `PartialResultsStability=low\|medium\|high` | 每个 object 必须显式 `additionalProperties:false`；**不支持** `minLength`/`maximum`；可选属性 ≤12、union ≤16；不合规 schema 立即 400 | WS 时序 `run-task → task-started → continue-task×N → result-generated → finish-task → task-finished`；**连接必须跨任务复用**；`enable_ssml=true` 时只许一条 `continue-task` |
| 超时 | final 600 ms | 首 token 900 ms / 结构化完成 1500 ms | 首包 800 ms |

**热切换五步（不改业务代码）**：

1. `host/providers/providers.yaml` 一行 `asr: transcribe | funasr | tuya`，启动时按名构造。
2. `caps` 驱动编排：`streaming_out=false` 的 provider 自动退化成整句模式，编排代码里没有 `if vendor ==`。
3. 错误归一：adapter 只准抛 `ProviderError(code, retryable, vendor)`，`code` ∈ 准则 §3.3 的 7+3 集合，未知错误塌成 `upstream_5xx`；**每格降级必须在 `error` 帧带 `degrade` 字段**（准则 §3.3）。
4. `health()` 走 1-token / 1 字探针，失败不重试、只降级——它服务于 `make preheat` 与 30 s 巡检，不进主链路。
5. `MODE=cassette` 录/放 `providers/cassettes/*.jsonl`，与准则 §3.5 的 fixture **同一条 code path**：换供应商先过 cassette 回归，`house` 不许变。

---

## 2. 编排状态机：`speech_end` → `tts start`

**结论**：一条主线 + 三个投机。主线只等「能出声的最小单位」（`hook` 首句），不等完整 JSON；宣布句严格串在 judge 之后。**首句永不等判决**，判决永不等首句。

状态串：`LISTENING → FINALIZING(等 final) → DRAFTING(→首句 TTS) → SPEAKING → ANNOUNCING → CLOSING`。三个投机：① stable partial 预跑 LLM；② `hook` 一到就送 TTS；③ judge 一完成就合成宣布句。

| # | 相对 t0（观众末字） | 动作 | 并发/先后 | 预算 | 超时 | 失败去向 |
|---|---|---|---|---|---|---|
| 1 | −1200 → 0 | 设备播预录沉吟 | 与上行并行 | 1200 | — | 本地文件，无网络 |
| 2 | 0 → 300 | VAD 尾点（设备侧） | 主线 | **300** | 500 | 按钮「我说完了」/ 300 ms 硬切 |
| 3 | 300 → 360 | 上行尾帧到 t1 | 主线 | **60** | 200 | 丢帧不补 |
| 4 | ≤0 | stable partial → LLM 开跑 | **投机**，可 abort | — | — | 与 final 差 >2 字 → abort 重发 |
| 5 | 360 → 560 | ASR final（t2） | 主线 | **200** | 600 | partial-as-final |
| 6 | 560 → 910 | LLM 首 token（t3）+ `hook` 切句 | 主线 | **350** | 900 | 模板首句 |
| 7 | 910 → 1160 | TTS 首包（t4），`hook` ≤12 字 | 与 LLM 后续 token **并行** | **250** | 800 | 重发 1 次 → Polly → 预录 |
| 8 | 1160 → 1240 | 下行首帧入队 | — | **80** | — | 降采样不降时序 |
| 9 | **1240** | **TTFC = t5b − t0** | — | **1240** | 上台 1800 / Gate 2500 | — |
| 10 | 910 → 2410 | judge 完成（scores/evidence） | 与播放并行 | 1500 | 2000 | 兜底打分 |
| 11 | 2410 → 2660 | 宣布句 TTS 首包 | **串行**在 judge 后 | 250 | 800 | 预录宣布 8 句 |
| 12 | 至 90 s | 收尾 | — | — | 硬超 | 强制收尾句 |

**八条并发纪律**：

1. 沉吟永不等网络；它把 TTFV 钉在 0.4 s，与 TTFC 无关。
2. 投机入场券：`Stable=true` 前缀 ≥8 字、且 400 ms 未变；不满足就不投（省一次调用，也省 abort）。
3. 投机与 final 的比对用编辑距离 ≤2（同引原话校验阈值）；超了 abort，成本约 $0.0002，可接受。
4. 切句在网关做：流式扫描 JSON 里 `hook` 的值，遇 `。！？…` 即切；**≥6 字才送 TTS**，避免「唔。」单起一次合成。
5. `hook` 与 `line` 分别起 TTS task（两个 `seg`），**不合并不缓冲**——宣布句必须独占缓冲，否则尾字被前段挤掉。
6. 宣布句置 `is_announcement=true`：固定音量/语速，不继承前段 `rate`/`pitch`。
7. `abort` 顺序：TTS（先静音）→ LLM → ASR 上行 close；设备侧 `abort` 优先本地静音（准则 §3.6）。
8. 幂等键 `sid + seg`；重连只重发当前 `seg`，设备按 seg 去重。

---

## 3. 降级矩阵（本文件的核心）

**结论**：每一格只问三件事——**怎么发现、退到哪、观众听到什么**。「观众听到」列是验收口径，不是文学描述：写不出这一句的功能不许上。

### 3.1 ASR

| 故障格 | 检测 | 降级动作 | 观众听到什么 | 错误码 |
|---|---|---|---|---|
| 超时（600 ms 无 final） | 计时器 + 最后 partial 时间 | 最后一个 `Stable` 前缀 ≥8 字 → **当 final 用**直送 LLM；否则播提示句、回 ARMED 允许重说 | 前者：正常被分；后者：「唔……帽子老了，耳朵不灵，再说一遍？」（预录，不依赖 TTS） | `asr_timeout` |
| 5xx / 流异常关闭 | HTTP 5xx、连接异常 | 有 partial → 当 final；无 partial → 3 s 环形缓冲重放一次到备 provider（fun-asr），+400 ms；仍败 → 提示句 | 多数正常；最坏听到提示句，**不会静默** | `upstream_5xx` |
| 限流（429） | 429 / `rate limit` 串 | **不退避等待**（观众等不起）：立刻走 partial-as-final；60 s 内新会话优先备 provider | 正常或提示句 | `rate_limited` |
| 空结果 / 只有标点 | `strip()` 后 <2 字 | 视为「没听清」，不计入 15 s 静音计时 | 提示句 | `asr_timeout` |

### 3.2 LLM

| 故障格 | 检测 | 降级动作 | 观众听到什么 | 错误码 |
|---|---|---|---|---|
| 首 token 超时（900 ms） | 计时器 | 播**已预合成的模板首句**（「唔……让我看看。」，本地文件 0 ms）；judge 继续等，等到就用 | 音色正常、语气正常，只是那句是预录 | `llm_timeout` |
| 结构化输出失败 | 400 ValidationException / JSON 解析失败 / 缺字段 | 400 分两种：不支持的特性**立即** 400（schema 写错，直接修）；「Schema is too complex」要等编译**约 90 s** 才报。运行期解析失败 → 切「宽松模式」（纯 prompt + 本地 JSON 修复）一次 → 降温重试 1 次 → 兜底打分 | 正常 | `upstream_5xx`（另记 `anomaly:schema_invalid`） |
| 内容安全拦截 | `stop_reason=refusal`、guardrail intervened、输出命中黑名单 | 安全人格句（预录）：「帽子今天不谈这个。」+ 一句关怀 + 换一个具体问题给第二次机会；再触发 → 收尾回 ARMED，**不算失败** | 角色化拒绝，不出戏 | 无 error 帧（记 `anomaly:safety_stop`） |
| 引原话校验不过（编辑距离 >2） | `judge.validate` | 重试 1 次 → 仍不过：用 `evidence` 最长一条拼模板「你说『…』——这句我记下了。」 | 理由变通用，但**仍宣布学院** | 无 error 帧（记 `anomaly:quote_fail`，与 `04-console-ops.md` 的错误分类同名） |
| 限流 / 长时间 5xx | 429 / 连续 5xx | 切 Nova Lite 同区（**它也要单独预热 schema**，见 §4）；仍败 → 兜底打分（本地关键词表 5 题 + 8 句预录） | 学院仍出，理由模板化 | `rate_limited` |

### 3.3 TTS

| 故障格 | 检测 | 降级动作 | 观众听到什么 | 错误码 |
|---|---|---|---|---|
| 首包超时（800 ms） | 计时器 | ① 同一连接重发该句 1 次（`continue-task`）→ ② 切 Polly Neural Zhiyu → ③ 播预录句 | ①几乎无感；②音色变女声播报（可听出换人）；③预录音色 | `tts_timeout` |
| 音色不可用 | `task-failed` 的 `error_message` / 400 | 回退到**不带 instruction 的基底音色 id**（同一音色家族），不行再 Polly | 语气变平，但仍是男声，不跳女声（Polly 之前先试基底） | `upstream_5xx` |
| 连接断（close/1006） | `onclose` | 连接池双热备：重连（200–400 ms）→ 重发**当前句**（幂等靠 `seg`）；2 次失败 → 预录 | 半句后停 0.3–1 s 再续——帽子本来就慢，可接受 | `tts_timeout` |
| 限流（`Requests rate limit exceeded`） | 错误串 | 单帽并发恒为 1，不降并发；直接切 Polly | 音色变 | `rate_limited` |
| 宣布句失败 | 同首包超时 | **只许预录**：按 house 播 8 句里的对应句；不许用 Polly（女声宣布学院会毁掉高潮） | 预录音色 + 学院正确 | `tts_timeout` |

> 最要紧的三条：**ASR 用 partial 当结果**、**LLM 用预合成模板首句**、**宣布句只许预录**。

---

## 4. 预热清单与 `make preheat`

**结论**：预热的唯一目的不是省钱，是把「第一次会慢 / 第一次会 400」的五件事（DNS/TLS、schema 编译、prompt cache、TTS 连接与音色、ASR 连接）挪到开场前。冷跑约 95 s（schema 编译主导），热跑约 4 s；**任一项失败 `exit 1`，舞台不上**。

| # | 步骤 | 做什么 | 预期耗时（冷 / 热） | 失败判据 |
|---|---|---|---|---|
| 1 | DNS/TLS 常连接 | 三个端点建连并保活（心跳 15 s） | 0.8–1.8 s（本机实测冷 TLS 0.78–1.76 s）/ <20 ms | 任一 >2 s |
| 2 | Bedrock schema 首编译 | 对 judge 主模型**与** Nemotron **各打一发**（同一份 schema） | ≤90 s（官方「up to approximately 90 seconds」），并行 ≈95 s / <800 ms | 400 ⇒ schema 写错，立即修 |
| 3 | prompt cache | 用完整静态前缀打一发，读 `cached_tokens` | ~600 ms | `cached_tokens=0` ⇒ 判「不启用 cache」 |
| 4 | TTS 连接与音色 | 两条连接各 `run-task` 一句「唔……让我看看。」，取首包 | 300–900 ms / <300 ms | 音色 400 / instruction 不支持 |
| 5 | ASR 连接 | 1 s 静音 + 一句标准句，等 final | 200–600 ms | 无 final / 语言不支持 |
| 6 | 预录核对 | `persona/preroll.json` 的 11 条（3 沉吟 + 8 宣布）时长 + SHA | <50 ms | 缺文件 / 时长偏差 ±20% |
| 7 | 汇总 | 写 `reports/preheat-<ts>.json` 并打表 | — | 任一项 fail → exit 1 |

**三个必须写进注释的事实**（都来自官方页）：

- **90 s 与 24 h**：新 schema 首次编译最长约 90 s，编译产物缓存 24 h——所以预热是**每天**的事，不是一次性。
- **prompt cache 的 512 token 下限**：Claude Haiku 5.5 每个缓存检查点最少 512 token，TTL 5 分钟或 1 小时，命中即重置，写入按 1.25× 计费。我们 300 字 prompt 估 250–400 token（估算，未标定），**低于下限就无法缓存**。做法：把 `prompt.md` + 四院台词样例做成 600–700 token 的稳定前缀（history 永远放后面）。若 11/16 24:00 前没做到 ≥512，就**明确写「不启用 cache」**，别留半成品；做进去了，收益是首 token prefill 少 30–80 ms（估算，需实测），钱可忽略。
- **schema 缓存是否跨模型复用，官方未写明** → 保守做法：主判官与 Nemotron 各预热一次，成本约 $0.001/场。

---

## 5. NVIDIA Nemotron 作为第二判官

**结论**：它不是兜底（比主判官慢），在线只在一种情况下、离线是常态；**一致性率是它唯一的产出**，且永不阻塞宣布。

| 触发 | 在线/离线 | 门限 | 处理 |
|---|---|---|---|
| 主判官低置信 | **在线（并发发起）** | `top1−top2 < 2` 或 `max < 6`，且预算剩余 ≥900 ms | 并发跑；宣布前未回 → 按主判官走，结果只落库 |
| 主判官超时/失败 | **离线** | 首 token 900 ms 超时 | 会话后 30 s 内补跑，**不参与本次** |
| 抽样 A/B | **离线** | 每 5 次抽 1（或每场第 1 人） | 落库 |
| 每场开场 | 离线 | 1 次 warm | 预热 schema（§4 步 2） |

**同 schema 比对与一致性口径**：两个模型共用一份 `judge.schema.json`。若 Bedrock 上 Nemotron 不支持结构化输出（`03-cloud.md` 标「视模型卡」），走 prompt + 本地 JSON 修复，**解析失败样本不计入分母**（否则把解析失败算成不一致，指标就假了）。一致 = `argmax(scores)` 相同；另记软一致 = 四维 Spearman ρ ≥0.8。报告给**两个数**：裸一致率 + Cohen's κ（四院先验不齐，κ 才站得住）；n ≥ 20 才写进材料。
**成本/延迟上限**：$0.000315/次（800 in / 300 out，官方计价）；抽样 20% → 100 次 +$0.0063（≈¥0.045）。在线硬上限 **1 次/会话、900 ms 即弃**；延迟数字需实测，不猜。

| 它干什么 | 它不干什么 |
|---|---|
| 同 schema 出 scores/evidence 做对照 | **不改 house**（判决权在代码 `argmax`，准则附录 C） |
| 离线一致性统计（率 + κ） | 不做在线兜底（比主判官慢，救不了场） |
| 抽样 A/B 的对照组 | 不写台词、不进 prompt 前缀、不进 cache |
| 材料里「第二模型交叉验证」那一页 | 不被观众听到、不参与任何降级决策 |

---

## 6. Kiro 在开发期怎么用

**结论**：Kiro 只干一件事——把「契约 + 降级矩阵」变成可执行的测试，产出三件可 grep 的物：**spec 文件、commit 链、测试报告**。它不碰 prompt 与判决公式。

| 阶段 | 产物 | 命令/入口 | 留证 |
|---|---|---|---|
| ① spec | `.kiro/specs/provider-contract/{requirements.md,design.md,tasks.md}`（三文件结构官方；目录名按工具默认，版本不同以实际为准）；requirements 用 EARS（「当 ASR 600 ms 无 final，系统应…」），design 放 §2 时序，tasks 拆 8–12 条 | Kiro spec 面板 | 目录入库 |
| ② adapter | tasks 生成 3 个 adapter 骨架 + `tests/contract/test_provider_contract.py`（provider × 契约 12 条参数化） | `pytest -k contract` | 每 task 一 commit，`Refs: G2` |
| ③ 故障注入 | `providers/faults.py`：`timeout / 5xx / rate_limit / garbage_json / refusal / ws_close` 六模式，覆盖 §3 的 12 格 | `make fault-matrix` | `reports/fault-<日期>.html` |
| ④ 回归 | cassette 回放 happy / asr_timeout / 断网三条，`house` 不许变 | `make replay` | CI 红绿 |

**留证三件套**：`.kiro/specs/` 入库（**官方三文件结构：requirements / design / tasks**）+ 每 task 一 commit（`Refs: G2`，body 写「为什么」）+ `reports/*.html` 进 `release/`。
**一条禁令**：Kiro 不得生成 `judge/` 的判决代码与 `persona/prompt.md`——判决权与人格不是 AI 的活（准则附录 C 第 1 条）。把这三条项目规矩写进 `.kiro/steering/`（官方工作区目录已核实），让 agent 不许越界。

---

## 7. TuyaOpen / 涂鸦云作为第三 provider

**结论**：**本期不接**。若接，只接 ASR，绝不接 TTS。

| 项 | 判断 |
|---|---|
| 接入点 | **ASR**：文本可观测、可降级、可自算 t2/t3。**TTS 不接**：音色是项目灵魂 + 复刻权利风险 + 无公开风格接口 |
| 需要什么 | 涂鸦开发者账号 + 云项目 + **PID** + 物模型（至少两个 DP：ASR 文本上报、TTS 文本下发，另需 `session_id` 对齐）+ license（T5AI-Core 出厂烧录；ESP32 自激活规则**需核实**）+ 按台授权计价**需核实** |
| 风险 | ① **不可观测**：拿不到 t2/t3/t4 → 上位机验收「6 时间戳」直接挂，TTFC 讲不出来；② 延迟未知：多两跳，冷 TLS 实测 0.78–1.76 s，估 +1.5–3.5 s，打穿 1.8 s；③ 音色控制弱（无公开 instruction 接口，需核实）；④ 许可 `NOASSERTION`（本次 GitHub API 复核：1,948 star、2026-11-13 仍在提交）；⑤ 与 G4 冻结冲突：加一个 provider ≈ 改配置 + 测试矩阵 + 1 次彩排 |

**「什么条件下才接」——五条全满足**：① 赛方**书面**确认 license 与 PID/物模型文档；② 以插件接入（一个 adapter 文件 + 一行配置，**不改编排**）；③ 实测首包中位 ≤600 ms（3 次）；④ 能拿到文本级中间结果（自算 t2/t3），否则只做离线对照；⑤ 时间在 **11/17 24:00 之后**——而准则规定此后**只删不加** ⇒ 落到结论：**本期只写评估笔记，不接**。

---

## 8. 质量与成本

**结论**：盲评只评「听感与相关性」，不评「分得准不准」（没有 ground truth）；成本上 **ASR 占 73%**，所以任何省钱动作都不该动 LLM。

### 8.1 20 条固定输入人工盲评表

| 列 | 内容 | 谁填 |
|---|---|---|
| # | 01–20 | C |
| 输入脚本 | 逐字，不临场编 | C |
| 期望倾向 | 只写「更像哪两院」，不写唯一答案 | C |
| 实际 house / 四院分布 | `result.house`；汇总「≥3 院、任一 ≤40%」 | 自动 |
| 首句字数 / 引原话通过率 | ≤12 字；编辑距离 ≤2 | 自动 |
| 像不像帽子（1–5） | 盲听，不看 house | A/B/C 交叉 |
| 理由与输入是否相关（1–5） | 盲听 | A/B/C 交叉 |
| TTFC | 秒表 + 日志对账（>200 ms 判本次作废） | 自动 |
| 出戏 / 故障 | 自由文本 | 观察者 |

盲法三条：播放顺序随机；不告知模型与供应商；三人独立打分后再对表，分歧 >2 分进「争议集」复听。汇总只报**中位数与通过率**，不报平均（n=20 的平均没有意义）。

### 8.2 单次会话成本拆解

| 项 | 单价（官方） | 单次用量 | 美元 | 人民币 | 占比 |
|---|---|---|---|---|---|
| ASR | $0.0001667/秒 | 90 s | $0.01500 | ¥0.1065 | **73%** |
| LLM | $0.10 / $0.50 每 1M | 800 in / 300 out | $0.00023 | ¥0.0016 | 1% |
| TTS | $0.13 / 万字符 | 400 字 | $0.00520 | ¥0.0369 | 25% |
| 第二判官 | $0.000315/次 | 抽样 20% | $0.00006 | ¥0.0004 | <1% |
| **合计** | | | **$0.0205** | **¥0.145** | 100% |
| 100 次 | | | $2.05 | ¥14.5 | 与 ¥0.145 目标一致 |

预热另计：每场 1–3 次调用（schema 编译 + cache 写）≈ $0.002，可忽略。

### 8.3 延迟预算（与主报告 1.24 s 对齐）

| 口径 | 值 | 用在哪 |
|---|---|---|
| 分段预算合计 | **1.24 s** = 300 + 60 + 200 + 350 + 250 + 80 | 方案与 PPT |
| 上台验收 | **1.8 s**（中位，10 次） | 彩排 G8 |
| 内部 Gate | **2.5 s**（不过即砍环节） | 11/16 23:30 |

一句话对齐：§2 表中带预算的六行（300 / 60 / 200 / 350 / 250 / 80）逐段等于主报告 §5.3 的六段；而 **600 / 900 / 800 ms 是「超时阈值」，不是「分段预算」**——两个数不能相加。`03-cloud.md` 与架构文档 §4.2 看似「打架」，唯一原因就是没区分这两列。

---

## 9. 明确不做

| 不做 | 为什么 | 谁最容易提 |
|---|---|---|
| 端侧 LLM | 帽内 8 MB PSRAM，与最小可用模型差 3 个数量级 | 「要不要离线也能判」 |
| 端侧 TTS 当主角 | UTMOS 2.80（教师 4.42）、只吃英文音素；它只配做断网兜底 | 「省云费」 |
| 实时变声 | 需要真人配音员实时说话，多人、多延迟、多损耗；角色音色 TTS 直接给 | 「更像电影原声」 |
| 把判决交给模型 | 会漂移、会讨好；`house` 必须代码 `argmax` | 「让大模型直接给学院」 |
| 多供应商同时在线 | 双跑双付费、双向日志对不齐、失败归属不清；唯一例外是 Nemotron 第二判官（只对照，不判决） | 「都接上更保险」 |

---

## 10. 与准则的一致性 + 待核实

**一致性三条**：① 判决权在代码，`judge` 纯函数、可单测，LLM 只出 `evidence` + `scores`；② 不新增错误码，降级一律复用准则 §3.3 的 7+3 集合并带 `degrade` 字段；③ 三 adapter 用同一 `replay` code path，`make smoke-host` 三发、`make replay` 三 fixture 与准则 §6.2 对齐。
**与 `01-device-api.md` 的接缝**：ASR 600 / LLM 900 / TTS 800 三处软阈值逐字一致；本文的「judge 完成 1500 / 硬 2000」是编排内部预算，**不改** `llm{delta}` 的 3 s 硬阈值，也不新增消息类型。

| # | 待核实 | 谁 | 何时 |
|---|---|---|---|
| 1 | Nemotron 在 Bedrock 上的中文 JSON 稳定性（20 条）与模型 id | B | 11/16 |
| 2 | schema 编译缓存是否跨模型复用 | B | 11/16 预热时实测 |
| 3 | 我们静态前缀的实际 token 数（是否 ≥512） | B | 11/16 |
| 4 | CosyVoice WS 是否支持 24000 采样率、`instruction` 字段名 | B | 11/16 |
| 5 | 涂鸦云中文首包延迟、授权计价、是否允许自带音色 | B | 11/16 |

---

**来源（本次直接抓取）**：[Bedrock 结构化输出](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)（90 s 首编译 / 24 h 缓存 / `additionalProperties:false` / 可选属性 ≤12 / union ≤16）、[Bedrock prompt caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)（Claude Haiku 5.5 = `anthropic.claude-haiku-5-5`，最小 512 token，TTL 5 min/1 h，写入 1.25×）、[Transcribe 流式与 partial 稳定化](https://docs.aws.amazon.com/transcribe/latest/dg/streaming-partial-results.html)（`IsPartial`/`Stable`/`PartialResultsStability`）、[CosyVoice WebSocket API](https://www.alibabacloud.com/help/en/model-studio/cosyvoice-websocket-api)（run-task→task-started→continue-task→result-generated→finish-task→task-finished，连接复用，SSML 与多段互斥）、[cosyvoice-v3.5-flash](https://www.alibabacloud.com/help/en/model-studio/cosyvoice-v3-5-flash)（free-style instruction）、[Kiro Specs](https://kiro.dev/docs/specs/) 与 [Kiro Steering](https://kiro.dev/docs/steering/)（`requirements.md`/`design.md`/`tasks.md`；`.kiro/steering/`）、[TuyaOpen](https://github.com/tuya/TuyaOpen)（ASR/KWS/TTS、ESP32 支持、license `NOASSERTION`）。价格与模型对照见 `03-cloud.md`（Transcribe $0.010/min、Haiku 5.5 $0.10/$0.50、CosyVoice $0.13/万字符、Nemotron 3 Super 120B $0.15/$0.65）。
