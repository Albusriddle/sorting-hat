# 修复报告：烧板联调问题（2026-11-16 13:35）

> 对应输入：`烧板联调问题-11-17.md`（设备端联调记录）
> 对应提交：**`e29f38c`**（`42e50f5..e29f38c`，已推 `origin/main`）
> 回归：**37 passed**；冒烟（全零 PCM + text）`house=loyalty`；8 秒计时观察 PASS

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
4. 若使用副本 `D:\学习区\分院帽\sorting-hat-main`，`git pull` 到 `e29f38c` 再测。

---

# 附：第二轮（2026-11-17 交接说明）修复

| # | 问题 | 方案 | 端 | 验证 |
|---|---|---|---|---|
| 1 | 静音救场吞话 | `SILENCE_MS` 8000 / `SILENCE_BYE_MS` 20000；识别到词条时发 `vad{speech_start}`，host 收到即取消计时 | host + 固件 | 单测 + 代码审查 |
| 2 | 超时断线重连 | `bye` 任何 reason 都只结算、不断连 | host | `test_bye_silence_keeps_connection` |
| 3 | TTFC 负数/回绕 | 设备 `t0` 提前打点；host 只接受 `0≤差值≤120s`，否则 `None` + `clock_skew`；设备改有符号打印 | host + 固件 | `test_ttfc_is_none_when_device_clock_backwards` |
| 4 | 两个静音参数撞车 | 启动校验 `bye ≥ silence+5000`，不满足退出码 2 | host | `test_config.py` 3 条 |
| 5 | 设备 25s vs host 20s | 设备改 30000 ms | 固件 | 代码审查 |
| 6 | "声音来自 host PCM"误解 | 文档改为"CSK4002 念 `tts.text`；0x02 在无功放时忽略" | 文档 | — |

回归：**42 passed**；冒烟（全零 PCM + text）`house=loyalty`；启动校验输出
`invalid settings: SILENCE_BYE_MS(15000) must be >= SILENCE_MS(15000) + 5000`。
