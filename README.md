# 掂量帽 / Sorting Hat

一顶会说话的帽子：戴上（或按一下）→ 说一句预置台词 → 云端按这句话判学院 → 帽子用「分院帽」的语气念出结果。

三层交付：`hw/`（硬件与实测）、`fw/设备端/`（下位机，ESP32-WROOM-32D + Arduino）、`host/`（上位机，Python/FastAPI）。

> **现状（2026-11-18）**：上位机 **60 条测试全绿**；判院链路、静音节奏、参数自证、一轮一行落库都已收口。
> 设备端四院判院与 CSK4002 出声已在真机验证，但**板上仍是 `5d845bb` 旧固件**——仓库 main 的 `t0`／`vad_start`／30 s／有符号打印还没烧。
> 没有麦克风与功放，真实音频链路未打通（已接受）。

---

## 1. 能做什么 / 不能做什么

| 能做 | 说明 |
|---|---|
| 连上云端完成一次会话 | 设备 → 笔记本 `ws://…:8443/v1/voice`，60–90 秒 |
| 按「观众说的话」判院 | LD3320A 识别关键词编号 → 设备发预置台词 `text`；host 优先用它，不调 ASR |
| 四院 + 三条理由 | `house` 由代码 `argmax` 产生；理由必须是观众原话（编辑距离 ≤2） |
| 帽子开口 | host 下发桥接句（`tts.text`），设备用 CSK4002 念；院名由设备本地念 |
| 同一句话永远同一个学院 | 反集中/配额默认关闭（`MIN_HISTORY_FOR_BALANCE=9999`），演示可预期 |
| 兜底 | host：12 s 救场、20 s 空闲收尾、28 s 单轮硬上限；设备：30 s 监听超时、断网离线、串口按钮轮换四院 |
| 观测 | **一轮一行**落 `host/var/sessions.jsonl`，含文本/学院/分数/延迟/`ttfc_ms`/`clock_skew`/`ttfc_suspect`/`rescue`/`outcome` |
| 参数自证 | 起服打印 `[CFG] {...}`；`GET /v1/selfcheck` 可远程核对（token 掩码） |
| 两种 provider | 默认 mock（零成本）；可切 AWS（Transcribe + Bedrock + Polly） |

**不能做**（已接受）：自由说话转文字（无麦）、把云端 TTS 音频从帽子喇叭放出来（无功放）、全双工打断、TLS（现场内网，留 `REQUIRE_TLS` 开关）。

**硬件能力边界**：LD3320A 是命令词芯片，不是麦克风阵列——**要慢说、唤醒后停半秒到一秒、只说短句**；帽子说话时它仍在听（半双工是假的），观众此时别说话。

---

## 2. 架构

```
┌────────────── ESP32-WROOM-32D（Arduino 固件）──────────────┐
│ LD3320A（I2C 16/17, 0x79）  关键词 → 编号 → 预置台词文本     │
│ XFS5152/CSK4002（I2C 19/18, 0x40） 念桥接句 + 学院名        │
│ Wi-Fi STA ── ws://<laptop>:8443/v1/voice ──┐                │
└────────────────────────────────────────────┼────────────────┘
                                             ▼
┌──────────────────── 上位机（笔记本，Python）────────────────┐
│ device_app   网关：鉴权 / 会话 / 音频缓冲 / 静音计时 / 硬上限 │
│ engine       text 优先 → LLM → judge → 桥接句 → result      │
│ judge        纯函数：argmax + 引原话校验（平衡默认关）        │
│ providers    mock（默认）｜ AWS：Transcribe / Bedrock / Polly │
│ admin_app    healthz readyz preheat replay sessions stats     │
│              metrics selfcheck config halt + 大屏            │
│ metrics      sessions.jsonl（一轮一行）+ /v1/sessions        │
└──────────────────────────────────────────────────────────────┘
```

**设计红线**
1. `house` 只由代码算，模型只给 `evidence/scores`；`refuse` 原样透传、不判院。
2. 宣布句（院名）由设备本地念，桥接句由 host 下发；两者不混。
3. 没有文字、也没有可用音频时，只回「没听清」，不下发学院。
4. 会话结束只结算、不断连；断连只由 socket 关闭决定。
5. 一轮一行：记录键是 `sid#轮次`，同一条连接跑 100 场也不会互相覆盖。

---

## 3. 硬件（实物）

| 模块 | 型号 | 接口 | 能力 |
|---|---|---|---|
| 主控 | **ESP32-WROOM-32D** | — | Wi-Fi / WebSocket / I2C |
| 语音识别 | 幻尔 **LD3320A**（0x79） | Wire SDA16 / SCL17，100 kHz | 离线关键词 → 1 字节编号；不转文字、不出音频 |
| 语音合成 | 幻尔 **XFS5152 / CSK4002**（0x40） | Wire1 SDA19 / SCL18，10 kHz | 合成任意 GBK/UTF-8 文本；板载喇叭 |
| 麦克风 / 功放 | **无**（INMP441、MAX98357A 未采购） | — | 上行只能是全零帧；`0x02` 下行不外放 |
| 按键 / 灯 | **无** | — | 串口命令代用；`[LED]` 只是打印，别教人"等灯亮" |

ESP32-S3 因 5V 带不动两模块已停用；烧录速率用 **115200**（921600 会 `chip stopped responding`）。
引脚/地址/冲突见 [`hw/pinmap.md`](hw/pinmap.md)；物料见 [`hw/bom.csv`](hw/bom.csv)；实测目录 [`hw/measurements/`](hw/measurements/README.md) **目前为空（全部待测）**。

---

## 4. 快速开始（只跑上位机）

环境：Python **3.11+**、Windows / macOS / Linux。

```bash
cd host
pip install -r requirements.txt
pip install -r requirements-audio.txt   # 可选：Opus 解码；没有就走 0x04 PCM

# 本项目不自动读 .env；用环境变量（默认值即可跑通 demo）
export DEVICE_TOKEN=dev-token
export ADMIN_TOKEN=dev-token

python tasks.py test        # 60 passed
python tasks.py up          # device :8443 / admin :8080（admin 只绑 127.0.0.1）
```

另开终端：

```bash
cd host
export ADMIN_TOKEN=dev-token
python tasks.py preheat     # ok:true 即可；degraded 里的 preroll 不阻塞
python tasks.py ready       # 200
python tasks.py smoke       # text -> result，预期 house=loyalty
curl -s -H "X-Admin-Token: dev-token" localhost:8080/v1/selfcheck
```

起服应看到一行自证：

```
[CFG] {"silence_ms": 12000, "silence_bye_ms": 20000, "silence_hard_cap_ms": 28000,
       "min_history_for_balance": 9999, "balance_active": false, ...}
```

冒烟预期：

```
ready: s-xxxxxxxx {'in': 'pcm16|opus/16k/20ms', 'out': 'pcm16/16k/60ms'}
tts start ... text='唔……让我看看。'
result: loyalty ['我在乎身边的人'] ... scores={'loyalty': 11.0} announce={'variant': 0, 'file': 'loyalty-1.opus'}
```

> - **`make`**：macOS/Linux 可用 `make test / up / preheat / smoke`；Windows 用 `python tasks.py`。
> - **`.env` 不会自动加载**：`host/.env.example` 只是键名清单，请 `export` 注入；数值行不要带行内注释。
> - **`tasks.py`** 的管理面 token 读 `ADMIN_TOKEN`（默认 `dev-token`）。

---

## 5. 设备端（固件）

位置：`fw/设备端/firmware/sorting_hat_base/`。Arduino IDE 2.x，板型 **ESP32 Dev Module**，库：ArduinoJson、arduinoWebSockets。

| 宏（`hat_config.h`） | 默认 | 说明 |
|---|---|---|
| `HAT_ENABLE_MIC/SPK/LED/BTN/OPUS/VAD` | 全关 | 实物没有对应外设 |
| `HAT_HOUSE_ORIGINAL` | `0` | 0=赤翎/玄渊/星枢/穗垣；1=哈利波特原名 |
| `ASR_WAKE_WORD_ID` | `5` | 1–4 号四句内容，5 号唤醒 |
| `LISTEN_TIMEOUT_MS` | `30000` | 晚于 host 的 20 s 空闲收尾 / 28 s 硬上限 |

串口 115200：`w` 唤醒、`e` 说完、`b` 打断、`x` 故障、`o` 离线、`k` 能量、`a/1-4` 试听、`p` 词条表、`A-D` 模拟识别 1–4 号、大写 `P` 重写词条。

**词条表（实烧短拼音）**：`kai shi`（5，唤醒）/ `wo pa shu`（1）/ `wo yao de hen da`（2）/ `wo xi huan chai kai xiang`（3）/ `wo zai hu shen bian`（4）。1–4 与 intent 长句是**映射关系**，已验 6/6，不要重烧。

**仓库 main 相对板上固件的四处差异**（需重烧）：`t0` 移到 `vad_end` 之前、识别后补发 `vad{speech_start}`、`LISTEN_TIMEOUT_MS=30000`、时间戳有符号打印。

烧板清单与回传日志见 [`docs/handoff-fw-2026-11-17.md`](docs/handoff-fw-2026-11-17.md)。

---

## 6. 协议摘要

线上事实源：[`host/app/protocol.py`](host/app/protocol.py)；说明：[`docs/00-protocol.md`](docs/00-protocol.md)。

| 方向 | 消息 | 要点 |
|---|---|---|
| host → 设备 | `ready` | `sid`、`audio{in,out}`=`pcm16\|opus/16k/20ms` / `pcm16/16k/60ms`、`budget_ms=1240` |
| 设备 → host | `listen` / `vad` | `state:start`、`ev:speech_start/speech_end`（`speech_start` = "听到了"，host 停表） |
| 设备 → host | `text` | 词条映射文本，≤200 字；有它就不调 ASR |
| 设备 → host | `0x04` / `0x01` | PCM16/16 kHz/20 ms（320 样本）或 Opus（可选） |
| host → 设备 | `tts` | `start/stop`、`text`（桥接句 ≤40 字） |
| host → 设备 | `0x02` | PCM16/16 kHz/60 ms（1920 B），按 60 ms/帧节拍发 |
| host → 设备 | `result` | `house`、`reasons[3]`、`line`、`scores`、`announce{variant,file}`、`latency` |
| 双向 | `bye` | `done/doff/silence/timeout` + `dev_ts`；**host 不因 bye 断连** |

一次会话：`listen → text(可选) → vad_end → tts start(桥接) → 0x02 帧 → tts stop → result → 设备 bye{done,dev_ts}`。
`TTFV=t5a−t0`、`TTFC=t5b−t0`；host 只接受 `0 ≤ 差值 ≤ 120 s`，否则 `None` + `clock_skew`；救场轮的 TTFC 一律标 `ttfc_suspect`（救场句音频会先抢 `t5b`）。

---

## 7. 时序（一轮，含两种结局）

```
设备                                 host
 │ listen{start} ───────────────────▶ 开新一轮：seq+1，起静音计时
 │ text{...} ───────────────────────▶ 存为本轮文本
 │ vad{speech_start} ───────────────▶ heard.set() → 停表
 │ vad{speech_end} ─────────────────▶ 有 text 就直接判（不看音频）
 │                                    tts{start,桥接句} → 0x02 帧(60ms/帧) → tts{stop}
 │ ◀──────────────────────────────── result{house,reasons,scores,announce}
 │ 念本地院名，然后 bye{done,dev_ts} ▶ 落一行（含 ttfc）
 │
 │（12 s 没识别到）◀──────────────── tts{start,"唔……你在想什么呢？"} → 重锚计时
 │（28 s 硬上限 / 20 s 空闲）◀────── bye{silence} + close（设备重连，新 sid）
```

---

## 8. 目录

```
hw/                 引脚（含 I2C 地址）、BOM、实测（待测）
fw/设备端/           固件（Arduino）+ 生成器 + 编译检查
  firmware/sorting_hat_base/   .ino / hat_* / 驱动 / phrases_gbk.h
host/
  app/               config device_app engine judge providers(_aws) protocol
                     audio opus_codec preheat admin_app metrics state run
  persona/           houses.yaml, lines.yaml, prompt.md
  tests/             60 条（judge/协议/引擎/WS/AWS/Opus/配置/一轮一行）
  tasks.py           Windows 友好任务入口
docs/                协议、providers、runbook、修复报告、交接、验收单、design/（历史）
fixtures/            回放样例
release/             提交物
tools/               仓库自检、发布脚本
```

---

## 9. 配置（常用）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEVICE_TOKEN` | `dev-token` | 设备令牌；必须与固件 `secrets.h` 的 `TOKEN` 一致 |
| `ADMIN_TOKEN` | `dev-token` | 管理面 `X-Admin-Token`；`tasks.py` 读同一变量 |
| `PORT` / `ADMIN_PORT` | `8443` / `8080` | 设备面 / 管理面（仅回环） |
| `ASR_PROVIDER` / `LLM_PROVIDER` / `TTS_PROVIDER` | `mock` | 改 `aws` 走云端 |
| `MIN_AUDIO_RMS` | `50` | 低于此值视为静音；有 `text` 时不受影响 |
| `HISTORY_WINDOW` / `MIN_HISTORY_FOR_BALANCE` | `10` / `9999` | 反集中/配额；**默认关闭**（同句同果），要开就设成 10 |
| `SILENCE_MS` / `SILENCE_BYE_MS` / `SILENCE_HARD_CAP_MS` | `12000` / `20000` / `28000` | 救场 / 空闲收尾 / 单轮硬上限；bye ≥ silence+5 s，硬上限 ≤29 s（固件 30 s） |
| `TTS_PACE_MS` | `60` | 下行帧节拍；测试置 0 |
| `REQUIRE_TLS` / `TLS_CERT` / `TLS_KEY` | `0` / 空 | 开 TLS 时缺证书拒绝启动 |

完整键见 [`host/.env.example`](host/.env.example)。`/v1/config` 可热改 `max_share / recent3_penalty / min_history_for_balance / silence_ms / silence_bye_ms / silence_hard_cap_ms / min_audio_rms`，**改完立即校验，失败回滚并 400**。

---

## 10. 测试与验收

```bash
python -m pytest -q            # 60 passed
python tools/check_tree.py     # missing: none / extra: none
python tasks.py preheat        # ok:true
python tasks.py smoke          # result + scores + announce
```

- 判决纯函数；空 evidence / 全零分 / `refuse` → 不判院。
- 全零音频 + `text`：照常判院；无 `text` + mock：只回「没听清」并记 `outcome=aborted`。
- `bye` 任何 reason 都不断连；`abort` 也落一行；成功后再打断不会重复记。
- 平衡默认关闭：**同一个词条 15 场连演仍是同一个学院**。
- 真机验收（旧板即可跑，含连演 15 轮 / 拔网线 / 救场后 28 s）：[`docs/accept-host-2026-11-17.md`](docs/accept-host-2026-11-17.md)。

---

## 11. 常见问题

| 现象 | 排查 |
|---|---|
| 设备 403 / 4401 | `DEVICE_TOKEN` 与固件 `secrets.h` 的 `TOKEN` 是否一致 |
| 帽子不响 | 串口有没有 `[TTS] house=`；`/stats` 有没有 `last.house` |
| 只听到「没听清」 | `/stats.audio.rms` 是否 <50；无麦时应走 `text` |
| 说一半帽子插嘴 | 是否把 `SILENCE_MS` 改成 8 s；默认应为 12 s |
| 同一个词条判出不同学院 | `/v1/selfcheck` 看 `min_history_for_balance` 是否被设成 10 |
| 不知道跑的是哪套参数 | `curl -H "X-Admin-Token: …" localhost:8080/v1/selfcheck` |
| `/readyz` 503 | 先 `python tasks.py preheat`，看哪个 required 步骤红 |
| 大屏空白 | 从 `127.0.0.1:8080` 打开，或带 `X-Admin-Token` |
| 看到 bye 但连接没断 | 正常：host 只在结算，不断连 |
| 按 halt 还在跑 | `halt_new/stop_all` 只拦新 `listen`，不打断在途 |
| 改了 env 不生效 | 先停旧进程（端口占用），再 `python tasks.py up`；`.env` 不自动加载 |

更多：[`docs/runbook.md`](docs/runbook.md)。

---

## 12. 当前限制（已接受）

1. 无麦克风/功放：真实音频链路未打通，演示走「词条映射」。
2. 无真实 ASR：`TranscribeASR` 已就绪，等真 PCM。
3. 明文 `ws://`：现场热点内网；`REQUIRE_TLS` 可切 wss。
4. 12 句预录为**可选**（设备 TTS 直接念院名）；`preheat` 会显示 `degraded=preroll_placeholder`。
5. 未验证：Opus/VAD 真机、AWS 三件套实调、设备端编译（本机无 Arduino 工具链）。
6. 半双工是假的：帽子说话时 LD3320A 仍听，靠主持脚本规避。

## 13. 下一步

- [ ] 烧仓库 main 固件（`t0` 提前、`vad_start`、30 s、有符号打印），回传开机日志
- [ ] **固件 P0**：`THINKING` 级超时（Wi-Fi 抖动时帽子不会卡死）
- [ ] 唤醒即播 `PH_ASK`（"说吧，孩子。"）——现成词条，零硬件
- [ ] 每轮一行 `[ROUND] heard=0/1`，区分"没开口/没听清/听错"
- [ ] 旧板跑验收单用例 A–F
- [ ] AWS 凭证接通，`preheat` 全绿
- [ ] 彩排 3 次；11/18 15:00 冻结

## 14. 文档

| 文档 | 内容 |
|---|---|
| [docs/handoff-2026-11-18.md](docs/handoff-2026-11-18.md) | **交接报告**（现状、待办、风险、验收口径） |
| [docs/accept-host-2026-11-17.md](docs/accept-host-2026-11-17.md) | 旧板即可跑的 host 验收单（用例 A–F） |
| [docs/handoff-fw-2026-11-17.md](docs/handoff-fw-2026-11-17.md) | 给下位机/硬件的烧板清单 |
| [docs/fix-report-2026-11-16.md](docs/fix-report-2026-11-16.md) | 七轮修复报告（含每轮依据与验证） |
| [docs/00-protocol.md](docs/00-protocol.md) | 协议现状（消息/帧/时间戳/bye 语义） |
| [docs/providers.md](docs/providers.md) | mock ↔ AWS 切换 |
| [docs/runbook.md](docs/runbook.md) | 上台手册与故障速查 |
| [docs/status-2026-11-16.md](docs/status-2026-11-16.md)、[docs/design/](docs/design/README.md) | 历史快照 |

## 15. 协作

- `main` 保护；改动走短分支，合并前 `python -m pytest -q` 必须绿。
- 提交信息：`fix:` / `feat:` / `docs:`；涉及接口写清影响。
- 接口变更：先改 `host/app/protocol.py` 与 `docs/00-protocol.md`，再改固件，两边一起验。
- 改测试数/参数默认值时，用 `grep -rn "passed"`、`grep -rn "9999\|12000"` 全域扫一遍，避免只改一处。

## 16. 许可证与 IP

Apache-2.0，见 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)。
本仓库不使用《哈利波特》角色名、形象、原声或标识；四院为原创命名（赤翎/玄渊/星枢/穗垣）。`HAT_HOUSE_ORIGINAL=1` 仅供内部对比，不建议公开演示使用。
