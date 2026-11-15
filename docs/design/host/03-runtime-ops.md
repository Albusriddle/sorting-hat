# 分院帽 · 上位机 03 · 运行形态、部署与工程化

> 评审角色：运行形态 / 部署 / 工程化（上位机 owner = B）。时间口径：3 天、3 人、笔记本演出、手机热点、60–90 s 一会话、10 次连演不崩。
> 已读：`统一准则`（§1/§3/§4/§6/§8.1）、`工程架构` §4/§7、`可行性与实施方案` §7。**注：该文只有 §7.1–§7.3，无 §7.5；"可达性兜底"取 §11.3 与附录 C 的 P2「现场 8883/443/WS 可达性」。**
> 价格来源：`b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/...`（aws.amazon.com 计价页数字的真实来源）与 `pricing.us-east-1.amazonaws.com/offers/v1.0/aws/*`（官方 Price List），2026-11-15 抓取；区域 **ap-northeast-1（东京）**、Linux、按需、USD。汇率 ¥7.1/$ 只用于量级，不进提交材料。

---

## 0. 一页结论

| 决策 | 结论 | 理由（一句话） |
|---|---|---|
| 唯一推荐 | **① 笔记本本地（Docker Compose 单容器）+ 模型走云** | 三个 adapter 本来就是 SaaS，所以"本地"天然等于"混合"；唯一变量是**网关在哪**，本地=延迟最低、断网可控、¥0 |
| 备选 | **③ EC2 t4g.small 跑同一镜像** | `$0.0216/h`，停机不花钱，换机器=换一台笔记本；作热备与路演 |
| 明确否决 | ④ Fargate、⑤ API GW+Lambda、⑥ 自建 EMQX | 分别死于"多一层 ALB 就比 EC2 贵 2.4×"、"有状态长连接用 Lambda 是反模式"、"协议已冻结为 WSS，换 MQTT 要动固件" |
| 进程 | **1 容器 / 1 进程 / N 个 asyncio 任务** | 3 天里每多一个进程，就多一处 22:30 要修的东西 |
| 端口 | 8443 WSS（设备面，`0.0.0.0`）/ 8080 HTTP（大屏面，`127.0.0.1`） | 两个面两个口，大屏不对外暴露 |
| 起服务 | `make up` →（自动等）`/readyz` 全绿 | 目标 **90 s 内可上台**；离线镜像已 load 时实测 40 s |
| 成本 | 演示 3 天 **≈¥18–76**；赛后常驻 1 月 **≈¥290** | 云模型占八成，基础设施不构成成本项 |
| 最可能翻车 | ①热点+防火墙使设备连不上 8443；②没预热就上台（schema 首编译 90 s） | 见 §7.3 |

---

## 1. 部署形态决策矩阵

**结论：① 唯一推荐，③ 作备选，④⑤⑥ 否决。** 关键判断：本项目"本地/混合"的分界不在模型（模型永远在云），而在**网关进程跑在哪**。

| # | 形态 | 延迟 | 可控性 | 现场网络依赖 | 故障恢复 | 成本 | 3 天工时 | 判定 |
|---|---|---|---|---|---|---|---|---|
| ① | 笔记本本地（compose） | **最优**：设备→网关同热点一跳，t1 抖动 <5 ms | 高：改代码即生效，日志在本地 | **只依赖热点能否出口到云**：ASR/LLM/TTS 三段 | 重启容器 5 s；换机 2 min | **¥0** | **4–6 h**（含镜像与离线包） | ✅ **唯一上台形态** |
| ② | 混合（笔记本网关 + 云模型） | 同① | 同① | 同① | 同① | ¥0 + 云模型 | 同①（**不额外花工时**） | ✅ 与①合并，不单独实施 |
| ③ | EC2 t4g.small | 东京往返 +30–60 ms；TTFC 增 ~60 ms，仍在 1.8 s 内 | 中：SSH + 同镜像，但改代码要重启重建 | 只要热点能上网就行（**不依赖笔记本**） | 实例重启 40 s；换 IP 要改设备端点 | $0.0216/h，演示期 ~$0.4 | +3–4 h（安全组/证书/镜像推拉） | ⭕ **备选**：热备与路演 |
| ④ | Fargate | 同③ + 任务冷启动 30–60 s | 低：镜像必须走 ECR，改一行也要 push | 同③ | 需 TaskDef/ALB/目标组/安全组四件套 | 0.5vCPU/1GB ARM 730h = **$18.0** + **ALB $17.7** + LCU ≈ **$38/月** | +8–10 h | ❌ **否决**：比③贵 2.4×，且演示期无收益 |
| ⑤ | API GW WebSocket + Lambda | **不可控**：每消息一次调用，冷启动（百 ms 级）落在关键路径 | 低：会话状态要外置到 DynamoDB，每帧一次读写 | 同③ | 好（无服务器） | 1000 会话 ≈ **$6.9/月**（最便宜） | +10–12 h 且大概率调不通 | ❌ **否决**：见下 |
| ⑥ | 本地 EMQX / 自建 broker | 好（本机） | 低：多一进程、一套 ACL、一份许可 | 无改善 | 多一个可挂的组件 | 0 元 + 工时 | +6–8 h | ❌ **否决**：见下 |

**③ 的数字**：`t4g.small`（2 vCPU / 2 GiB，Linux，东京，按需）= **$0.0216000000/h**（官方 Price List `APN1` Linux 共享型）。
**④ 的数字**：Fargate 东京 x86 `$0.05056/vCPU-h + $0.00553/GB-h`，ARM `$0.04045/vCPU-h + $0.00442/GB-h`；ALB 东京 `$0.0243/h` + `$0.008/LCU-h`。
**⑤ 的钱**：WS 消息 `$1.26/百万`、连接分钟 `$0.315/百万`；Lambda 东京 `$0.0000002/请求`、`$0.0000166667/GB-s`。

**否决⑤的理由（不是钱）**：90 s 会话按 60 ms 一帧 ≈ 1500 上行 + 1500 下行 = **3000 条消息**；API GW 一条消息一次 Lambda 调用，会话状态只能塞进 DynamoDB（每帧一次读写），而 TTFC 上台线是 1.8 s——多一次冷启动就没了。规程要"一路流式合成 20 秒音频"，这是**有状态长连接**，Lambda 的模型与之相反。3 天内不存在把它调通的路径，故否决；答辩里写"评估过、不适用"。

**否决⑥的理由**：协议在 G2/G4 已冻结为 **WSS + JSON 控制帧 + 二进制 Opus 帧**，换 MQTT 要改 `fw/net/proto.c` 与设备状态机，等于推翻 A 的固件与 6 时间戳可观测性。EMQX 只解决"消息怎么送到"，不解决"ASR→LLM→TTS 怎么编排"，而后者才是上位机的全部工作。其仓库许可证字段是 `Other/NOASSERTION`（GitHub API 实读，与 TuyaOpen 同一个坑）——**收益 0，风险非 0**。

**②不单独列**：三个 adapter 都是云 API，"本地"本身已是混合；拆开只会让人以为有两条路径。凡"本地跑模型"（FunASR/TTS）一律只做断网兜底——笔记本上中文 TTS 首包 ≥1.5 s 就打穿上台线。

---

## 2. 进程与容器

**结论：一个容器、一个进程（uvicorn + 多 asyncio 任务），两个端口，三类检查，一个退出路径。** 不拆微服务不是拆不开，而是**每个独立进程都要一份 supervisor 配置、一个端口、一条日志路径和一次 22:30 的排障**。

| 项 | 规定 | 判据/命令 |
|---|---|---|
| 进程模型 | `host/app/main.py` 单进程：`ws_gateway` + `orchestrator` + 3 adapter + `judge` + `storage` + `console` 都是同进程内的模块 | `ps` 只有 1 个 python |
| 容器 | `sortinghat-host:<tag>`，`python:3.12-slim` 基底，`init: true`（tini 收尸 + 正确转 SIGTERM） | `docker compose ps` 1 个 running |
| 端口 | **8443/tcp** WSS 设备面（`0.0.0.0`）；**8080/tcp** HTTP 大屏面（**只绑 `127.0.0.1`**） | `ss -ltnp` 两条 |
| 健康检查 | `/healthz`：进程活 + 事件循环滞后 <200 ms（>500 ms 返 503）。`/readyz`：ASR 连接、Bedrock schema 已编译、TTS 会话已开、persona 已加载、最近一次成功会话 <10 min，逐项返 JSON | `curl -fsS localhost:8080/readyz` |
| 容器健康检查 | `interval 10s / timeout 3s / retries 3 / start_period 40s` | `docker inspect --format '{{.State.Health.Status}}'` |
| 优雅退出 | SIGTERM → 停接新 WS（回 `bye{reason:"fault"}` + close 1001）→ 等在播句 ≤5 s → flush JSONL → exit 0 | `stop_grace_period: 10s` |
| 崩溃重启 | `restart: unless-stopped`；容器内**不再叠 supervisor**（PID 1 已是 uvicorn，多一层只增排障面） | `docker events` 看 restart |
| 开机自启 | Windows 演示机：任务计划程序 `onlogon` 跑 `docker compose up -d`（**不要**用 `onstart`，Docker Desktop 要先起）；Linux 备机 systemd `After=docker.service` | 重启后 60 s 内 `/readyz` 绿 |
| 日志落盘 | 应用 JSONL：`./var/log/YYYYMMDD/session-<sid>.jsonl` 与 `./var/log/YYYYMMDD/host.jsonl`（bind mount，重建不丢）；容器 stdout：compose `json-file max-size 50m max-file 3` | `ls var/log/$(date +%F)` |
| 时区 | 容器 `TZ=Asia/Shanghai`，JSONL `ts` 带 `+08:00`；单调时钟一律 ms | 抽样 3 行看偏移 |

**为什么单进程够**：每会话带宽 ≈20 kbps，10 路并发也只有 ~400 kbps；CPU 花在 Opus 透传与 JSON 编解码，单进程 10 路余量充足（§5 判据 RSS <400 MB、CPU <70%）。多 worker 会拆散"每会话上下文"，让反集中计数（连续 3 次同院 ×0.85）失效——**这是功能约束，不只是性能约束**。

---

## 3. 一条命令起服务

**结论：`make up` 一条命令，90 s 内 `/readyz` 全绿；`.env.local` 共 6 组 44 个键，一个都不许硬编码。**

| 步骤 | 命令 | 预期 | 失败即停 |
|---|---|---|---|
| 1 | `docker load -i release/offline/host-g5.tar.zst`（首次/换机） | 15–40 s | 镜像 SHA 对不上 |
| 2 | `cp .env.example .env.local && vi .env.local`（首次） | — | 缺键 → 启动即报错退出（**不做默认值兜底**） |
| 3 | `make up` = `docker compose --env-file .env.local up -d` | 10–25 s | 端口占用/证书读不到 |
| 4 | 自动等 `/healthz` → `make ready`（轮询 `/readyz`，120 s 上限） | 30–60 s | 任一依赖红 → 打印那一项 |
| 5 | `make preheat`（Bedrock schema 空跑、TTS 建会话、ASR 试连） | 20–90 s（首编译最长 90 s） | 超时说明密钥/额度/区域 |
| 6 | 手机热点开、设备上电 → 看是否 `ready` | ≤3 s | 见 §7.3 |
| 7 | `make smoke`（3 条 fixture 回放 + 三 adapter 各一发） | 40 s，<¥0.01 | `house` 变了即红 |

**`.env` 键（全）**

| 组 | 键 |
|---|---|
| 网关 | `COMPOSE_PROJECT_NAME` `TZ` `GATEWAY_BIND`(0.0.0.0) `WSS_PORT`(8443) `HTTP_PORT`(8080) `TLS_CERT_PATH` `TLS_KEY_PATH` `ALLOW_INSECURE_WS`(默认 0，调试才 1) |
| 鉴权 | `DEVICE_TOKEN_FILE` `TOKEN_TTL_H` `ADMIN_TOKEN`(大屏/统计) `AUTH_FAIL_BURST`(5/min) |
| AWS | `AWS_REGION`(ap-northeast-1) `AWS_ACCESS_KEY_ID` `AWS_SECRET_ACCESS_KEY` `AWS_SESSION_TOKEN`(可选) `AWS_PROFILE`(本机可选) |
| 三个 adapter | `ASR_PROVIDER` `ASR_LANG`(zh-CN) `ASR_TIMEOUT_MS`(600) `LLM_PROVIDER` `LLM_MODEL_ID` `LLM_MAX_TOKENS` `LLM_TIMEOUT_MS`(900) `LLM_SCHEMA_ID` `TTS_PROVIDER` `TTS_VOICE_ID` `TTS_INSTRUCTION` `TTS_TIMEOUT_MS`(800) `POLLY_VOICE`(Zhiyu) `ALI_ASR_KEY`(备链) |
| 编排 | `SESSION_MAX_S`(95) `SILENCE_PROMPT_MS`(6500) `PING_INTERVAL_MS`(500) `PONG_DEADLINE_MS`(400) `ANTI_CLUSTER_FACTOR`(0.85) `ANTI_CLUSTER_STREAK`(3) |
| 观测与运维 | `LOG_DIR` `LOG_LEVEL` `METRICS_ENABLED` `REDACT_TEXT` `SESSION_RETENTION_D` `DEMO_MODE` `COST_LOG` |

**密钥怎么存**：只在 `.env.local`（`chmod 600`）与 CI secrets；**`.env*` 进 `.dockerignore`**，镜像里永远没有密钥（`docker history` 可验）；`gitleaks` pre-commit 拦 `AKIA`/`sk-`；纸质封存一份给 A，C 持只读副本（对应 `统一准则` §8.1 的 B 单点）。3 天内不用 Vault/Docker secrets——单机收益为零。

**离线镜像**：`docker save sortinghat-host:g5 | zstd -19 > release/offline/host-g5.tar.zst`（估 150–200 MB，基底 130 MB）；同时备 `pip download -r requirements.txt -d release/offline/wheels`（~80 MB，native 应急通道）；两份进 U 盘 + 第二台机，**11/20 彩排 3 必须在第二台机 load 成功一次**并写 `SHA256SUMS`。

---

## 4. 观测

**结论：4 个黄金信号的定义见下表；6 时间戳拆 `ingest`/`final` 两行落盘、用 `sid` join；不装 Prometheus。**

| 黄金信号 | 本题定义 | 采集点 | 观察窗 |
|---|---|---|---|
| 延迟 | **TTFC（t5b−t0）p50/p90**、TTFV（t5a−t0）、分段 t1→t2→t3→t4、事件循环滞后 | 会话结束由 `final` 行计算 | 单会话 + 滚动 10 次 |
| 流量 | 并发会话数、每小时会话数、上/下行帧率、字节/会话（估 ~0.7 MB）、换人时长 | 网关计数器，`/stats` 返 JSON | 1 min 滚动 |
| 错误 | 8 个错误码计数、`degrade` 非空占比、WS 重连率、超时率、`house` 缺失率 | 每次 catch 一次计数 | 5 min 窗口 |
| 饱和 | CPU%、RSS、FD 数、JSONL 写盘 p99、上游并发流占用（ASR/TTS 各限 N 路）、磁盘剩余 | 进程内 5 s 采样 | 1 min |

**6 时间戳落哪（两行结构）**

| 戳 | 产生方 | 落点 | 说明 |
|---|---|---|---|
| `t_arm` | 设备（单调 ms） | `final.device.t_arm` | 只做上下文，不算指标 |
| `t0` | 设备 | `final.t0` + 随 `result.latency` 回传 | TTFC 起点 |
| `t1` | 网关 | `ingest.t1`（**立即写，防丢**） | 末帧到达 |
| `t2` `t3` `t4` | 三个 adapter | `ingest.t2/t3/t4` | 分段归因 |
| `t5a` `t5b` | 设备 | `final.t5a/t5b` | 设备在 `bye` 前回传；2 s 未到写 `final_fallback` 并标 `recovered:false` |
| `recv_wall` | 网关（UTC） | 两行都有 | 与设备单调钟对账：>200 ms 本次作废，>500 ms 记 `clock_skew` |

**日志字段**：`ts`（带 +08:00）、`ev`、`level`、`sid`、`dev`、`boot_id`、`seq`、`code`、`degrade`、`dur_ms`、`ttfc_ms`、`house`、`text_sha8`、`text_len`、`cost_usd`、`ok`。音频**永不落盘**，`text` 默认只存哈希与长度。

```json
{"ts":"2026-11-21T14:03:12.481+08:00","ev":"session.final","level":"info","sid":"s7f3a","dev":"hat-02","boot_id":41,"t_arm":118234,"t0":142880,"t1":142962,"t2":143350,"t3":144010,"t4":144480,"t5a":143100,"t5b":144930,"ttfv_ms":220,"ttfc_ms":2050,"house":"courage","scores":{"敢":7.1,"要":4.4,"想":6.0,"守":5.2},"anti_cluster":false,"degrade":null,"asr_chars":37,"text_sha8":"9c1f0ab3","clock_skew_ms":12,"providers":{"asr":"transcribe","llm":"bedrock/haiku","tts":"cosyvoice"},"cost_usd":0.0204,"ok":true}
```

**告警阈值（`make watch` 每 5 s 轮询 `/stats`，只做三档灯，不接 Alertmanager）**

| 档 | 条件（5 min 窗口） | 动作 |
|---|---|---|
| 绿 | 错误率 <2% 且 TTFC p90 ≤1.8 s | 无 |
| 黄 | 错误率 ≥5% 或 TTFC p90 >2.5 s 或 `degrade` 占比 >20% | 大屏变黄；`make preheat` 重跑；不切备 |
| 红 | 错误率 ≥20% 连续 2 窗口，或 `/readyz` 连续 3 次失败 | 大屏红 + 15 s 内切按钮模式（`make fallback-btn`） |
| 单会话看门狗 | TTFC >4 s | 主动 `abort` + 预录收尾，记 `degrade=ttfc_watchdog` |

**大屏只显示 6 个数**：① 本轮 TTFC（与秒表对账过的那次）；② 本次学院（四院色）+ 引用的那句原话；③ 10 次 TTFC 的 p50/min/max；④ t0→t5b 分段条；⑤ 今日会话数 + 四院分布条（任一 ≤40% 才变绿）；⑥ 状态灯 + 三个 adapter 的连接点。**不显示**：token、原始转写、scores 明细（看不懂且涉隐私）。

---

## 5. 故障注入与压测

**结论：五类故障全部用应用层开关注入（可进 CI、可读、不烧钱），拔网用真拔；10 并发不是上台判据，串行 10 次才是。**

| 故障 | 注入方式 | 期望（通过判据） |
|---|---|---|
| ASR 超时 | `FAULT_ASR=timeout:5000`（adapter 包一层 sleep 后抛） | 600 ms 到点 → 「我没听清，再说一次？」+ `asr_timeout`；不卡状态机，5 s 内回 ARMED |
| LLM 5xx | `FAULT_LLM=5xx:100` | 重试 2 次（1/2 s 退避）→ 模板首句 + 兜底打分；`house` 仍产出且非空；记 `upstream_5xx` |
| TTS 断连 | `FAULT_TTS=drop:300`（首包后 300 ms 断 socket） | 800 ms 内切 Polly → 再切预录；音色变、句子完整；记 `tts_timeout` |
| 拔网 | 关热点 / 飞行模式 | 设备 **1.2 s** 内黄灯（500 ms ping ×2 + 200 ms 余量，**不能靠 15 s 心跳**）、**5 s** 内按钮模式播完一句；网关不崩；重连后新 `sid` |
| 限流 | `FAULT_LLM=429:100` | 退避 + `rate_limited` + 提示句；不无限重试（≤2 次） |

**10 并发要不要**：**不作验收项**。现场同时只有 1–2 顶帽子；"10 次连演不崩"指**串行 10 次**（每次 60–90 s + 20 s 换人 ≈ 15 min），观察泄漏与状态污染，不是吞吐。并发只做两件：① 2 路同连验证不串音；② 10 路压 3 min 作余量证据，只设资源判据。

**压测怎么跑**：`python tools/loadtest.py --clients 10 --fixture fixtures/session-g2.ndjson --ramp 2s --duration 180s --report var/loadtest-<ts>.json`，上游走 cassettes 回放（不烧钱、可重复）；真云只跑 2 路各 1 次。

| 判据 | 值 |
|---|---|
| 串行 10 次 | 10/10 出 `house`；TTFC p50 ≤1.8 s、p90 ≤2.5 s；RSS 增量 <50 MB；FD 不增长；四院任一 ≤40% |
| 2 路并发 | 无串音（两 `sid` 的 `house` 与理由互不污染），TTFC 差 <300 ms |
| 10 路压测 | p95 帧转发 <50 ms；RSS <400 MB；CPU <70%；零帧乱序；每会话 `house` 与 fixture 一致 |

---

## 6. 安全

**结论：设备侧只认 token + 证书钉扎，服务端只给四条 API 权限，日志默认不存文字，演示账号与开发账号物理隔离。**

| 项 | 做法 | 证据 |
|---|---|---|
| 设备 token | 32 B 随机，**NVS 首次配网写入**，不进固件源码；服务端只存 `sha256` 前缀表 | `make smoke` 用错 token 被拒 |
| 轮换 | 配网模式重写；旧 token 立即失效；失败 5 次/分钟封 IP 5 min | 日志 `auth_failed` 计数 |
| 服务端密钥 | `.env.local` 600 + 纸质封存 + C 持只读副本；镜像内无密钥（`.dockerignore`） | `docker history` 无 `AKIA` |
| IAM 最小权限 | 只四条：`transcribe:StartStreamTranscription`、`bedrock:InvokeModelWithResponseStream`、`polly:SynthesizeSpeech`、`logs:PutLogEvents`（限定 log group ARN）；**不用 `*`**；迁云后改用实例角色，不用长期 AK | 策略 JSON 截图 |
| TLS | 自签 CA（10 年）+ 服务端证书（1 年，SAN 同时写 `IP:192.168.43.x` 与一个备用域名）；固件内嵌 **CA 公钥**（不是指纹，换机不用重烧）；`ALLOW_INSECURE_WS` 只在调试为 1 | `openssl s_client` 握手 + 设备侧拒绝错证 |
| 容器 | non-root(10001)、`read_only` 根 + `tmpfs /tmp`、只挂 `var/log` 与 `certs`、`cap_drop: ALL`、不用 `network_mode: host` | `docker inspect` |
| 日志脱敏 | 音频只在内存环形缓冲，**永不落盘**；`text` 默认 `<redacted sha8 len>`；明文只进 `fixtures/private/`（.gitignore）；logger 正则替换 `AKIA`/`sk-`/`Bearer` | 抽 100 行 grep 无明文 |
| 演示账号隔离 | `demo` 与 `dev` 两个 IAM user/两个预算告警（$10）；demo key 演示前 1 天才建、演示后 24 h 内禁用 | 两账号账单截图 |
| 合规 | 现场一句话告知 + 二维码；大屏标「AI 合成语音」 | `统一准则` §10 |

---

## 7. 备份与切换

**结论：三层备份（离线包 / 第二台笔记本 / EC2 热备），切换目标 ≤2 min，11/20 彩排 3 必须实测计时。**

| 备份项 | 内容 | 频率 | 校验 |
|---|---|---|---|
| 镜像与依赖 | `host-g5.tar.zst` + `wheels/` + `SHA256SUMS`（U 盘 ×2） | 每次 tag | 第二台机 `docker load` 成功 |
| 第二台笔记本 | 同 compose 文件 + 独立 `.env.local`（独立 key） | 11/20 前装好 | 独立跑通一次完整会话 |
| 4G 热点 | 两台手机、两家运营商；**两个 SSID/密码都写进设备 NVS** | 常年 | 备热点 30 s 内可开 |
| 云端备用 | EC2 t4g.small 预装同镜像，安全组只开 8443；设备 NVS 存**两个 WSS 端点**（primary=笔记本 LAN IP，secondary=EC2 域名） | 演示前 1 天起 | 断笔记本后 3 s 内自动切 |

**切换时间表（目标 120 s）**

| 时刻 | 动作 | 累计 |
|---|---|---|
| T+0–10 s | 判故障：大屏红 / 设备无 `ready` / `/readyz` 连续失败 | 10 s |
| T+10–30 s | 旧机 `make down`（或直接断电，容器 `unless-stopped` 不重启） | 30 s |
| T+30–90 s | 新机 `make up && make ready`（镜像已 load，40 s 实测） | 90 s |
| T+90–110 s | 设备重连（退避 1/2/4/8 s）+ `make smoke` 一条 happy fixture | 110 s |
| T+110–120 s | 大屏确认绿；口头报「已切换」 | **120 s** |

**§7.3 现场最可能翻车的两点**：① **热点 + Windows 防火墙/Docker 端口转发**——设备拿到的 `192.168.43.x` 会变，证书 SAN 或入站规则没跟上就进 3 s 超时重连循环；对策：SAN 写两个常见网段 IP + 备用域名，放行入站端口，开场前 `curl -k` 自测；② **没预热**——Bedrock 新 schema 首编译最长 90 s、TTS 会话未建，第一场直接超时；对策：`make preheat` 进 §3 第 5 步，彩排 3 专门演一次"跳过预热"看它怎么坏。

---

## 8. 成本

**结论：演示 3 天 ¥18–76，赛后常驻 1 月 ¥290 量级；钱不是约束，别为省钱改架构。**

**演示 3 天账**

| 项 | 数量 | 官方单价 | 小计 |
|---|---|---|---|
| 笔记本本地（①） | 3 天 ×8 h | ¥0（电费 ≈¥0.6/天） | **¥0** |
| 云模型（ASR+LLM+TTS） | 100–500 次 × $0.0204 | $0.0204/次 | $2.0–10.2 ≈ **¥14–72** |
| EC2 热备（仅彩排+上台时段） | 18 h | $0.0216/h | $0.39 ≈ ¥2.8 |
| 公网出口 | 0.5 GB | $0.114/GB | $0.06 ≈ ¥0.4 |
| CloudWatch Logs | 0.05 GB | $0.76/GB | $0.04 |
| **合计** | | | **≈¥18–76** |

**赛后常驻 1 个月（730 h）**

| 项 | 数量 | 单价 | 小计 |
|---|---|---|---|
| EC2 t4g.small | 730 h | $0.0216/h | $15.77 |
| EBS 根卷 20 GB | 1 | **需核实**（估 $1.6） | ~$1.6 |
| CloudWatch Logs | 5 GB 摄入 | $0.76/GB | $3.80 |
| 公网出口 | 10 GB | $0.114/GB | $1.14 |
| 云模型 | 1000 次 | $0.0204 | $20.40 |
| **合计** | | | **≈$43/月 ≈¥305**（不含 EBS） |

**三形态同口径对照（730 h，含 1000 次会话）**

| 形态 | 基础设施 | 合计 | 判定 |
|---|---|---|---|
| ① 笔记本 | ¥0（电费 ~¥18/月） | **¥145/月**（只有模型） | 演示期最优 |
| ③ EC2 t4g.small | $20.7 | **$41/月 ≈¥291** | 赛后最优 |
| ④ Fargate 0.5vCPU/1GB+ALB | $38.5 | $59/月 ≈¥419 | 贵 1.4×，无收益 |
| ⑤ API GW+Lambda（3M 消息/月） | $6.9 | $27/月 ≈¥192 | 最便宜，**延迟否决** |

带宽：Opus 单会话上下行 ≈0.7 MB，1000 次 ≈0.7 GB——不是成本项，却是演示期唯一不可控的外部依赖（选①的理由）。

---

## 9. 明确不做（3 天口径）

| 不做 | 为什么（具体到本项目） | 替代 |
|---|---|---|
| **K8s** | 全部负载 = 1 容器 / 1 进程 / 峰值 2 路会话；引入控制面要 2 台机器 + 一整套 YAML，编排收益为 0，而 22:30 的 15 分钟会被它吃掉 | `docker compose` + `restart: unless-stopped` |
| **服务网格** | 网格解决"多服务间"流量治理；本项目服务间只是进程内函数调用 | 进程内调用 + 超时预算 |
| **多区域** | 延迟预算 1.24 s，多区域只增加 DNS 与一致性复杂度；演示只有一台帽子 | 单区东京 + 备用区域仅备案（不实施） |
| **自动扩缩容** | 峰值 2 路，扩缩容的最小粒度（1 任务）已是峰值的 500% | 手动 `docker compose scale`（真需要时） |
| **IaC（Terraform/CDK）** | 手写 4 个资源（实例/SG/EIP/日志组）比写状态机+后端+drift 更快；且 3 天环境会变 10 次，review 成本高于收益 | 一页 `docs/runbook/ec2.md` 的 12 条命令 + 一次实操录像 |

**补充纪律**：五项若在 11/17 12:00 后被提，一律走 RFC 且默认"不做"——它们不改善 TTFC、不改善断网恢复、也不改善 10 次连演，只消耗工时。

---

> 本文件只做运行形态与工程化裁决，不含部署代码；所有价格可由 `b0.p.awsstatic.com` / `pricing.us-east-1.amazonaws.com` 原文复现，标注「需核实」的一项（EBS 单价）不得写进提交材料当结论。
