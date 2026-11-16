# 掂量帽 / Sorting Hat —— 交付仓库

三层：`hw/`（硬件与实测）、`fw/设备端/`（下位机，ESP32-WROOM-32D + Arduino）、`host/`（上位机，Python）。

## 快速开始（只跑上位机）

```bash
cd host
cp .env.example .env          # 改 DEVICE_TOKEN / ADMIN_TOKEN
pip install -r requirements.txt
pip install -r requirements-audio.txt   # 可选：Opus 解码（没有就走 0x04 PCM）
python tasks.py test          # 单测（34 passed）
python tasks.py up            # device :8443 / admin :8080
# 另开一个终端
python tasks.py preheat       # 六步；degraded=preroll_placeholder 仍可上台
python tasks.py smoke         # text -> result，应看到 house 与 scores
```

> 设备端 `fw/设备端/firmware/sorting_hat_base/secrets.h` 里的 `TOKEN` 必须与上位机 `DEVICE_TOKEN` 一致，否则设备收到 403。

## 当前形态（2026-11-16）

- 硬件：ESP32-WROOM-32D + 幻尔 LD3320A（离线关键词→编号）+ XFS5152/CSK4002（I2C 合成）；**没有** INMP441 / MAX98357A。
- 因此上行没有真实音频：设备把"词条编号 → 预置台词文本"发给上位机，判决按这段文本走；音频通道（0x04）保留但当前是全零帧。
- 上位机默认 mock provider，可切 AWS（Transcribe/Bedrock/Polly，见 `docs/providers.md`）。
- 宣布句由设备本地 TTS 念院名；桥接句由上位机下发、设备用 `speakUTF8` 念。

## 目录

```
hw/            引脚、BOM、实测记录
fw/设备端/      固件（Arduino 工程）+ 生成器 + 编译检查脚本
host/          上位机：网关/编排/判决/provider/观测/测试
docs/          providers、runbook、协议说明；docs/design/ 是 11-15 设计快照（历史）
fixtures/      回放样例
release/       提交物
```

## 文档

- 协议与实现：`host/app/protocol.py`（线上事实源）；`docs/00-protocol.md`（现状 + 历史说明）
- Provider 切换：`docs/providers.md`
- 上台手册：`docs/runbook.md`
- 设计快照（历史）：`docs/design/README.md`
