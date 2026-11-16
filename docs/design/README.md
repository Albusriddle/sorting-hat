> **历史快照（2026-11-15）**：以下文档描述的是 ESP32-S3 + INMP441 + MAX98357A + xiaozhi 路线的设计。
> 11-16 实物改为 ESP32-WROOM-32D + LD3320A + XFS5152、Arduino 自建固件，**这些文档中的硬件/协议字段（`t` 键、`opus/24k`、`hello/caps`）已不适用**。
> 现状以根目录 `README.md`、`docs/00-protocol.md`、`host/app/protocol.py` 为准。

# 设计文档归档

> 这些文档是「掂量帽 / Sorting Hat」在 2026-11-15 一天的产出，按评审流水线归档。
> 代码与文档同版本；如冲突，以 `docs/design/00-protocol.md` 与 `docs/design/unified-standard.md` 为准。

## 主文档

| 文件 | 内容 | 来源 |
|---|---|---|
| `feasibility.md` | 可行性、技术选型、72 小时执行方案 | 五路评审汇总 |
| `architecture.md` | 上位机 / 下位机 / 硬件三层分工、接口契约、故障责任 | 架构评审 |
| `unified-standard.md` | 统一工程准则：事实源、错误码、G0–G8、六态、仓库施工 | 双盲→复核→合并 |
| `host-plan.md` | 上位机方案：功能、接口全表、选型、降级、加分项 | 双盲→复核→合并 |
| `execution-plan.md` | 执行路线 P0–P4、Gate、命令清单、验收 | 执行评审 |
| `00-protocol.md` | 会话协议 v1（WSS + Opus + JSON） | 协议设计 |

## 五个角度的评审（`reviews/`）

| 文件 | 角度 | 关键结论 |
|---|---|---|
| `01-acoustic.md` | 结构与声学 | 半双工；1 m 75 dBA 是天花板；电池放帽箍 |
| `02-edge.md` | 端侧语音 | 端侧只做四件事；0.22× 实时是「快 4.5 倍」 |
| `03-cloud.md` | 云侧管线 | Transcribe + Bedrock + CosyVoice；Nova Sonic 无中文 |
| `04-experience.md` | 体验与 IP | 帽子先开口；IP 降 B 级 |
| `05-exec.md` | 赛事执行 | 83 人时 vs 87 人时；11/17 24:00 交 v1 |

## 上位机四份角度分析（`host/`）

`01-device-api.md`（对下位机接口）、`02-voice-orchestration.md`（Provider 契约与降级）、`03-runtime-ops.md`（部署与成本）、`04-console-ops.md`（大屏/档案/运营），以及 `review.md`（第三人复核）。

## 统一准则的第三人复核（`unified/review.md`）

对双盲两版（甲/乙）的交叉比对、16 处事实冲突、遗漏项与新流程图评估。

> 双盲原稿（甲/乙）与盲评输入未归档到仓库，保留在工作区 `sortinghat/**/blind/`。
