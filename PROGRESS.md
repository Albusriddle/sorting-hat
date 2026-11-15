# 进度（截至 2026-11-15 22:5x）

## 已完成（本机可复现）

| # | 事项 | 证据 |
|---|---|---|
| 1 | 仓库骨架（七目录） | `python tools/check_tree.py` → missing: none |
| 2 | 上位机 MVP（WS + 管理面 + 控制台） | `python -m app.run`；`/healthz` 200 |
| 3 | 六步预热 | `POST /v1/preheat` → `ok:true`，6 步全绿，60 ms |
| 4 | 端到端冒烟（无设备） | `python tools/smoke_ws.py` → 连接 42 ms、`tts start` 52 ms、`result` 56 ms、20 帧音频 |
| 5 | 判决（argmax + 反集中 + 引原话） | `pytest` 15 passed |
| 6 | 协议消息与错误码白名单 | `pytest` 覆盖 |
| 7 | 大屏 `/stats` + 控制台页 | `curl localhost:8080/` |
| 8 | AWS 三个 adapter（Bedrock / Polly / Transcribe） | `docs/providers.md`；无凭证时 preheat 失败即 fail-closed |
| 9 | 12 句宣布词占位（4 院 × 3） | `host/persona/lines.yaml`，`preheat` 校验 12 文件 |

## 待办（需要硬件/凭证）

- [ ] ESP32-S3 刷机出声（A）
- [ ] 真实 AWS/Alibaba provider 接入（B，按 `docs/providers.md`）
- [ ] 12 句预录音频（C 录制 → `host/assets/preroll/{house}-{1..3}.opus`）
- [x] Opus→PCM 解码（opuslib + pyogg 的 opus.dll；`/stats.audio.decoded` 实测 1）
- [ ] 设备端 `0x04` PCM 回退通道（代码已支持，固件待加）
- [ ] 设备 `bye.dev_ts` 回传（A）→ 才能算 `TTFC = t5b − t0`
- [ ] 彩排 3 次（全员）

## 命令
```bash
cd host && python -m pytest -q
python -m app.run                       # device :8443 / admin :8080
curl -s -X POST localhost:8080/v1/preheat -H "X-Admin-Token: dev-token"
python host/tools/smoke_ws.py
```
