# 执行路线与步骤（可行性最高的一条）

> 依据：`sortinghat/上位机方案.md`、`sortinghat/统一准则-通信协议-仓库施工.md`、`sortinghat/工程架构-上位机下位机硬件.md`。
> 状态：**上位机骨架已落地并通过本机验证**（见 §8）；硬件与真实供应商待接。
> 时间：今天 2026-11-15 22:5x；提交 11/18；路演 11/21。

---

## 0. 三条执行原则

1. **先能演，再好看。** 任何一步不能直接产出"帽子里有声音"的，排到后面。
2. **接口先冻，代码后追。** G1（引脚）→ G2（协议）→ G3（判决）→ G4（协议全冻），每次冻结由下游签字。
3. **每天一个 Gate，过不了就砍。** 砍功能不砍验收（真机、真对话、视频、回执）。

---

## 1. 路线总览

| 阶段 | 时间 | 目标 | Gate | 谁 |
|---|---|---|---|---|
| **P0 出声** | 11/15 18:00–23:30 | 帽子听得见、说得出 | **G1** 18:00 引脚冻结；**G2** 23:30 出声 + 协议冻结 | A（硬件/固件）+ B（网关） |
| **P1 闭环** | 11/16 全天 + 晚 | 说→ASR→LLM→TTS→帽子说，10 次 TTFC ≤2.5 s | **G3** 23:30 判决/人格冻结 | A+B |
| **P2 降级** | 11/17 白天 | 九格降级 + 断网按钮模式 + 大屏 | 四类超时各演示一次 | B+C |
| **P3 材料** | 11/17 晚–11/18 15:00 | 视频、README、贡献清单、回执 | **G5** 11/17 24:00 交 v1；**G6** 11/18 15:00 冻结 | C |
| **P4 路演** | 11/19–11/21 | 3 次彩排 + 踩点 + 上台 | **G8** 11/20 22:00 彩排通过 | 全员 |

---

## 2. 阶段 P0：今天（11/15）

| 时刻 | 动作 | 命令/判据 | 状态 |
|---|---|---|---|
| 18:00 | 采购下单；称帽；`hw/pinmap.md` 签字 | `FROZEN G1 20261115 <SHA>`；帽本体 ≤150 g | 待 A |
| 18:00 | 上位机骨架与预热可跑 | `make up && make preheat` → `ok:true` | **✅ 已完成** |
| 20:00 | STM32/ESP32 工具链就绪，刷官方固件 | 串口有日志 | 待 A |
| 21:30 | 麦克风回环（录 5 s） | 峰值 −12~−6 dBFS、无削顶 | 待 A |
| 22:30 | 喇叭放音（固定 Opus 文件） | 1 m 处 68–72 dBA | 待 A |
| 23:00 | 设备连网关，说一句，帽子回一句 | `G2a`：听得见 | 待 A+B |
| 23:30 | 抓一次真实会话 → `fixtures/session-g2.ndjson`；协议字段冻结 | `FROZEN G2` | 待 A+B |

**今晚不过 G2 的唯一退路**：切"手机进帽"（4–8 人时），网关侧**一行不用改**——因为它只认 WSS。

---

## 3. 阶段 P1：11/16 闭环

| 步骤 | 动作 | 判据 |
|---|---|---|
| P1-1 | ASR adapter 接真（Transcribe Streaming，`docs/providers.md`） | 说一句，`stt.final` 文本正确 |
| P1-2 | LLM adapter 接真（Bedrock 结构化输出；预热打真 schema，读超时 150 s） | 返回 `evidence/scores/line`，JSON 合法 |
| P1-3 | judge 接真（已实现，`argmax + ×0.85 + 引原话 ≤2`） | 20 条输入 ≥3 院、任一 ≤40% |
| P1-4 | TTS adapter 接真（CosyVoice instruction 音色） | 首包 ≤800 ms，音色听审通过 |
| P1-5 | 8 句预录（4 院 × 2）录制并入库 | `host/assets/preroll/*.opus` sha 记录 |
| P1-6 | 端到端 10 次 | TTFC 中位 ≤2.5 s（内部 Gate）、无崩溃 |
| P1-7 | `fixtures` 回放 | `POST /v1/replay` 与真机结果一致 |
| P1-8 | **G3 冻结**：`result.schema` + `houses.yaml` + `lines.yaml` | `x-frozen: G3` |

**风险**：Bedrock 结构化输出首编译 90 s；TTS 音色不达标；ASR 中文标点影响引原话校验（编辑距离 ≤2 已放宽）。

---

## 4. 阶段 P2：11/17 降级与大屏

| 步骤 | 动作 | 判据 |
|---|---|---|
| P2-1 | 九格降级全部触发一次（`/v1/config` 的 `fault` 开关） | 每条都有一句"观众听到什么" |
| P2-2 | 断网按钮模式 | 拔网 1.2 s 检测、5 s 就绪、仍能宣布 |
| P2-3 | 大屏 `/stats` + 控制台页 | 字幕/理由/延迟/四院分布/揭晓层 |
| P2-4 | `/v1/halt` 刹车 | 新会话拒接、在途收 `bye{timeout}` |
| P2-5 | 观测：8 戳落 JSONL、`/v1/sessions` 可查 | 与秒表差 ≤200 ms |
| P2-6 | 连跑 10 次 | RSS 增幅 <20%，无泄漏 |

---

## 5. 阶段 P3：材料与提交

| 步骤 | 动作 | 判据 |
|---|---|---|
| P3-1 | 90 秒视频（一镜到底 ≥60 s、人帽同框、时间戳、原声） | 见主报告 §10.4 |
| P3-2 | README / 架构图 / 自研贡献清单 / 许可证 | `make release-check` |
| P3-3 | **11/17 24:00 交 v1** | 回执截图 |
| P3-4 | 11/18 15:00 冻结，补拍成片 | 只改错别字 |
| P3-5 | 11/18 18:00 交 v2 | 回执 + 二次确认 |

---

## 6. 阶段 P4：路演

彩排 1（11/19 晚，对镜头）→ 彩排 2（11/20 下午，真机+线材）→ 彩排 3（11/20 晚，全流程+三种故障）→ 11/21 上午踩点。
判据：全程 ≤5:00；拔网/换帽/断电各 15 s 内切备播。

---

## 7. 命令清单（照抄即可）

```bash
# 仓库自检
cd hat && python tools/check_tree.py

# 上位机
cd host && python -m pytest -q
python -m app.run                      # device :8443 / admin :8080

# 预热与就绪（开场前必做）
curl -s -X POST localhost:8080/v1/preheat -H "X-Admin-Token: dev-token"
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/readyz

# 端到端冒烟（无设备）
python host/tools/smoke_ws.py

# 回放与刹车
curl -s -X POST localhost:8080/v1/replay -H "X-Admin-Token: dev-token" \
  -H 'Content-Type: application/json' -d '{"text":"我想赢，我要第一"}'
curl -s -X POST localhost:8080/v1/halt -H "X-Admin-Token: dev-token" \
  -H 'Content-Type: application/json' -d '{"mode":"halt_new"}'
```

---

## 8. 已执行记录（本机，2026-11-15）

| 项 | 结果 |
|---|---|
| 仓库骨架 | `check_tree.py` → `missing: none / extra: none` |
| 单测 | **31 passed**（judge / protocol / engine / api / ws flow / aws / opus） |
| 预热 | `ok:true`，6 步全绿，**60 ms**（persona 2.3 / asr 21.4 / llm 30.2 / tts 2.0 / preroll 4.0 / write 0.5） |
| 端到端冒烟 | 连接 **42 ms**；`tts start` **52 ms**；`result` **56 ms**；**20 帧音频**；`quote_ok: true` |
| 一次会话的延迟（mock） | t0→t2 21 ms、t2→t3 30 ms、t3→t4 5 ms，`host_ms=56` |
| 判决样例 | 输入「我最想要的是被认可，但我又不想说出来。」→ `ambition`，理由 `["我最想要的是被认可","但我又不想说出来"]` |
| 大屏 | `GET /` 返回控制台页，`/stats` 返回会话与延迟 |

> mock 的 56 ms 不代表真实链路；它证明**协议、状态机、判决、降级入口、观测**都已通。真实 TTFC 由 t1–t4 决定，接入 provider 后重测。

---

## 9. 阻塞项（需要你或硬件组动手）

| # | 阻塞 | 谁 | 解除判据 |
|---|---|---|---|
| 1 | 帽子/开发板/喇叭到货 | 你 | 今天 18:00 下单 |
| 2 | 刷机出声 | A | 串口有日志、喇叭响 |
| 3 | 8 句预录 | C | 4 院 × 2，同音色，入库带 sha |
| 4 | AWS/阿里凭证 | 你 | `.env` 六组键填好 |
| 5 | 设备 `bye.dev_ts` 回传 | A | `TTFC = t5b − t0` 可算 |

---

## 10. 验收总表（勾选）

- [x] 仓库七目录齐全
- [x] `/healthz`、`/readyz`、`/v1/preheat` 可跑
- [x] 判决纯函数 + 反集中 + 引原话校验
- [x] 端到端冒烟（mock）出音频与 `result`
- [x] 15 条单测通过
- [ ] 真机出声（G2a）
- [ ] 真实 ASR/LLM/TTS 接入
- [ ] 8 句预录
- [ ] 断网按钮模式
- [ ] 10 次连演
- [ ] 视频与回执
