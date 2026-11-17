# 进度（截至 2026-11-17 02:40）

## 已完成（本机可复现）

| # | 事项 | 证据 |
|---|---|---|
| 1 | 仓库七目录 + 实物版 pinmap/bom | `python tools/check_tree.py`；`hw/pinmap.md`、`hw/bom.csv` |
| 2 | 上位机网关/编排/判决/管理面/大屏 | `python tasks.py up`；`/healthz`、`/stats` |
| 3 | 六步预热（preroll 可选） | `python tasks.py preheat` → `ok:true`，`degraded=[preroll_placeholder]` |
| 4 | 端到端冒烟（无设备） | `python tasks.py smoke` → `house=loyalty`、`scores`、`announce` |
| 5 | 单测 | `python tasks.py test` → **60 passed** |
| 6 | 设备端固件（Arduino） | `fw/设备端/firmware/sorting_hat_base/`（A 上传） |
| 7 | 学院名双套 + 编译开关 | `gen_phrases.py` 生成；`HAT_HOUSE_ORIGINAL` 切换 |
| 8 | 词条映射 → text 通路 | 设备 `hat_intent`；host `text` 分支；冒烟验证 |
| 9 | 零音频闸 / 鉴权等值 / halt / watchdog / 落库 | 两轮修复见 `docs/fix-report-2026-11-16.md` |

## 待办（需要硬件/凭证）

- [ ] **烧板验证** S-05（学院名）、S-07（桥接句出声）、S-08（唤醒 5 号、按钮入口）——需要 Arduino IDE
- [ ] AWS 凭证（`ASR_PROVIDER/LLM_PROVIDER/TTS_PROVIDER=aws` 后 `preheat` 全绿）
- [ ] 12 句正式预录（**可选**；`PRERECORD_REQUIRED=1` 才强制）
- [ ] 真实麦克风（INMP441/USB 声卡）接上后把 0x04 换成真 PCM，即可启用 Transcribe
- [ ] 彩排 3 次（全员）

## 命令

```bash
cd host
export DEVICE_TOKEN=dev-token ADMIN_TOKEN=dev-token   # .env 不自动加载
python tasks.py test                 # 60 passed
python tasks.py up                   # device :8443 / admin :8080
python tasks.py preheat
python tasks.py ready                # 200
python tasks.py smoke                # text -> result
```
