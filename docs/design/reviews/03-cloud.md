# 03 · 云侧语音管线与分院人格算法

> 评审对象：分院帽实体复刻（麦克风 + 喇叭 + 云侧 ASR/LLM/TTS/存储，单次会话 60–90 秒）。
> 核查时间：2026-11-15。环境说明：本会话 `web_search` 返回 401 不可用，全部核实改用 `web_fetch` / `curl` 直取官方页与**官方计价数据源**（`b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/*`，即 aws.amazon.com 计价页上价格数字的真实来源）；PDF 与纯 JS 渲染页抓不到的一律标「未核实」，不猜。
> 与上一版备忘录的关系：`分院帽项目-可行性与实施方案.md` 的三条结论（Transcribe Streaming 支持中文、Polly 中文只有 Neural 且 Generative 无中文、CosyVoice-v3-Flash 流式克隆 $0.13/万字符）**本次全部复核成立**（细节有修正，见各节）。本文增量：Nova Sonic 核实、成本细算、分院算法防偏与一致性、声音作为敏感个人信息的合规落地。

---

## 0. 结论速览

1. **主链路推荐：Transcribe Streaming（zh-CN）+ Bedrock Claude Haiku 5.5（结构化输出）+ CosyVoice-v3-Flash/v3.5-flash 中文角色音色**。这三段今天都能直接开通，`3 天可用` 判定全部为「是」。单次 90 秒约 **$0.020（¥0.15）**，100 次 ≈ **¥15**——云成本不构成任何约束。
2. **Nova Sonic（双向流式语音）已上线、可用、但「仅英文（及法/意/德/西/葡/印地）」**：官方语言表 10 个 locale 里**没有中文**，Nova 1/2/2.5 三代文档均未列中文音色。→ **不能做中文主链路**，可作路演英文彩蛋。这是本次最关键的核实结果。
3. **TTS 是唯一不可替代的组件**，「最省力路径」不是克隆队友，而是 **CosyVoice 的「指令控制」：用一个现成老年男声基底 + 一句中文风格描述**，零录音、零授权风险、30 分钟出音色。克隆队友是可选加分项（需书面同意 + AI 标识）。
4. **分院算法最大的坑不是「分不准」，是「所有人都分到格兰芬多」**。解法是把判决权从 LLM 手里拿走：LLM 只负责**举证**（四维证据 + 引用原话），`house` 由代码按公式 + 反集中修正算出。这样既防偏又可解释。
5. **最大合规风险：声音是敏感个人信息**（PIPL 生物识别条款），叠加「合成人声必须标识」。最小可行合规包：**音频不落盘 + 现场一句话告知 + 克隆须被克隆人书面单独同意 + 赛后 7 天删除音色 + 播报前后 AI 合成提示**。

---

## 1. ASR

**结论**：「3 天能用」选 **AWS Transcribe Streaming**（中文流式已确认、按秒计费无最低、SDK 齐、能拿 AWS 生态分）；「中文更稳」选 **阿里 fun-asr-realtime / paraformer-realtime-v2**（方言、热词、噪声鲁棒是官方明写的优势，且便宜 3.5 倍）。两者都用 WebSocket，**切换成本约半天工时**，这就是最好的保险。

| 方案 | 中文 | 流式 | 价格（官方） | 90 s 成本 | 3 天可用 | 中文稳定性 |
|---|---|---|---|---|---|---|
| **AWS Transcribe Streaming** | zh-CN / zh-HK(yue-HK) / zh-TW 均 `batch, streaming` | 是 | **$0.010/分钟**（$0.0001667/秒，按秒计费、无最低）；免费额度 60 分钟/月 × 12 个月 | **$0.0150** | **是** | 标准普通话；方言/口音/专名弱（未见官方中文鲁棒性表述） |
| 阿里 paraformer-realtime-v2 | 普通话（含方言）+ 英/日/韩，`language_hints` 可切 | 是 | **该页未列价 → 未核实**（RPM 1200） | 未核实 | 是 | 官方明写「covers multiple regional dialects」+ 热词 |
| 阿里 fun-asr-realtime | 中英 + 方言，噪声鲁棒、热词、ITN | 是 | **$0.000047/秒** | **$0.0042** | 是 | 同上（同门更强的一代） |
| 火山（豆包语音） | 是（流式/一句话/录音文件识别） | 是 | 文档站为 JS 应用，**未核实** | — | 需国内实名与商务流程，**3 天有不确定性** | 口传很好，但无一手价 |
| 本地 FunASR | 是（16k 流式中文成熟） | 是 | 0 元 API 费（要一台常驻机器 + 工时） | ¥0 + 机器 | 半是（模型下载 + 服务封装 ≥1 天） | 可控，但断网才划算 |

- **延迟量级：官方未公布数值 → 未核实**。可确定的是流式 + 边传边出中间结果；工程上按「尾字 300–800 ms」做预算，`待实测`（见 §5 时序表）。
- 实操细节：Python 用 `awslabs/amazon-transcribe-streaming-sdk`（官方列出），不是 boto3 直调；`ap-northeast-1`（东京）与 `ap-southeast-1`（新加坡）流式同价 $0.0001667/秒，上海演示选东京。
- 免费额度算术：100 次演示 × 90 s = 150 分钟，超出 60 分钟额度 90 分钟 ≈ **$0.90**。别为这 6 块钱做任何设计妥协。

来源：<https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html>、<https://aws.amazon.com/transcribe/pricing/>（"Streaming transcription is priced at $0.01 per minute"、按秒计费无最低、Free Tier 60 分钟）、<https://www.alibabacloud.com/help/en/model-studio/paraformer-realtime-v2>、<https://www.alibabacloud.com/help/en/model-studio/fun-asr-realtime>

---

## 2. LLM（人格扮演 + 结构化 JSON）

**结论**：**Bedrock 上首选 Claude Haiku 5.5**（$0.10/$0.50，比 Nova 2 Lite 便宜 4 倍、人设贴合度高）；**「纯 AWS 叙事」备选 Nova Lite**（$0.06/$0.24，AWS 自家最省的一档里性价比最好）；**NVIDIA Nemotron 3 Super 120B 用作「第二校验模型」**——这是把评分表里「NVIDIA」那一项变成真实用途、而不是硬凑的最佳挂法。中文人设最强的仍是 DeepSeek/Qwen，作为断网外的备链路。

| 模型（Bedrock 标准档；Claude 取 Global CRIS 档） | 输入/1M | 输出/1M | 单次 800 in / 300 out | 结构化输出 | 备注 |
|---|---|---|---|---|---|
| Amazon Nova Micro | $0.035 | $0.14 | $0.000070 | 支持 | 最便宜；人设偏干 |
| Amazon Nova Lite | $0.06 | $0.24 | $0.000120 | 支持 | 纯 AWS 叙事性价比最优 |
| Amazon Nova 2 Lite | $0.30 | $2.50 | $0.000990 | 支持 | 新一代，贵 8 倍 |
| Amazon Nova Pro | $0.80 | $3.20 | $0.001600 | 支持 | 本项目不必 |
| **Claude Haiku 5.5** | **$0.10** | **$0.50** | **$0.000230** | 支持 | **推荐主选** |
| NVIDIA Nemotron Nano 2 | $0.06 | $0.23 | $0.000117 | 视模型卡 | 最省 |
| **NVIDIA Nemotron 3 Super 120B** | **$0.15** | **$0.65** | **$0.000315** | 视模型卡 | **推荐作校验模型** |
| （对比）DeepSeek-V4.1-Flash 峰值 / 谷时 | $0.30 / $0.15 | $1.20 / $0.60 | $0.00060 / $0.00030 | JSON Output ✓ | 中文人设最听话 |
| （对比）Qwen-Flash 新加坡 | $0.05 | $0.40 | $0.000160 | Structured Outputs ✓ | 北京区更便宜（$0.022/$0.216） |

**Bedrock 结构化输出的四个硬约束**（会直接影响你的 3 天排期）：

1. 每个 object **必须**显式 `additionalProperties: false`，否则 400；
2. **不支持** `minLength/maxLength/minimum/maximum`——「三条理由每条 ≤40 字」「分数 0–10」这类约束**只能在 prompt 里写 + 代码里校验**；
3. 可选属性全 schema 合计 ≤12 个，union 类型 ≤16 个 → schema 要画得扁；
4. **新 schema 首次调用要现场编译语法，最长约 90 秒**，之后缓存 24 小时 → **演示前必须预热一次，否则第一次演示直接超时**。这是本次最容易踩的坑。

来源：<https://aws.amazon.com/bedrock/pricing/>（NVIDIA 面板：Nemotron Nano 2 $0.06/$0.23、Nemotron 3 Super 120B $0.15/$0.65）、<https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html>、<https://api-docs.deepseek.com/quick_start/pricing>、<https://www.alibabacloud.com/help/en/model-studio/qwen-flash>

---

## 3. TTS（最关键）与「分院帽音色」

**结论**：Polly 中文**只有 Neural（cmn-CN Zhiyu，女声）**，**Generative 引擎 55 个音色里一个中文都没有**——上一版结论复核成立，且这次是逐条核对音色表得到的。因此中文演示的音色必须走第三方。**最省力路径 = CosyVoice 指令控制（不克隆真人）**。

| 方案 | 中文 | 克隆 | 流式 | 价格（官方） | 400 字成本 | 判定 |
|---|---|---|---|---|---|---|
| Polly Neural `Zhiyu`（cmn-CN） | ✅ | ❌ | 实时/异步 | $16/1M 字符 | $0.0064 | 音色=女声播报员，**做不出帽子**；留作兜底预录 |
| Polly Neural `Hiujin`（yue-CN 粤语） | ✅(粤) | ❌ | 实时 | $16/1M 字符 | $0.0064 | 同上 |
| Polly Generative（55 音色） | ❌ 无中文 | ❌ | 双向流式 | $30/1M 字符 | $0.0120 | 只能做英文彩蛋 |
| **CosyVoice-v3-Flash** | ✅ | ✅ **5–20 s 参考音频** | ✅ 实时流式 | **$0.13/万字符**（新加坡）/$0.14335（北京） | **$0.0052** | **主选（新加坡区）** |
| **CosyVoice-v3.5-Flash** | ✅（10 语种） | ✅ + **指令控制（free-style instruction）** | ✅（官方称首字延迟更低） | $0.116/万字符（仅北京区列价，新加坡**未核实**） | $0.0046 | **主选（北京区）**，风格控制最省事 |
| Inworld Realtime TTS-2 | 称 ~500 语言 | ✅ 3–30 s | ✅ | $25/1M 字符 | $0.0100 | 自然语言 steering 强，但贵 2 倍 |
| Inworld TTS-2 Flash | 同上 | ✅ | ✅ 首包可至 50 ms | $15/1M 字符 | $0.0060 | 便宜且快，**但忽略文字指令** |
| ElevenLabs | 多语种 | ✅ | ✅ | 1 credit/字符；Creator $22/121k ≈ **$1.82/万字符** | $0.073 | 贵约 14 倍，比赛不划算 |
| 火山（豆包语音，双向流式 + 声音复刻 + 音色设计） | ✅ | ✅ | ✅ | **未核实**（文档站 JS 应用） | — | 能力齐，商务流程 3 天有风险 |

### 3.1 「分院帽音色」三条路的取舍

| 路径 | 工时 | 质量 | 风险 | 建议 |
|---|---|---|---|---|
| **A. 现成老年男声 + 指令控制**（CosyVoice-v3.5-flash，北京区） | **30–60 分钟** | 高（沙哑、慢、气声都可写进 instruction） | 零授权风险 | **必做（推荐主线）** |
| B. 克隆一位队友（v3-flash，5–20 s 参考音频） | 2–3 小时（录音 10 版挑 1 版 + 调参 + 试听） | 最高（真人质感） | 需被克隆人**书面单独同意** + AI 合成标识；音色存第三方 | 有时间才做，**作为 A 的加分替代** |
| C. Polly Neural Zhiyu | 10 分钟 | **不合格**（女声播报） | 低 | **只用于兜底预录 10 句** |
| D. 风格化处理（与 A/B 叠加，不是替代） | 1 小时 | 决定「像不像帽子」 | 低 | **必做** |

**A 的具体写法**（这才是「最省力」的全部秘密）：`instruction` 写中文风格描述，别写音色 ID 试错——「七十岁上下的老人，声音沙哑偏低，语速慢，句尾略上扬带点戏谑，像在自言自语；每个逗号后停半拍」。一次生成 4 版，10 分钟能听完全部，选 1 版锁定。

**D 的四个免费增益**：
1. **文本层**：台词里塞「唔……」「嗯——」「让我看看……」；破折号、省略号直接变成停顿；
2. **首句 ≤12 字**：「唔……让我看看。」——12 字 ≈ 1.5 秒音频，正好盖住 LLM + TTS 的延迟；
3. **预录 3 句沉吟 + 2 句兜底**（本地播放，零延迟、零成本）：`沉吟A.wav`「唔……又一位新面孔。」`沉吟B.wav`「有趣，非常有趣。」`兜底.wav`「让我再想想……」
4. **语速**：中文 4.2–4.6 字/秒是「老人说话」的甜点；超过 5 字/秒立刻不像帽子。

来源：<https://docs.aws.amazon.com/polly/latest/dg/available-voices.html>（cmn-CN Zhiyu：Generative=No、Long Form=No、Neural=Yes）、<https://docs.aws.amazon.com/polly/latest/dg/generative-voices.html>（55 音色、无中文；东京/新加坡可用）、Polly 计价数据源 `meteredUnitMaps/polly/USD/current/polly.json`（Neural $16/1M、Generative $30/1M）、<https://www.alibabacloud.com/help/en/model-studio/cosyvoice-v3-flash>、<https://www.alibabacloud.com/help/en/model-studio/cosyvoice-v3-5-flash>、<https://inworld.ai/pricing>、<https://inworld.ai/tts>、<https://elevenlabs.io/pricing>

---

## 4. Amazon Nova Sonic：核实结果与架构判断

**结论：可用，且已在第三代（Nova 2.5 Sonic），但「仅非中文」——不能做中文主链路。**

| 核实项 | 结果 | 依据 |
|---|---|---|
| 是否上线 | **是**。Nova 2 Sonic 2025-12-02 发布、状态 Active；**Nova 2.5 Sonic 2026-10-05 发布**（支持到 2027-10-05） | Bedrock 模型卡 |
| 模型 ID / API | `amazon.nova-2-sonic-v1:0`、`amazon.nova-2-5-sonic`；唯一 API = `InvokeModelWithBidirectionalStream`（不支持 Converse/Invoke） | 模型卡 |
| 区域 | us-east-1 / us-west-2 / eu-north-1 / **ap-northeast-1（东京）**，**不支持跨区推理**（Geo/Global 均 No） | 模型卡 |
| **语言** | **官方语言表 10 个 locale：en-US、en-GB、en-AU、en-IN、fr-FR、it-IT、de-DE、es-US、pt-BR、hi-IN。polyglot 音色（Tiffany/Matthew）只覆盖英/法/意/德/西/葡/印地 7 种。Nova 1 文档更少（5 种）。→ 三代文档均无中文** | nova2 用户指南「Language support」 |
| 延迟 | 官方只写 "low latency"/"lower latency"，**无任何数值 → 未核实** | 模型卡 |
| 计价 | speech token **$3 / 1M 输入、$12 / 1M 输出**；text token $0.33/$2.75；**官方未公布「每秒音频≈多少 token」→ 单次成本无法精确折算（未核实）** | aws.amazon.com/nova/pricing |
| 角色扮演 | 支持（2.5 明确「更可靠地遵循 system prompt / persona 指令」、barge-in、工具调用、code-switching、跨模态输入） | 模型卡 |
| 限制 | **不支持 Guardrails**、不支持 Count tokens、不支持 Abuse detection；并发配额 20 个双向流（2.5 可申请提高，2 不可调） | 模型卡 |

**判断（这就是那道架构分叉）**：

- 若中文可用，Nova Sonic 会把「ASR+LLM+TTS」三段合成一段，管线代码量减半、首字延迟天然最优——**但它不可用中文**，分叉直接关闭。这不是「再等等」的问题：Nova 1→2→2.5 三代的语言表都没加中文，3 天内不可能变。
- 复刻它的架构收益（单段端到端）有**低工时替代**：仍然三段，但用 §5 的「预录沉吟 + 按句流式」，实测首字能压到 2.0–2.5 s，与 Sonic 的量级同档。
- **唯一值得做的 Sonic 用法**：路演现场若评委用英文提问，切到 Sonic 做 **30 秒英文对话**（东京区，`amazon.nova-2-5-sonic`），一句话证明「我们评估并验证了端到端语音大模型」。**工程量 4–6 小时**（双向事件协议 + 16 kHz PCM 双向编码 + barge-in 处理）→ **不建议在 11/18 前做**，建议 11/19–11/20 有余力再做。
- 另一个隐性风险：**语音模型按 token 计费且不公布 token/秒换算**，账单不可预估。这在评分「工程与技术实现」里是可以主动讲的对照点——「我们评估了 Nova Sonic，因中文缺失与计费不可预估而弃用」，比「我们不知道有这个东西」强得多。

来源：<https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-sonic.html>、<https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-5-sonic.html>、<https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html>、<https://docs.aws.amazon.com/nova/latest/userguide/speech.html>、<https://aws.amazon.com/nova/pricing/>

---

## 5. 管线编排（流式拼接、并发、超时、降级）

**结论**：单帽单会话、**半双工**、**按句切分 + 首句 ≤12 字**、**预录沉吟打头**。首字目标 ≤2.0 s（可接受 2.5 s）。所有超时都必须有「不联网也能演完」的出路。

### 5.1 五个工程约定

1. **切分规则**：LLM 流式输出按 `。！？…\n` 切句；第一句强制 ≤12 字（prompt 里写死）；每句 ≥6 字才送 TTS，避免「唔。」这种碎片单独起一次合成。
2. **并发与隔离**：一件事一次会话，`session_id` 贯穿 ASR/LLM/TTS 三个连接；每会话独立 WebSocket，不共享缓冲；全局并发上限取三者最小值（Nova 20/账号、CosyVoice RPM 180、Transcribe 流式并发**未核实**）。单帽演示并发恒为 1，这个上限只是防呆。
3. **超时与重试**：ASR 3 s 无 final → 重问一句；LLM 首 token 2.5 s → 切模板句；LLM 总 6 s → 截断已生成部分照播；TTS 首包 1.5 s → 播预录句；会话硬超 90 s → 强制收尾宣布。重试：ASR 1 次（换区/换厂商）、LLM 1 次（降温度）、TTS 2 次（换音色不换文本）。
4. **幂等**：`session_id + seq`，播放侧去重，防止重连导致同一句播两遍。
5. **预热**：Bedrock 结构化输出 schema **开场前调一次**（首次编译最长 90 s）；TTS 音色预热一次。

### 5.2 端到端时序表（t=0 为「观众说完最后一个字」）

| # | 阶段 | 相对时间 | 预算 | 观测点 | 超时降级 |
|---|---|---|---|---|---|
| 0 | 预录沉吟起播（与上传并行） | −1200 → 0 | 1200 ms | 播放日志 | 无（本地文件） |
| 1 | VAD 尾点判定 | 0 → +300~500 | 400 ms | VAD 事件时间戳 | 降到 300 ms + 按钮「我说完了」 |
| 2 | 上行（Opus 16k，~24 kbps） | +400 → +480 | 80 ms | WS 抓包 | 就近区域（东京） |
| 3 | ASR final（流式尾字） | +480 → +780 | 300 ms | 首字/尾字时间戳 | 重试 1 次 / 切 fun-asr |
| 4 | LLM 首 token（流式） | +780 → +1680 | 900 ms | 第一个 SSE chunk | **切模板句 + 预录音频** |
| 5 | 第一句完整（≤12 字） | +1680 → +1980 | 300 ms | 切句器出句 | 用已有片段凑一句 |
| 6 | TTS 首包 | +1980 → +2280 | 300 ms | 首个音频帧 | 播预录兜底句 |
| 7 | 下行 + 播放缓冲（双缓冲） | +2280 → +2420 | 140 ms | 首帧入队 | 降采样率保时序 |
| 8 | **首字出声** | **≈ +2400** | — | 麦克风回路实测 | — |
| 9 | 正文流式播放（按句流水线，覆盖 LLM 后续 token） | +2400 → +30 s | — | 每句起播时间 | — |
| 10 | 收尾（宣布学院 + 灯/帽尖） | 至 ≤90 s | — | 会话总时长 | 硬超时强制收尾 |

> 关键读数：**首字出声 ≈ 录音结束后 2.4 s，但观众感知的空白只有 1.2 s**（前 1.2 s 是帽子在「沉吟」）。这就是「延迟不是被消灭，是被表演掉」。全部数字为分段估算，`待实测`。

---

## 6. 分院算法（防偏 + 强相关 + 一致性 + 兜底）

**结论**：**不要相信 LLM 的判决，只相信它的举证。** 把 `house` 的计算权收回代码，是同时解决「全都格兰芬多」和「理由和对话无关」的唯一手段。

### 6.1 输出 schema（严格版，适配 Bedrock structured outputs）

```
{ house: "勇气|野心|智慧|忠诚",
  scores: { 勇气:int, 野心:int, 智慧:int, 忠诚:int },   // 0–10，代码侧校验
  evidence: { 勇气:[str], 野心:[str], 智慧:[str], 忠诚:[str] },  // 每条 ≤12 字原话片段
  reasons: [str, str, str],   // 每条 ≤40 字，必须含「……」引语
  line: str }                 // ≤30 字角色台词
```
> 注意：schema 不支持 `minLength/maxLength/minimum/maximum`，长度与分值区间**只能靠 prompt 约束 + 代码断言**；`additionalProperties: false` 必须逐层显式写。

### 6.2 prompt 骨架（约 300 字，可直接用）

> 你是霍格沃茨的分院帽，一顶一千岁的旧帽子。你说话慢、爱卖关子、带点戏谑，但从不说教。
> 你只做一件事：根据对面这个人刚才说的话，判断他更像哪一种人。
> **规则**：①你**不做判决**，只负责举证——在 `evidence` 里为四个维度各摘至少一条他的原话（≤12 字，逐字摘，不许改写）；②`reasons` 三条必须各含一处「引号原话」，指向具体行为或动机，不许写「你很勇敢」这类空话；③四个维度里必须有两个以上分数接近（差 ≤2），不要给满分；④`line` 是你的一句台词，20 字内，不要提任何书名、地名、人名；⑤如果对方说的话不足以判断，就不要硬评，在 `line` 里再问一个具体问题。
> 说得越具体，分得越准。

> 命名与 IP 分级解耦：上面这段 prompt 的**结构**在 A/B/C 三级方案下完全不用改，只换名词——A 级用原名；B 级改为「一顶会说话的旧帽子 / 四种气质」；C 级改为完全原创的四个学院名与四维（勇气/野心/智慧/忠诚可保留，它们是通用人格词，不像学院名那样是登记性标识）。分级细则见 `04-experience.md`。

### 6.3 四条防偏机制（按性价比排序）

| 机制 | 做法 | 效果 |
|---|---|---|
| **①判决权收回** | LLM 只出 `evidence` + `scores`；`house = argmax(scores)`，由**代码**算 | 最强。避免 LLM「因为台词好听所以选格兰芬多」 |
| **②反集中修正** | 维护本场 house 直方图；若连续 3 次同院，下一次该院分数 ×0.85（软打折，不改前两名差 >3 的判决） | 解决「观众投票式偏好」导致的聚集 |
| **③强制拉开** | 代码校验：top1 − top2 < 2 时，要求 LLM 补一条对比性追问（允许第 3 个问题） | 让分数真的有区分度，也给「2–4 句话」留出第 3 句 |
| **④台词池** | 每院 6 套开场词 + 6 套宣布词，随机不重复（本场不重复） | 现场观众互相听得到，重复会立刻暴露「模板感」 |

### 6.4 理由与对话强相关（可机器校验）

`reasons[i]` 必须包含 `「…」`；代码提取引号内文本，与 ASR 转写做**编辑距离 ≤2 的子串匹配**（容忍 ASR 错字）。不通过 → 重试 1 次 → 仍不通过 → 用 `evidence` 里最长的一条拼模板：「你说『…』——这句我记下了。」（永不空手）。

### 6.5 一致性校验六条（全部代码断言，任一失败即降级）

① JSON 可解析 ② `house` ∈ 4 个枚举 ③ `house == argmax(scores)`（不等则强制以代码为准并记 anomaly）④ 三条 `reasons` 互不重复（两两 Jaccard <0.5）⑤ `line` 命中 IP 黑名单（书名/地名/人名）则为 0 分 ⑥ 长度与数值区间。

### 6.6 兜底：5 道选择题式本地打分（LLM 挂了也能演完）

- 5 道题，每题 4 个选项，选项各映射一个学院 +1（题库本地 JSON，零网络）；
- 观众答 3 题即可（每题 5 秒），答不出就用默认分布；
- 代码算四维分数 → `house` → 播对应学院的**预录台词**（每院 2 句，共 8 句）；
- 这条路径与主链路共用**同一份输出结构**，上层渲染（灯/帽尖/扫码页）完全不用改。

---

## 7. 安全与合规

### 7.1 内容安全：三层，且绝不「教育」观众

| 层 | 做法 | 触发后 |
|---|---|---|
| 输入侧 | ASR 文本关键词 + 轻量分类（自伤、未成年、政治敏感、辱骂、真实人名） | 切「安全人格」：帽子**不出戏**地终止（「帽子今天不谈这个。」），随后一句关怀 |
| 生成侧 | system prompt 写死：不诊断、不评价真实人物、不涉政治与宗教评判、不给医疗建议 | — |
| 输出侧 | `line` 与 `reasons` 过黑名单正则；TTS 前再过一遍 | 该句弃用，换模板句 |

自伤场景只有一个正确做法：**不追问、不分析、不戏剧化**，一句话关怀 + 引导求助（心理援助热线号码演示前人工核实后预置，**不要凭记忆写号码**）。未成年出现在展台：现场规则「**16 岁以下需监护人陪同**」宁可保守。

### 7.2 声音是敏感个人信息（这是本项目最大的合规风险）

PIPL 把「生物识别」列为敏感个人信息；**声纹/声音在用于识别身份时属生物识别信息**，实务上按敏感个人信息从严处理。处理敏感个人信息需同时满足：特定目的 + 充分必要性 + 严格保护措施 + **单独同意** + 事前**个人信息保护影响评估**（对应 PIPL 第 28、29、30、55 条；**本次未能在线取到法条原文**——人大网页为框架页、`cac.gov.cn` 连接失败，条文序号按公开文本整理，**正式对外引用前必须复核**）。

| 处理动作 | 是否涉敏感信息 | 最小可行做法 |
|---|---|---|
| 会话音频上传 ASR | 是 | **流式直通、不落盘**：ASR 返回文本即丢音频；服务端日志只留文本 + 时间戳 + 会话 id（无姓名/手机号） |
| 转写文本存储 | 是（可关联人身） | 默认**不保存**（现场提供「保存档案」勾选，默认关）；若保存，30 天自动删除 |
| 克隆队友声音（CosyVoice） | **是，且是二次处理** | 被克隆人**书面单独同意**（用途、期限、撤回方式）；告知音色保存在阿里云；**赛后 7 天内删除音色** |
| 分院结果上云（DynamoDB/扫码页） | 否（去标识） | 只存 `{session_id, house, scores, reasons}`，不存音频、不存转写 |

**现场告知（30 秒，写在牌子上，也口头说一句）**：
> 「这次对话会实时转成文字用于分院，**音频不留存**；可以说『停』随时中止。分院结果只保留学院和理由，不带你的名字。」
> 牌子配二维码 → 隐私说明页（处理者、目的、期限、撤回方式、联系方式）。克隆音色另需一句：「帽子的声音由 AI 合成。」

### 7.3 AI 合成内容标识（容易被忽略的硬要求）

《人工智能生成合成内容标识办法》自 **2025-09-01 施行**，要求对**合成人声/仿声**添加显式标识（条文细节同样**未能在线核实**，按公开口径执行）。落地三条：①帽子播放前/后一句「以下声音由 AI 合成」或灯带固定提示；②路演拍摄的短视频上传平台时勾选「AI 生成」；③分院档案页脚注「本页文字与语音由 AI 生成」。（顺带一个加分点：Inworld TTS 官方称其输出**含水印/频谱指纹**——若走 Inworld，这就是合规叙事素材。）

---

## 8. 成本

**结论**：**单次 90 秒 ¥0.07–0.16，100 次演示 ¥7–16。云成本可以当作 0，任何为此做的架构妥协都是错的。**（汇率按 ¥7.1/$ 假设，非核实数字）

### 8.1 单次 90 秒会话（ASR 90 s + LLM 800/300 token + TTS 400 字）

| 环节 | AWS 一套 | 阿里一套 |
|---|---|---|
| ASR | Transcribe Streaming 90 s × $0.0001667 = **$0.0150** | fun-asr-realtime 90 s × $0.000047 = **$0.0042** |
| LLM | Claude Haiku 5.5 800×$0.10/1M + 300×$0.50/1M = **$0.00023** | Qwen-Flash（新加坡）800×$0.05 + 300×$0.40 = **$0.00016** |
| TTS | Polly Neural Zhiyu 400 字 × $16/1M = **$0.0064**（**音色不合格**） | **CosyVoice-v3-Flash** 0.04 万字符 × $0.13 = **$0.0052** |
| **合计（按各自原生栈）** | **$0.0216 ≈ ¥0.153** | **$0.0096 ≈ ¥0.068** |
| **合计（推荐混合：AWS ASR+LLM，CosyVoice TTS）** | **$0.0204 ≈ ¥0.145** | — |

变体：Inworld TTS-2 Flash 替代 → $0.0212；ElevenLabs 替代 → $0.088（贵 4 倍）；Nova Sonic 若走端到端，按「10 token/秒」推断（**未核实**）约 $0.010/次——但因为**没有中文**，此路不通。

### 8.2 100 次演示

| 方案 | 合计 | 备注 |
|---|---|---|
| AWS 原生（Transcribe + Haiku 5.5 + Polly Neural） | **≈ $2.16 ≈ ¥15.3** | 免费额度抵 40 次（60 分钟）→ 实付 ≈ ¥11 |
| 推荐混合（Transcribe + Haiku 5.5 + CosyVoice） | **≈ $2.04 ≈ ¥14.5** | 同上减免 → 实付 ≈ ¥10 |
| 全阿里（fun-asr + Qwen-Flash + CosyVoice） | **≈ $0.96 ≈ ¥6.8** | 无免费额度也几乎免费 |

**对比参照**：一顶帽子的 BOM ¥200–360，一次 3 天的人力成本按最低 ¥200/h × 55 人时 ≈ ¥11,000。**云成本占预算的 0.1%**。

---

## 9. 「3 天最小管线」与「路演版」

| 组件 | 3 天最小管线（11/16–11/18） | 路演版（11/19–11/21） | 单点故障？ |
|---|---|---|---|
| 端侧 | ESP32-S3（xiaozhi-esp32 改）或树莓派兜底 | 同 + 热备机 | **是（唯一一顶帽子）** |
| 传输 | WebSocket + Opus，半双工 gate | + 断线重连 + 序列号去重 | 中 |
| ASR | **Transcribe Streaming zh-CN**（东京） | + fun-asr-realtime 备链路（自动切） | **是（无备即毁）** |
| LLM | **Claude Haiku 5.5 + Bedrock structured outputs（开场预热 schema）** | + Nemotron 3 Super 120B 交叉校验（拿 NVIDIA 分） | 否（模板句兜底） |
| TTS | **CosyVoice-v3.5-flash 指令音色**（北京）或 v3-flash 克隆（新加坡） | + 预录 10 句 + Polly Neural 英文彩蛋 | **是（音色是项目灵魂）** |
| 编排 | 笔记本 FastAPI 单进程 + 本地日志 | + 进程守护 + 一键离线开关 | 中 |
| 网络 | 现场 Wi-Fi + 手机热点 | + 4G 路由 | **是** |
| 存储 | 不落盘 | DynamoDB 存去标识结果 + 扫码页 | 否 |

**「一旦不可用就直接毁掉演示」排序**：① 现场网络 → ② TTS 服务/音色 → ③ 帽子本体（结构/电池/啸叫）→ ④ ASR → ⑤ LLM（有模板兜底，不毁）。
**处置**：为 ①②③ 各配一条**完全独立**的兜底（双路热点 / 预录 10 句 + 离线整段脚本 / 热备机），并且**彩排时必须演练一次「拔网线」**。这三件事的工时必须写进 11/17 的排期，而不是留到 11/18。

**不建议在 11/18 前做的**：Nova Sonic 端到端（4–6 小时，无中文）、火山接入（商务流程不可控）、ElevenLabs（贵且无额外收益）。

---

## 附录 A · 结论表

| 组件 | 选型 | 理由 | 3 天可用 | 单次成本 |
|---|---|---|---|---|
| ASR | **AWS Transcribe Streaming（zh-CN，东京）**，备 fun-asr-realtime | 中文流式已确认、$0.010/min、按秒计费、SDK 齐、拿 AWS 分 | ✅ | $0.0150 |
| LLM | **Bedrock Claude Haiku 5.5**（结构化输出）；校验模型 Nemotron 3 Super 120B | 人设最强最便宜；Nemotron 让 NVIDIA 分有真实用途 | ✅ | $0.00023 |
| TTS | **CosyVoice-v3.5-flash（指令控制，北京）**；备 v3-flash 克隆（新加坡） | 中文流式 + 风格指令 + $0.116–0.13/万字符；Polly 中文只有女声 Neural | ✅ | $0.0046–0.0052 |
| 兜底 TTS | Polly Neural Zhiyu（预录 10 句） | 断网/服务超时时不空手 | ✅ | $0 |
| 端到端语音 | **Amazon Nova Sonic 2.5 = 不用**（无中文） | 三代文档均无中文 locale；token 计费不可预估 | — | 未核实 |
| 编排 | 笔记本 FastAPI + WebSocket | 演示优先，不引入 API Gateway 冷启动 | ✅ | $0 |
| 合计 | | | | **≈¥0.14/次，100 次 ≈¥15** |

## 附录 B · 端到端时序表

见 **§5.2**（首字出声 ≈ 录音结束后 2.4 s，感知空白 1.2 s）。关键节点：VAD 尾点 400 ms → ASR 尾字 300 ms → LLM 首 token 900 ms → 首句（≤12 字）300 ms → TTS 首包 300 ms → 下行缓冲 140 ms。

## 附录 C · 未能核实清单

| # | 条目 | 尝试路径 | 处理 |
|---|---|---|---|
| 1 | Transcribe Streaming 端到端延迟数值 | 官方文档 / 计价页 | 无公开数值，写「待实测」 |
| 2 | 阿里 paraformer-realtime-v2 单价 | Model Studio 模型页 | 页面未列价 → 不写数字，只用家族内已核实的 fun-asr-realtime |
| 3 | 火山引擎（豆包语音）TTS/ASR 单价 | `volcengine.com/docs/6561/79823` | 页面为 JS 应用，仅取到能力目录（双向流式 TTS/声音复刻/音色设计/端到端实时语音），**无价** |
| 4 | Nova Sonic 延迟 | 模型卡 / 用户指南 | 仅 "low latency" 定性 |
| 5 | Nova Sonic 每秒音频对应 token 数 | nova 计价页 / 模型卡 | 未公布 → 单次成本无法精确折算 |
| 6 | CosyVoice-v3.5-flash 新加坡区价格 | 模型页 | 仅列北京区（$0.116/万字符） |
| 7 | ElevenLabs 中文逐语种支持 | 计价页（JS 渲染） | 仅取到 credit 规则（TTS 1 credit/字符）与档位价 |
| 8 | Inworld 中文（普通话）音色质量 | `inworld.ai/tts` | 官方称 ~500 语言，未逐条核实中文 |
| 9 | PIPL 条文原文（第 28/29/30/31/55 条） | npc.gov.cn（框架页，无正文）、cac.gov.cn（连接失败） | 按公开文本整理，**引用前须复核** |
| 10 | 《人工智能生成合成内容标识办法》条文细节 | cac.gov.cn / gov.cn（连接失败） | 仅按公开口径执行，条文未核实 |
| 11 | AWS 数据保留与「不使用客户数据训练」条款 | 未取 | 落地前查官方 Privacy/Data Protection 条款 |
| 12 | Transcribe 流式并发配额、Polly 免费额度 | 未取 | 演示并发=1，不影响；额度按 ¥0 估算更保守 |
| 13 | 汇率 ¥7.1/$ | — | **假设值**，非核实数字 |

**来源清单（全部为本次直接抓取）**：AWS — [Transcribe 支持语言](https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html)、[Transcribe 计价](https://aws.amazon.com/transcribe/pricing/)、[Bedrock 计价](https://aws.amazon.com/bedrock/pricing/)、[Bedrock 结构化输出](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html)、[Polly 音色表](https://docs.aws.amazon.com/polly/latest/dg/available-voices.html)、[Polly Generative 音色](https://docs.aws.amazon.com/polly/latest/dg/generative-voices.html)、[Nova 计价](https://aws.amazon.com/nova/pricing/)、[Nova 2 Sonic 模型卡](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-sonic.html)、[Nova 2.5 Sonic 模型卡](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-2-5-sonic.html)、[Nova Sonic 语言支持](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html)、[Nova 1 Sonic 概览](https://docs.aws.amazon.com/nova/latest/userguide/speech.html)；阿里云 — [cosyvoice-v3-flash](https://www.alibabacloud.com/help/en/model-studio/cosyvoice-v3-flash)、[cosyvoice-v3.5-flash](https://www.alibabacloud.com/help/en/model-studio/cosyvoice-v3-5-flash)、[paraformer-realtime-v2](https://www.alibabacloud.com/help/en/model-studio/paraformer-realtime-v2)、[fun-asr-realtime](https://www.alibabacloud.com/help/en/model-studio/fun-asr-realtime)、[qwen-flash](https://www.alibabacloud.com/help/en/model-studio/qwen-flash)；其他 — [DeepSeek 计价](https://api-docs.deepseek.com/quick_start/pricing)、[Inworld 计价](https://inworld.ai/pricing)、[Inworld TTS](https://inworld.ai/tts)、[ElevenLabs 计价](https://elevenlabs.io/pricing)。
