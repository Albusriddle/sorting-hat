# 修复报告：烧板联调问题（2026-11-16 13:35）

> 对应输入：`烧板联调问题-11-17.md`（设备端联调记录）
> 对应提交：**`e29f38c`**（`42e50f5..e29f38c`，已推 `origin/main`）
> 回归：第一轮 37 passed（历史值）；**最新以文末最后一轮为准**；冒烟（全零 PCM + text）`house=loyalty`；8 秒计时观察 PASS

## 0. 结论

| # | 联调问题 | 归属 | 根因 | 状态 |
|---|---|---|---|---|
| 1 | 零音频闸挡掉 `text`，判院一次没执行 | host（S-06 回归） | 闸在 `ENGINE.run` 之前，且未区分"有没有 text" | ✅ 已修 |
| 2 | 第二次 `tts start` 像"没念" | host 时序 + 设备一处 | host 一口气发完 0x02 帧就发 `stop`（137 ms），设备 `tts.stop()` 把句子掐断；**不是**状态机跳过 | ✅ 已修（两端） |
| 3 | 会话结束后静音计时还在跑 | host | 失败分支重挂 `silence_monitor`，且无 `result`/`bye` 收尾 | ✅ 已修 |
| 4 | 会话完整顺序确认 | — | 与实现一致 | ✅ 已写入协议文档 |

## 1. 问题 1：`text` 被零音频闸挡掉

**现象**：`w → A → e`，无麦全零帧，`rms=0<50`，host 回"没听清"，无 `result`。

**改动**（`host/app/device_app.py`）：

```python
has_text = bool((last_text or "").strip())
if has_text:
    pass                                  # 有文字就用文字
elif settings.asr_provider == "mock":
    await send_tts_line("唔……我没听清，再说一次？")
    continue                              # mock 不看 pcm，不能凭底噪判院
elif not pcm or stats["rms"] < settings.min_audio_rms:
    await send_tts_line("唔……我没听清，再说一次？")
    continue
```

**为什么加 mock 防护**：设备端临时给全零帧填 ±121 底噪（RMS=121>50），若某次没发 text，`MockASR` 会返回罐头句凭空判院。此防护堵住该路径。

**验收**：
- `test_text_with_zero_pcm_still_judges`（全零 PCM + text → `courage`）
- 冒烟改为全零 PCM：`result: loyalty`，`/v1/sessions` 中 `audio.rms=0` 但学院正常

## 2. 问题 2：第二次 `tts start` "不念"

**纠正根因**：`hat_comm.cpp` 里 `tts.speakUTF8(txt)` 在状态判断**之前**、无条件执行；状态判断只影响是否切 SPEAKING，不会跳过播放。

**真实原因**：host 把 `0x02` 帧一次性全发完（无节拍），紧接着发 `tts stop`；设备 `tts{stop}` 里的 `tts.stop()` 在 137 ms 后把 CSK4002 掐断。

**改动**：
| 端 | 文件 | 内容 |
|---|---|---|
| host | `host/app/engine.py`、`host/app/device_app.py` | 发帧按 `TTS_PACE_MS`（默认 60 ms/帧）节拍；`t4` 改取**首帧**（原来在整段发完后） |
| host | `host/app/config.py` | 新增 `TTS_PACE_MS`；测试里置 0 保持快速 |
| 设备 | `fw/设备端/.../hat_comm.cpp` | `tts{stop}` **不再** `tts.stop()`；硬停只保留在 `abort`/按钮 |

**验收**：桥接句能完整念完；静音救场句（"唔……你在想什么呢？"）不再被 137 ms 掐断；`host_ms` 不再包含整段音频时长。

## 3. 问题 3：会话结束后计时还在跑

**根因**：失败分支 `start_silence()` 重挂了监控；且该轮没有 `result`，设备不发 `bye{done}`，host 以为会话仍在 → 6.5 s 救场、15 s `bye{silence}`、断连、`sid` 变化。

**改动**（`host/app/device_app.py`）：计时器改为**按轮**——
- `listen start` 启动 `silence_monitor` + `session_watchdog`；
- `vad speech_end`（成功或失败）**立即 cancel 两者，失败不再重挂**；
- `result` 完成 / `bye` 再 cancel 兜底；
- 下一轮 `listen` 重新启动。

**验收**：脚本在无 text + 全零 PCM 后观察 8 秒——只有 1 次 `tts start`（"没听清"），无第二次救场、无 `bye`；`sid` 不变。

## 4. 问题 4：会话顺序（确认并写死）

`docs/00-protocol.md` 增加：

```
listen → text(可选) → vad{speech_end}
       → tts start(桥接句) → 0x02 帧(60ms/帧) → tts stop
       → result{house,reasons,line,scores,announce}
       → 设备 bye{done,dev_ts}
```

补充：`result.line` 设备不要念（按 `house` 念本地 GBK）；`tts{stop}` 不代表硬停；`bye{done}` 不关连接。

## 5. 改动文件（9 个）

```
docs/00-protocol.md                      +3
docs/handoff-fw.md                      +14（新增 §7 联调变更）
fw/设备端/.../hat_comm.cpp               ±3（stop 不硬停）
host/app/config.py                       +1（TTS_PACE_MS）
host/app/device_app.py                  +13（text 优先 / 按轮计时 / 节拍）
host/app/engine.py                       +8（节拍 + t4 首帧）
host/tests/conftest.py                   +4（测试关掉节拍）
host/tests/test_ws_flow.py              +40（2 条新测试）
host/tools/smoke_ws.py                   ±4（改全零 PCM）
```

## 6. 回归与证据

```
python -m pytest -q        → 37 passed, 1 warning in 1.15s
check_tree.py              → missing: none / extra: none
smoke（全零 PCM + text）    → ready ... out=pcm16/16k/60ms
                              tts start ... text='唔……让我看看。'
                              result: loyalty ... scores={'loyalty': 11.0}
8s 计时观察               → tts starts = [0.0]  PASS
```

新增测试：
- `test_text_with_zero_pcm_still_judges`
- `test_noise_without_text_does_not_judge`
- （上一轮）`test_two_sessions_one_connection_after_bye_done`

## 7. 兼容性与回滚

- **旧固件**（未重烧）：仍可工作；`tts{stop}` 会硬停，桥接句可能被截断；不发送 `bye{done}` 时 host 2 s 后落库、无 `ttfc_ms`。
- **新固件**：桥接句完整、`bye{done}` 带 `dev_ts`、`ttfc_ms` 可得。
- **回滚**：`git revert e29f38c`；设备重烧上一版。
- 无协议破坏性变更：仅新增 `TTS_PACE_MS` 配置与文档语义。

## 8. 设备侧仍需完成

1. 重烧 F5（`tts{stop}` 不硬停）；
2. 删除 ±121 底噪绕过；
3. 复测：`w → A → e` 出 `result`；静音 6.5 s 救场句完整；失败一轮后 20 s 无 `bye`；
4. 若使用副本 `D:\学习区\分院帽\sorting-hat-main`，`git pull origin main` 到最新（至少 `09a7d45` 之后）再测。

---

# 附：第二轮（2026-11-17 交接说明）修复

| # | 问题 | 方案 | 端 | 验证 |
|---|---|---|---|---|
| 1 | 静音救场吞话 | `SILENCE_MS` 12000 / `SILENCE_BYE_MS` 20000；识别到词条时发 `vad{speech_start}`，host 收到即取消计时 | host + 固件 | 单测 + 代码审查 |
| 2 | 超时断线重连 | `bye` 任何 reason 都只结算、不断连 | host | `test_bye_silence_keeps_connection` |
| 3 | TTFC 负数/回绕 | 设备 `t0` 提前打点；host 只接受 `0≤差值≤120s`，否则 `None` + `clock_skew`；设备改有符号打印 | host + 固件 | `test_ttfc_is_none_when_device_clock_backwards` |
| 4 | 两个静音参数撞车 | 启动校验 `bye ≥ silence+5000`，不满足退出码 2 | host | `test_config.py` 3 条 |
| 5 | 设备 25s vs host 20s | 设备改 30000 ms | 固件 | 代码审查 |
| 6 | "声音来自 host PCM"误解 | 文档改为"CSK4002 念 `tts.text`；0x02 在无功放时忽略" | 文档 | — |

回归：**43 passed**（第三轮后 44；第四轮后 48）；冒烟（全零 PCM + text）`house=loyalty`；启动校验输出
`invalid settings: SILENCE_BYE_MS(15000) must be >= SILENCE_MS(15000) + 5000`。


---

# 附：第三轮（2026-11-17 全仓审阅）修复

| # | 问题 | 方案 | 验证 |
|---|---|---|---|
| 1 | 静音救场与新 listen 竞态 | `tts_lock` 串行化发送；新 `listen` 等上一句发完 | 代码审查 |
| 2 | abort 不落库 | `abort` 写 `outcome=aborted, reason=doff` | `test_abort_records_row` |
| 3 | 校验只在 run.py | `device_app` 导入时 `validate_settings()` | 任意入口生效 |
| 4 | watchdog 关闭时引擎仍写 socket | 先 `task.cancel()` 再关闭，并记 `timeout` | 代码审查 |
| 5 | aborted 行缺文本 | `record_aborted(reason, text)` | 代码审查 |
| 6 | providers/runbook 34、runbook/PROGRESS 的 `.env` | 改 44、改 export | 文档抽查 |

回归：**44 passed**（当时值）。


---

# 附：第四轮（2026-11-17 上午，host 侧不依赖硬件）修复

| # | 问题 | 方案 | 验证 |
|---|---|---|---|
| 1 | 静音默认值不够覆盖"慢说+停顿" | 默认 `SILENCE_MS=12000`（`SILENCE_BYE_MS=20000`） | `test_config.py` |
| 2 | `/v1/config` 运行时可绕过校验 | 改完立即 `validate_settings()`，失败回滚并 400 | `test_config_rejects_invalid_silence_pair` |
| 3 | 旧/新固件行为差异未回归 | 新增 `vad_start→vad_end`、`bye{timeout}` 复用连接两条测试 | 48 passed |
| 4 | 文档计数/唤醒词/过期说法 | README/PROGRESS/providers/runbook 48；handoff F3/H2 与 fw/README 改 `kai shi` | 文档抽查 |
| 5 | 真机验收口径缺失 | 新增 `docs/accept-host-2026-11-17.md`（旧板可直接跑） | 文档 |

回归：**48 passed**。


---

# 附：第五轮（2026-11-17 中午，全仓审阅后）修复

| # | 问题 | 方案 | 验证 |
|---|---|---|---|
| 1 | 设备念院名 >2 s 时 TTFC 丢失 | `flush_later` 延迟 2 s → **10 s**，`bye{done}` 仍立即落库 | `test_dev_ts_can_arrive_after_two_seconds` |
| 2 | 成功后按打断会多一条 aborted | 按 sid 记 `recorded`，已记过则跳过；新一轮 `listen` 清除 | `test_abort_after_result_does_not_add_aborted_row` |
| 3 | `/v1/config` 只校验 silence | `validate_settings` 补 `min_audio_rms/max_share/recent3_penalty/history_*` 范围 | `test_config_rejects_out_of_range_rms` |
| 4 | 配置测试污染 `STATE.config` | 测试保存/恢复；endpoint 仍是"先校验后写 STATE" | `test_config_does_not_pollute_state` |
| 5 | watchdog 只取消引擎 | 先 `cancel(silence_task, task)` 再关闭 | 代码审查 |
| 6 | 文档 8000/pull hash/历史数 | 全部同步为 12000 / 最新 main / "当时值" | 文档抽查 |

回归：**52 passed**。

---

# 附：第六轮（2026-11-18，host 侧不依赖新固件）修复

| # | 问题 | 方案 | 验证 |
|---|---|---|---|
| 1 | 平衡机制按"连接"累积，第 11 个判院轮次起必翻院 | `MIN_HISTORY_FOR_BALANCE` 默认 10 → **9999**（关闭，同句同果）；机制代码保留，要用就显式设 10 | `test_balance_is_off_by_default` |
| 2 | 无法证明跑的是哪套参数 | `config.effective()` + 起服打印 `[CFG] {...}`；新增 `GET /v1/selfcheck`（token 掩码） | `test_selfcheck_masks_tokens` |
| 3 | 救场后只剩 8 s 就被收尾 | 救场句播完**重锚** `last_speech`；同时新增 `SILENCE_HARD_CAP_MS=28000` 单轮硬上限（必须 < 固件 30 s） | `test_rescue_then_hard_cap_bye` |
| 4 | TTFC 被救场句音频污染却无标记 | 行内新增 `rescue`；救场轮且 `ttfc<1000` 时标 `ttfc_suspect` | `test_session_row_has_rescue_flag` |
| 5 | 无"连演 15 轮/拔网线"验收用例 | 验收单新增用例 D/E/F | 文档 |

回归：**57 passed**。

---

# 附：第七轮（2026-11-18，全仓审阅后）修复

| # | 级别 | 问题 | 方案 | 验证 |
|---|---|---|---|---|
| 1 | 高 | README 三处仍写 52/57 条测试 | 全部改 **60**；README/PROGRESS/providers/runbook/验收单同步 | 文档抽查 |
| 2 | 中 | `pending`/`timers` 以 sid 为键，同连接第二场会覆盖第一场 | 键改 `(sid#轮次)`，`new_round()` 每轮递增；`_collect` 绑定当轮键 | `test_two_rounds_without_bye_keep_both_rows` |
| 3 | 中 | `/v1/config` 不含 `silence_hard_cap_ms` | 加进允许键（校验已限 ≤29000） | `test_config_can_hot_tune_hard_cap`、`test_config_rejects_hard_cap_above_device_timeout` |
| 4 | 低 | `rescued_round` 死代码 + `nonlocal_rescue` 列表当变量 | 删列表，统一 `nonlocal rescued_round` | 代码审查 |
| 5 | 低 | `ttfc_suspect` 与 `clock_skew` 语义分裂 | 救场轮统一标 `ttfc_suspect`，负值仍记 `clock_skew` | 代码审查 |
| 6 | 低 | `banner()` 函数内 import json | 提到模块顶部 | 起服横幅实测 |
| 7 | 中 | handoff 未提硬上限；runbook 无 selfcheck | 两处补齐 | 文档 |

回归：**60 passed**；起服 `[CFG]` 与 `/v1/selfcheck` 实测通过。
