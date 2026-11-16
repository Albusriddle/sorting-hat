# 掂量帽 / Sorting Hat

一顶会说话的帽子：戴上（或按一下）→ 说一句预置台词 → 云端按这句话判学院 → 帽子用「分院帽」的语气念出结果。

本仓库是参赛原型的三层交付：`hw/`（硬件与实测）、`fw/设备端/`（下位机，ESP32-WROOM-32D + Arduino）、`host/`（上位机，Python/FastAPI）。

> **现状（2026-11-16）**：控制面已闭环，判词链路已由「词条文本」驱动；**没有麦克风与功放**，所以真实音频上行/下行未打通，属已接受的硬件缺口。详见 [项目现状报告](docs/status-2026-11-16.md)。

---

## 1. 它现在能做什么

| 能做 | 说明 |
|---|---|
| 连上云端并完成一次会话 | 设备 → 笔记本 `ws://…:8443/v1/voice`，一次 60–90 秒 |
| 按「观众说的话」判院 | 设备把关键词编号映射成预置台词文本（`text` 消息）发给上位机 |
| 四院 + 三条理由 | 判决由代码 `argmax` 产生，理由必须是观众原话 |
| 帽子开口 | 上位机下发桥接句（如「唔……让我看看。」），设备用 CSK4002 念；学院名由设备本地念 |
| 断网/超时兜底 | 6.5 s 救场、15 s 收尾；设备侧 4 s 断网进离线，可按钮轮换四院 |
| 观测与复盘 | 每次会话落 `host/var/sessions.jsonl`，含文本、学院、分数、8 个时间戳 |
| 两种 provider | 默认 mock（零成本）；可切 AWS（Transcribe + Bedrock + Polly） |

**不能做**（已接受）：自由说话转文字（无麦）、把云端 TTS 音频从帽子喇叭放出来（无功放）、全双工打断、TLS（现场内网，留开关）。

---

## 2. 架构

```
┌────────────── ESP32-WROOM-32D（Arduino 固件）──────────────┐
│ LD3320A（I2C 16/17）  关键词 → 编号 → 预置台词文本          │
│ XFS5152/CSK4002（I2C 19/18）  念桥接句 + 学院名             │
│ Wi-Fi STA ── ws://<laptop>:8443/v1/voice ──┐               │
└────────────────────────────────────────────┼───────────────┘
                                             ▼
┌──────────────────── 上位机（笔记本，Python）────────────────┐
│ device_app   WSS 网关：鉴权 / 会话 / 音频缓冲 / watchdog     │
│ engine       text 优先 → LLM → judge → 桥接句 → result      │
│ judge        纯函数：argmax + 反集中 + 引原话校验（≤2 编辑距离）│
│ providers    mock（默认）｜ AWS：Transcribe / Bedrock / Polly │
│ admin_app    /healthz /readyz /preheat /replay /stats /halt  │
│ metrics      sessions.jsonl + /v1/sessions + /v1/metrics     │
└──────────────────────────────────────────────────────────────┘
```

**设计红线**：`house` 只由代码算，模型只给 `evidence/scores`；宣布句与桥接句分开（避免「念 A 宣布 B」）；没有音频/没有文本时不判院。

---

## 3. 硬件（实物）

| 模块 | 型号 | 接口 | 能力 |
|---|---|---|---|
| 主控 | **ESP32-WROOM-32D** | — | Wi-Fi / WebSocket / I2C |
| 语音识别 | 幻尔 **LD3320A** | Wire SDA16 / SCL17，100 kHz | 离线关键词 → 1 字节编号；不转文字、不出音频 |
| 语音合成 | 幻尔 **XFS5152 / CSK4002** | Wire1 SDA19 / SCL18，10 kHz | 合成任意 GBK/UTF-8 文本；板载喇叭 |
| 麦克风 / 功放 | **无**（INMP441、MAX98357A 未采购） | — | 上行只能是全零帧；`0x02` 下行不外放 |
| 按键 | 板载 BOOT（GPIO0） | — | 短按开始/打断，长按 2 s 重连/退出离线 |

引脚、编译开关与冲突记录见 [`hw/pinmap.md`](hw/pinmap.md)；物料见 [`hw/bom.csv`](hw/bom.csv)。实测数据目录 [`hw/measurements/`](hw/measurements/README.md) **目前为空**（全部待测）。

---

## 4. 快速开始（只跑上位机）

环境：Python **3.11+**（开发机为 3.13）、Windows / macOS / Linux。

```bash
cd host
pip install -r requirements.txt
pip install -r requirements-audio.txt    # 可选：Opus 解码；没有就走 0x04 PCM

# 本项目不自动读取 .env，请用环境变量（默认值即可跑通 demo）
export DEVICE_TOKEN=dev-token
export ADMIN_TOKEN=dev-token

python tasks.py test        # 35 passed
python tasks.py up          # device :8443 / admin :8080（admin 只绑 127.0.0.1）
```

另开一个终端：

```bash
cd host
export ADMIN_TOKEN=dev-token
python tasks.py preheat     # 六步；看到 ok:true 即可（degraded 里的 preroll 不阻塞）
python tasks.py ready       # 200
python tasks.py smoke       # text -> result，预期 house=loyalty
```

冒烟预期输出：

```
ready: s-xxxxxxxx {'in': 'pcm16|opus/16k/20ms', 'out': 'pcm16/16k/60ms'}
tts start ... text='唔……让我看看。'
result: loyalty ['我在乎身边的人'] ... scores={'loyalty': 11.0} announce={'variant': 0, 'file': 'loyalty-1.opus'}
```

> **macOS / Linux** 可用 `make test / make up / make preheat / make smoke`；Windows 没有 make，用 `python tasks.py`。
> **`.env` 不会被自动加载**：`host/.env.example` 是键名清单，请用 `export` 或 `direnv` 注入；`tasks.py` 的管理面 token 固定读 `dev-token`，改了 `ADMIN_TOKEN` 时请用 curl 或临时改回默认。

---

## 5. 设备端（固件）

位置：`fw/设备端/firmware/sorting_hat_base/`。用 **Arduino IDE 2.x**，板型 **ESP32 Dev Module**，库：ArduinoJson、arduinoWebSockets。

| 宏（`hat_config.h`） | 默认 | 说明 |
|---|---|---|
| `HAT_ENABLE_MIC/SPK/LED/BTN/OPUS/VAD` | 全关 | 实物没有对应外设 |
| `HAT_HOUSE_ORIGINAL` | `0` | 0=赤翎/玄渊/星枢/穗垣；1=哈利波特原名 |
| `ASR_WAKE_WORD_ID` | `5` | 1–4 号留给四句内容，5 号唤醒 |

串口 115200，命令：`w` 唤醒、`e` 说完、`b` 打断、`x` 故障、`o` 离线、`k` 能量、`a/1-4` 试听、`p` 词条表、`A-D` 模拟识别 1–4 号。

烧板前静态检查（需宿主 g++）：`python fw/设备端/tools/check_build.py fw/设备端/firmware/sorting_hat_base`。

**烧板清单与回传日志**见 [`docs/handoff-fw.md`](docs/handoff-fw.md)（F1–F6）。

---

## 6. 协议摘要

线上事实源是 [`host/app/protocol.py`](host/app/protocol.py)，说明见 [`docs/00-protocol.md`](docs/00-protocol.md)。

| 方向 | 消息 | 要点 |
|---|---|---|
| host → 设备 | `ready` | `sid`、`audio{in,out}`=`pcm16\|opus/16k/20ms` / `pcm16/16k/60ms`、`budget_ms=1240` |
| 设备 → host | `listen` / `vad` | `state:start`、`ev:speech_start/speech_end` |
| 设备 → host | `text` | 词条映射文本，≤200 字；**有它就优先于 ASR** |
| 设备 → host | `0x04` / `0x01` | PCM16/16 kHz/20 ms（320 样本）或 Opus（可选） |
| host → 设备 | `tts` | `state:start/stop`、`text`（桥接句 ≤40 字） |
| host → 设备 | `0x02` | PCM16/16 kHz/60 ms（1920 B） |
| host → 设备 | `result` | `house`、`reasons[3]`、`line`、`scores`、`announce{variant,file}`、`latency` |
| 双向 | `bye` | `reason:done/doff/silence/timeout`、`dev_ts{t_arm,t0,t5a,t5b,t_stop}`；`done` 不关连接 |

二进制帧统一为 `1 B type + 4 B seq(BE) + payload`。时间戳：`TTFV=t5a−t0`、`TTFC=t5b−t0`；对账差 >200 ms 本次指标作废。

---

## 7. 目录

```
hw/                 引脚（实物）、BOM、实测记录（待测）
fw/设备端/           固件（Arduino）+ 生成器 + 编译检查
  firmware/sorting_hat_base/   .ino / hat_* / 驱动 / phrases_gbk.h
host/
  app/               device_app, engine, judge, providers(_aws), protocol,
                     audio, opus_codec, preheat, admin_app, metrics, state, run
  persona/           houses.yaml, lines.yaml, prompt.md
  tests/             35 条（judge/协议/引擎/WS/AWS/Opus）
  tasks.py           Windows 友好任务入口
docs/                协议、providers、runbook、现状、handoff、design/（历史）
fixtures/            回放样例
release/             提交物
tools/               仓库自检、发布脚本
```

---

## 8. 配置（常用）

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEVICE_TOKEN` | `dev-token` | 设备令牌；必须与固件 `secrets.h` 的 `TOKEN` 一致 |
| `ADMIN_TOKEN` | `dev-token` | 管理面 `X-Admin-Token` |
| `PORT` / `ADMIN_PORT` | `8443` / `8080` | 设备面 / 管理面（仅回环） |
| `ASR_PROVIDER` / `LLM_PROVIDER` / `TTS_PROVIDER` | `mock` | 改 `aws` 走云端 |
| `MIN_AUDIO_RMS` | `50` | 低于此值视为静音，不判院 |
| `HISTORY_WINDOW` / `MIN_HISTORY_FOR_BALANCE` | `10` / `10` | 反集中/配额只在攒够历史后启用 |
| `SILENCE_MS` / `SILENCE_BYE_MS` | `8000` / `20000` | 救场 / 收尾（bye 必须 ≥ silence+5 s，否则拒绝启动） |
| `REQUIRE_TLS` / `TLS_CERT` / `TLS_KEY` | `0` / 空 | 开 TLS 时缺证书拒绝启动 |

完整键见 [`host/.env.example`](host/.env.example)。

---

## 9. 测试与验收

```bash
python -m pytest -q            # 35 passed
python tools/check_tree.py     # missing: none / extra: none
python tasks.py preheat        # ok:true
python tasks.py smoke          # result + scores + announce
```

- 判决纯函数：`argmax` + 连续 3 次同院 ×0.85（历史 ≥10 才启用）+ 引原话校验（编辑距离 ≤2）。
- 无文本/无音频：只回「没听清」，**不下发学院**。
- 会话记录：`host/var/sessions.jsonl`，字段含 `text/house/scores/latency/ttfc_ms/dev_ts/audio.rms`。

---

## 10. 常见问题

| 现象 | 排查 |
|---|---|
| 设备 403 / 4401 | `DEVICE_TOKEN` 与固件 `secrets.h` 的 `TOKEN` 是否一致 |
| 帽子不响 | 串口有没有 `[TTS] house=`；`/stats` 有没有 `last.house` |
| 只听到「没听清」 | `/stats.audio.rms` 是否 <50（无麦时正常，应走 `text`） |
| `/readyz` 503 | 先 `python tasks.py preheat`，看哪个 required 步骤红 |
| 大屏空白 | 必须从 `127.0.0.1:8080` 打开（或带 `X-Admin-Token`） |
| 设备连不上 | 手机热点是否通、防火墙 8443、`secrets.h` 的 IP 是否为笔记本当前 IP |

更多：[`docs/runbook.md`](docs/runbook.md)。

---

## 11. 当前限制（已接受）

1. 无麦克风/功放：真实音频链路未打通，演示走「词条映射」。
2. 无真实 ASR：`TranscribeASR` 已就绪，等真 PCM。
3. 明文 `ws://`：现场手机热点内网；`REQUIRE_TLS` 可切成 wss。
4. 12 句预录为**可选**（设备 TTS 直接念院名）；`preheat` 会显示 `degraded=preroll_placeholder`。
5. 未验证：Opus/VAD 真机、AWS 三件套实调、设备端编译（本机无 Arduino 工具链）。

## 12. 下一步

- [ ] 烧板验证 S-05/S-07/S-08（学院名、桥接句、5 号唤醒）
- [ ] AWS 凭证接通，`preheat` 全绿
- [ ] 若加麦：把 `0x04` 换成真 PCM，启用 Transcribe
- [ ] 彩排 3 次，11/17 24:00 交 v1

## 13. 文档

| 文档 | 内容 |
|---|---|
| [docs/status-2026-11-16.md](docs/status-2026-11-16.md) | 项目现状报告（已验证/缺口/风险/48 小时） |
| [docs/handoff-fw.md](docs/handoff-fw.md) | 给下位机/硬件侧的工作报告（烧板清单） |
| [docs/00-protocol.md](docs/00-protocol.md) | 协议现状（消息/帧/时间戳） |
| [docs/providers.md](docs/providers.md) | mock ↔ AWS 切换 |
| [docs/runbook.md](docs/runbook.md) | 上台手册与故障速查 |
| [docs/design/](docs/design/README.md) | 11-15 设计快照（**历史**，硬件/协议已变） |

## 14. 协作

- 分支：`main` 保护；改动走短分支，合并前 `python -m pytest -q` 必须绿。
- 提交信息：`fix: …` / `feat: …` / `docs: …`，涉及接口的写清影响。
- 接口变更：先改 `host/app/protocol.py` 与 `docs/00-protocol.md`，再改固件；两边一起验。

## 15. 许可证

Apache-2.0，见 [`LICENSE`](LICENSE) 与 [`NOTICE`](NOTICE)。

> 版权与 IP：本仓库**不使用**《哈利波特》的角色名、形象、原声或标识；四院为原创命名（赤翎/玄渊/星枢/穗垣）。`HAT_HOUSE_ORIGINAL=1` 仅供内部对比，不建议在公开演示/视频中使用。
