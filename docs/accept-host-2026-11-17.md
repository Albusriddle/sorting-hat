# 上位机验收单（2026-11-17，旧板也能跑）

> 目的：在**不重烧**当前 `5d845bb` 板子的前提下，先验证仓库版 host 的三处修复
> （text 优先、12 s 静音、bye 不复用断连）。
> 适用：A 手里那块 COM14 / 10.46.227.164 的板子。
> 注：外部《测试流程-完整版》里的旧值/旧说法以本仓库 `docs/runbook.md` 为准。

## 0. 部署

```bash
cd host
export DEVICE_TOKEN=dev-token ADMIN_TOKEN=dev-token
export SILENCE_MS=12000 SILENCE_BYE_MS=20000
python tasks.py test          # 期望 60 passed
python tasks.py up            # 先确认旧进程已停，端口没被占
curl -s localhost:8080/healthz
```

记录当前 `sid`（串口 `[NET] sid=...`）与 `/v1/sessions?n=1`。

## 用例 A：文字优先（旧固件即可）

1. 串口 `w`（唤醒）→ `A`（模拟 1 号）→ `e`（说完）
2. 期望：
   - 串口 `[WS-TX] text "我最怕输…"`
   - 云端 `[WS-RX] tts start text="唔……让我看看。"`
   - `[WS-RX] result house=courage`
   - `[TTS] house=courage (赤翎)`
3. host 侧：`/v1/sessions?n=1` 最后一行 `house=courage`、`rms=0`、`outcome` 为空/无。

## 用例 B：静音 12 s（旧固件即可）

1. 串口只 `w`，不说话。
2. 期望：
   - 约 12 s：`tts start text="唔……你在想什么呢？"`
   - 约 20 s：host 发 `bye{silence}` 并断开；**这是 host 自己的收尾**，不是 bug。
   - 重新 `w` 后能继续（新 sid 可接受；若 host 未断，sid 应不变）。
3. 旧固件还会在 25 s 自己发 `bye{timeout}`；若 host 先断，它不会触发。

## 用例 C：TTFC 兼容（旧固件即可）

旧固件 `t0` 在 `vad_end` 之后，可能出现 `t5b < t0`：
- 期望写库 `ttfc_ms=null`、`clock_skew` 为负数；
- **不允许**出现 `4294966xxx` 或负数 `ttfc_ms`。

## 回传证据（4 条）

```
[BOOT] asr=... tts=...
[NET] sid=... in=pcm16|opus/16k/20ms out=pcm16/16k/60ms
[WS-TX] text "..." / [WS-TX] bye ...
[WS-RX] result house=...
```

再附：`/healthz` 输出、`/v1/sessions?n=3` 的 `house/ttfc_ms/clock_skew`。

## 已知差异（旧固件）

| 项 | 旧固件（现在的板子） | 新固件（仓库 main） |
|---|---|---|
| `vad_start` | 无（识别后只发 vad_end） | 识别后补发，host 停表 |
| `t0` | `vad_end` 之后 | `vad_end` 之前 |
| 超时 | 25 s | 30 s |
| TTFC 打印 | 无符号（会 4294966xxx） | 有符号（n/a） |

**结论**：用例 A/B/C 通过 = host 修复有效；要验证 `vad_start`/`t0`/30 s，仍需重烧 main。

---

## 用例 D：连演 15 轮同词条（验证平衡机制已关闭）

目的：确认"同一个词条永远判同一个学院"，这是 11-18 识别率报告暴露的最大缺陷。

```
0. 前提：**每说一次前必须先重新唤醒**（固件只从 OFF/ARMED 进 LISTENING；帽子念完回到 ARMED 才可再唤醒）
1. 起服日志应出现 [CFG] {... "min_history_for_balance": 9999, "balance_active": false ...}
2. 同一词条连说 15 次（每次都要重新唤醒）
3. 期望：15 次 result 的 house 完全一致
4. 反证：若第 11 轮起开始变成 courage，说明平衡机制仍开着
   → 检查 GET /v1/selfcheck 的 effective.min_history_for_balance
```

## 用例 E：拔网线取证（交给 A 的 P0）

目的：确认"帽子卡在 THINKING"是固件侧问题，不是上位机不发。

```
1. 唤醒后立刻拔掉热点（或关笔记本 Wi-Fi）
2. 期望（上位机侧）：没有 result 发出；设备串口无 [WS-RX]
3. 恢复网络后：
   - 上位机：连接由设备重连，新 sid，一切正常
   - 设备：若停在 THINKING 且无法自愈（只能按串口 b 或断电）→ 固件 P0 成立
4. 回传：拔网前后各 10 行串口日志
```

## 用例 F：救场句不再"只剩 8 秒"

```
1. 设置 SILENCE_MS=12000 / SILENCE_BYE_MS=20000 / SILENCE_HARD_CAP_MS=28000（默认值）
2. 只唤醒、不说话：约 12 s 听到救场句
3. 救场句念完后再等：约 28 s（不是 20 s）才收到 bye{silence}
4. /v1/sessions 该行应带 "rescue": true
```
