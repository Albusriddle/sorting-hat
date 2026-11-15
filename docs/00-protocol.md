# 协议（仓库内唯一事实源）

完整协议见 [`docs/design/00-protocol.md`](design/00-protocol.md)（与本仓库同版本）。
设备侧实现参考 `fw/`；服务端实现参考 `host/app/protocol.py`。

## 附：v1.1 增量（0x04 PCM 回退通道）

| 项 | 内容 |
|---|---|
| 帧类型 | `0x04` ｜ `seq u32` ｜ 16 kHz / 16-bit / 单声道 PCM |
| 方向 | 设备 → 网关 |
| 用途 | 无 libopus 时，设备并行上传一路 PCM 供 ASR 使用（带宽 ×4，零解码） |
| 兼容 | 网关同时支持 `0x01`（Opus，优先）与 `0x04`；未知类型回 `bad_frame{dropped}`，不断连 |
| 上限 | 单会话 PCM 缓冲 120 s（3.84 MB），超出丢弃并计数 |
