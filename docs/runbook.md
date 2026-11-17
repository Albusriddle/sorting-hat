# 上台手册（Windows / macOS 通用）

1. `cd host`，`export DEVICE_TOKEN=… ADMIN_TOKEN=…`（`.env` 不会自动加载；键名见 `.env.example`）；设备 `secrets.h` 的 `TOKEN` 与 `DEVICE_TOKEN` 一致。
2. `pip install -r requirements.txt`（可选 `-r requirements-audio.txt`）。
3. `python tasks.py test` → 48 passed。
4. `python tasks.py up`（device :8443 / admin :8080）。
5. `python tasks.py preheat` → `ok:true`；若 `degraded:["preroll_placeholder"]` 可上台（宣布句走设备 TTS）。
6. `python tasks.py ready` → 200。
7. `python tasks.py smoke` → 看到 `result ... announce=...`。
8. 设备上电 → 戴上/按 `w` → 说预置台词（或按 `A-D` 模拟）→ 帽子念院名。

## 故障速查

| 现象 | 先查 |
|---|---|
| 设备 403 | `DEVICE_TOKEN` 与 `secrets.h` 的 `TOKEN` 是否一致 |
| 帽子不响 | `/stats` 有无 `last.house`；串口 `[TTS] house=` 有没有 |
| 只听到"没听清" | `/stats.audio.rms` 是否 <50（无麦时是 0，走 `text` 才对） |
| readyz 503 | `python tasks.py preheat`，看哪个 required 步骤红 |
| 大屏空白 | 大屏必须从 `127.0.0.1:8080` 打开，或带 `X-Admin-Token` |
| 看到 bye 但连接没断 | 正常：host 现在任何 `bye` 都只结算本轮，不断连 |
| 按了 halt 还在跑 | `halt_new/stop_all` 只拦新 `listen`，不打断在途会话 |
| 改了 env 不生效 | 先停旧进程（端口占用），再 `python tasks.py up` |
| 静音救场太早/太晚 | `SILENCE_MS` 必须覆盖"唤醒后停顿 + 慢说"（建议 12 s）；`SILENCE_BYE_MS ≥ SILENCE_MS+5 s` |

## 主持提示（半双工）

帽子说话时麦克风是关的：等它念完再提示下一位说话；LD3320A 只在识别完成时给编号，所以"开始说"没有提前信号，救场计时只能按 8 s 兜底。

