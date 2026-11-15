# 分院帽 · 上位机方案第三方复核

> A = `blind/input-A.md`（乙）；B = `blind/input-B.md`（甲）。只按内容判断。
> 基准：`统一准则`（最高事实源）＋`工程架构`＋`analysis/00-protocol.md`＋`可行性`；四份角度分析（`host/01~04`）作参照。
> `web_search` 401，外部事实用 GitHub API / 官方页直取，见文末"核实"。**结论：A 更像"能上台"，B 更像"能落地"；A 32/35，B 28/35。**

## 1 逐项打分（1–5）

| 维度 | A | B | 一句话理由 |
|---|---|---|---|
| 功能覆盖 | 5 | 4 | A 三层 26 项带"露馅度"，含故障注入六模式与静音救场；B 补了合规标识三处（§10 硬要求），但无救场与账本 |
| 设备接口完整性 | 5 | 4 | A 16 条七列含幂等/码表/`error` 双向/4 戳必填；B 握手头与码表更全，但 `bye` 写成单向、dev_ts"可选"、`error` 整条消失 |
| 技术选型 | 4 | 5 | A 的加权矩阵与五形态对比清楚，止于"2 路够用"；B 的 `websockets`/`max_queue`/CA 内嵌公钥/端口纪律是 22:30 能救命的旋钮 |
| 编排与降级 | 5 | 4 | A 四类超时×软硬×兜底×四级音色链，宣布预录、静音计时归上位机；B 的 9 格矩阵更好测，但宣布走实时 TTS、静音策略空缺 |
| 加分项真实性 | 4 | 4 | A 的 AWS"0 工时"最诚实、license 事实最精确，但 Kiro 记 2 h 低估；B 的 Kiro 4 h 合理、五条前置可证伪，但 I8 与 §6 自相矛盾 |
| 三天可行性 | 4 | 3 | A 的 judge 落在 G3 前、8 条 make 验收含反证，代价是无缓冲；B 有 3 h 显性缓冲，但 judge 晚于 G3 一天，且净增 ≈9 h 加分工作不在任何时间块里（实际 ≈36.5 h） |
| 风险与单点 | 5 | 4 | A 五条风险带触发信号，且有唯一的"人单点"（B 独占 key）；B 的多 worker 让反集中失效是好洞察，但缺人单点与概率/owner |

## 2 交叉比对

| 主题 | A 写了什么 | B 写了什么 | 冲突 | 采用 |
|---|---|---|---|---|
| 部署形态 | 1 容器 1 进程 2 端口；笔记本唯一上台，EC2 120 s 热备 | 同构 + non-root/read_only + CA 内嵌公钥 + 8080 只绑环回 | 否 | B 的容器/证书纪律 + A 的切备流程 |
| Provider 契约 | `open/push/events/abort` + `health/warmup`（同 02 §1） | 单一 `stream()` 异步生成器 + `arm/cancel/health`，理由是"push 完忘了读"会死锁 | 是 | A 的动词命名 + B 的取消语义（≤50 ms、幂等、不抛） |
| 预热与就绪 | `/readyz` 门禁；读超时 150 s；冷 ≤3 min、热 ≤40 s | 六步清单、任一项 fail 即 `exit 1`；目标"≤90 s 全绿" | 是 | B 的清单与 fail-closed + A 的 150 s；改"热 ≤90 / 冷 ≤180"。B 六步冷跑相加已 >90 s，目标自相矛盾 |
| **宣布句** | **8 句预录（4 院×2）为唯一路径**，实时 TTS 只做过桥句 | **实时 TTS 为主**（judge 后 2410→2660，预算 250/超时 800），预录为兜底 | 是 | **A**：02 §3.3 三处"只许预录"；B 的 250 ms 合成会让灯先变色、声后到 |
| 心跳与拔网 | 心跳 15 s；1.2 s 检测归设备（上行写失败+下行静默） | 500 ms 应用 ping；同一行又写"不承担 1.2 s 检测" | 是（B 内部也矛盾） | A；B 的"整秒旋钮"事实保留为注释，删 500 ms |
| `result` 与宣布 | judge 1500/2000，宣布串其后；`last_msg_id` 去重 | 明写"`result` 与 `tts{start}` 同 100 ms 内到" | 否 | B 的 100 ms 规则 + A 的预录（预录下三者天然同刻） |
| 存储与落盘 | `ingest.jsonl`+`final.jsonl`（sid join）+`profiles/` 24 h 删 | `final` 1 行+`ingest` N 行；断电只丢当前行；S3 只放 release | 否 | B 的"只丢当前行" + A 的 24 h 删；两版都缺"音频不落盘" |
| 大屏与档案页 | 5 层必有（定格 ≥8 s、断 SSE 1 s 轮询）；档案页可降级 | 5 层+页脚票数/AI 标识；档案页必须有（合规落点）；合规物料必须有 | 是 | B 的范围 + A 的验收判据；档案页"必须有，但是最后一个砍" |
| Nemotron 触发 | 低置信+预算 ≥900 ms 并发一次，永不阻塞 | `top1−top2<2` 或 `max<6` 且预算余 ≥900 ms，没回就按主判官 | 近似 | B 的阈值 + A 的表述；"预算余"无参照系，建议删在线分支 |
| TuyaOpen | 不接；license 为 Apache-2.0 缩短声明 591 B→NOASSERTION | 不接；五条前置全满足才谈，若接只接 ASR | 否 | B 的前置 + A 的 license（已复核） |
| 验收条目 | 8 条 make，含"跳过预热必红"、6 戳 <50 ms | 8 条命令，含 1008、iptables 后 1.2 s/5 s、abort <300 ms | 否 | 合 10 条：A 的 1/2/3/5/6/7/8 + B 的 2/5/6 |
| 错误码表 | 缺 `session_expired`、`rate_limited` | 10 码齐，但把 `session_expired` 放在 `bye` 行 | 是 | B 的集合 + A 的 `error` 双向行；`session_expired` 回 error |
| 时间基准 | 只在 `ready`/`bye` 各一次，中间线性插值（自称反对逐帧） | 随每个下行文本帧下发（=01 §2 #4） | 是 | B 逐帧；A 的两点法降为断流兜底 |
| 会话续期 | 仅一句"会话留 30 s 可续" | 零 | 都缺 | A 的方向 + 新增契约（§4） |

## 3 与基准事实的冲突

| # | 基准 | A | B | 判定 |
|---|---|---|---|---|
| 1 | snake_case（§3.1） | 全篇 snake ✓ | 全篇 snake ✓ | 两版都对；错在基准：00-protocol 通篇 camelCase，须回改并加 lint |
| 2 | `stt`/`abort`（§3.1） | ✓ | ✓，但 C1 要把信封 `t`→`type` | 都对；B 的改名撞 §3.4"只增不改"与 G2 冻结 |
| 3 | 8 戳 `t_arm…t5b` | `bye.dev_ts` 4 戳 + JSONL 8 戳 ✓ | 4 戳只在示例里，正文写"可选" | A 对；B 与 §3.2"缺一条作废"冲突 |
| 4 | TTFC 1.24/1.8/2.5 | 三层齐，但"t1→t4=780 ms"算错（200+350+250=**800**） | 三层齐，且点明"1.24 与 600/900/800 不能相加" | B 优；A 的 780 必须改 800 |
| 5 | 断网 1.2 s + 5 s 就绪 | 1.2 s ✓，全篇没有"5 s 按钮模式就绪" | 1.2 s 黄灯 + 5 s 出声（验收 #6） | B 对（=§6.2 第 5 步）；A 丢了一个 DoD 数字 |
| 6 | G0–G8 | 11/17 晚写"G3 交付"（G3=11/16 23:30） | "tag g3"打在 11/18 15:00（应为 G6） | 都错一格；九处 RFC（A 3+B 6）须压在 G4 前 |
| 7 | 六态（§7.5） | 用 ARMED/ERROR，未提态数 ✓ | 写"五态切换的唯一外部输入" ✗ | B 错；`工程架构 §3.3` 标题也写"5 个"却列 6 个，以 §7.5 为准 |
| 8 | 7 个旧码 | 缺 `session_expired`、`rate_limited` | 齐，但位置错 | B 覆盖好；位置改 |
| 9 | 判决不进模型 | argmax+×0.85+编辑距离 ≤2+3 连强制换+兜底打分 | 只有"judge 纯函数（argmax/反集中/引原话）" | A 可验收，B 只是承诺 |
| 10 | `bye` 双向（§3.6） | 双向 ✓ | 云→设；C3 主张"只看 close code" | B 错：§7.5 摘下要 `abort`+`bye{doff}`，close 分不出 doff/timeout |
| 11 | 未知即忽略（§3.4） | 未写 | 明写"静默丢弃并计数、不许回 error"+单测 | B 对，A 缺（协议 lint 会红） |

另：A 的 C1 称"准则 §3.2 要求逐帧"、C3 称"准则 §3.6 已写 ping 不承担 1.2 s"——**准则里没有这两句**（分别在 `01 §2 #4`、`01 #14`）。引错文比改错值更危险。

## 4 两份都没写的服务（上位机对下位机）

| 服务 | A | B | 必须补 | 致命度 |
|---|---|---|---|---|
| 会话续期与幂等 | 一句"30 s 可续" | 零 | 重连带 `sid`、服务端留 30 s 上下文、重放未确认 `result`、新 sid 换 `last_msg_id` 前缀 | 高 |
| 设备重启账本 | 引 §8.3 + `announced` 不发 `result` | 零（只靠 JSONL 重建） | 账本 8 字段 + `hello`/续期上报 `announced`/`boot_id`；SPEAKING 掉电不重播、THINKING 掉电回 ARMED（§8.3 两条验收进 G8） | **最致命（重复宣布=当场穿帮）** |
| 时间基准回写 | ready/bye 两点 | 逐帧 | 逐帧 + Δ 首帧基线 + 漂移 >500 ms 记 `clock_skew` 并落库 | 中 |
| 限流与背压 | 只标"可降级"，无机制 | `max_queue`/`write_limit`，429→Nova Lite | 2 帽并发上限、单 IP 10 会话/分（00 §6）、429 不退避直走 partial-as-final | 中 |
| 配置热更新边界 | 按 `version` 弃旧，无生效点 | 同 | 三类生效点：音量/尾点立即；灯色下一次 SPEAKING；prompt/台词下一会话；会话中拒改并回 `rejected[]` | 高 |
| preheat 失败处理 | 门禁 + 150 s + "跳过必红" | 任一项 fail 即 exit 1 | 分级：L0 拒上台（ASR/TLS/schema），L1 降级上台（TTS→Polly、Nemotron 跳过）；`preheat_age_ms` 门限 | 高 |
| 管理面鉴权 | 零（`/metrics`、`/readyz`、`halt` 裸奔） | 零（`/v1/preheat`、`/v1/replay`、`/v1/config` 裸奔） | `X-Admin-Token` + 反代只暴露 `/v1/voice`（01 §3）+ `kill` 的 drain 语义 | 高 |
| 日志脱敏 | 零 | 仅"fixture 采集/脱敏"一处 | 音频不落盘、`stt.text` 存哈希+长度、原话上屏需 `consent.share`（§10 / 04 §6） | 高 |
| 备用端点切换 | 只有服务器侧 120 s 切 | NVS 双端点+备用域名，切 ≤3 s | 补触发判据（谁判笔记本死）+ 切换后 sid 处理 + SAN 覆盖两端点 | 中 |

## 5 加分项：谁真用、谁硬凑

| 项 | 判定 | 证据够不够 | 合并注意 |
|---|---|---|---|
| Kiro | **真用**（开发期） | 够：两版同形态（`.kiro/specs/` 三文件 + steering 禁令 + 每 task 一 commit `Refs: G2` + reports） | 取 B 的 4 h（A 的 2 h 做完 spec+3 adapter+契约测试偏乐观）；两版都禁止它碰 `judge/` 与 `prompt.md` |
| AWS | **真用**（运行时） | 够：Transcribe/Bedrock/Polly 在主链路；A 的"0 工时"诚实，B 的"6 h 净增 2"含混 | 别为加分搬 Fargate/Lambda（两版都否决，对） |
| Nemotron | **半真**：只做对照 | 够（n≥20 + 裸一致率 + κ），但两版都留了在线分支 | **删在线分支**：并发=双倍 token、与主判官抢 Bedrock 配额（429 会打主判官）、预热多一次 90 s 级 schema 编译；且"预算余 ≥900 ms"没参照系 |
| TuyaOpen | **硬凑**（两版都判不接） | A 的 license 最精确（591 B/NOASSERTION）；B 的五条前置最可证伪 | 只留 `docs/eval/tuya.md`；赛方发已烧 license 的板才做第三顶帽子，且只接 ASR |

## 6 给第四人的合并建议

| 章 | 采用 | 必须新增 |
|---|---|---|
| 1 一页纸 | A 的三角色 + 五数表 | 补 TTFV（A 缺）与 ¥0.145（B 缺） |
| 2 功能清单 | A 的三层 26 项骨架 + B 的合规物料/票数页脚 | 账本、续期、鉴权、脱敏四项 |
| 3 接口全表 | A 的 16 条七列为骨 | 并入 B 的握手头/逐帧时间基准/10 码；`error` 与 `bye` 都双向、六态、dev_ts 必填 |
| 4 技术选型 | B 的容器/证书/端口纪律 | A 的五形态对比与"不做平台"边界 |
| 5 编排与降级 | A 的四类超时+音色链+静音归上位机 | B 的 9 格矩阵与"两列不能相加"、B 的六步预热 + A 的 150 s |
| 6 加分项 | A 的 AWS 0 工时 + B 的五条前置 | 删 Nemotron 在线分支 |
| 7 三天计划 | A 的 G3 前完成 judge + B 的缓冲与逐块出口判据 | 把 ≈9 h 净增加分移出关键路径 |
| 8 风险与单点 | A 的人单点 + B 的多 worker/时钟跳变 | 合并去重成一张表 |

**三条合并时不能丢的硬规定**

1. **判决权不进模型**：`house=argmax(scores)`＋连续 3 次同院 ×0.85＋第 4 人强制换院＋引原话编辑距离 ≤2；Kiro 不许生成 `judge/` 与 `persona/prompt.md`。
2. **宣布只许预录，且 `result`/`tts{start}`/首帧同刻（≤100 ms）**：8 句入库，实时 TTS 只做过桥句；宣布失败的唯一退路是下一条预录，不许 Polly。
3. **一份账本、一条时间轴**：设备 NVS 账本与服务端 JSONL 用同一 `sid`+`last_msg_id` 对齐，`announced=true` 重启只亮灯不重播；8 戳 >200 ms 本次作废、>500 ms 记 `clock_skew`。

> **核实（2026-11-15）**：① [Bedrock 结构化输出](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) 逐字命中"up to approximately 90 seconds""cached for 24 hours"、optional ≤12／union ≤16、`additionalProperties:false`，且要求"client read timeout to at least 120 seconds"——A 的 §8.4 与 150 s 有据，B 的"≤90 s 全绿"会被判成超时。② xiaozhi `docs/websocket.md`（GitHub API 取全文，sha `d7cdefb` 与 B 引用一致）：按 `type` 分发、v1 裸 Opus、v2 带 timestamp、v3 为 type+reserved+payload_size（共 4 B，B 写"1+2"不精确）、无 `bye`、无 `ping`。③ TuyaOpen：`LICENSE` 591 B 的 Apache-2.0 缩短声明、SPDX `NOASSERTION`、1948★、11-13 仍在提交——A 对。④ `esp_websocket_client.h`：`size_t ping_interval_sec`（default 10）、`pingpong_timeout_sec`、keepalive 5/5/3——B 的"整秒、无 1.2 s 档"成立。⑤ 仓库数：xiaozhi-esp32 33,258★/694 issues/MIT；xiaozhi-esp32-server 11,302★/JavaScript/MIT-均对。**需核实**：Polly 单价、CosyVoice 24 kHz 与 `instruction`、Bedrock 上 Nemotron 的 model id 与中文 JSON 稳定性、涂鸦首包延迟（`raw.githubusercontent.com` 被拦，改用 API 取文）。
