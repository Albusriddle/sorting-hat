# 固件（ESP32-S3）

> 本目录是**骨架**：路线①用官方固件，只改服务器地址/关唤醒词/改灯色；路线②自建。
> 上游锁定：见 `UPSTREAM.md`（赛期不 `git pull`）。

## 六态（G1 冻结）
OFF / ARMED / LISTENING / THINKING / SPEAKING / ERROR（OFFLINE 复用 ARMED 黄常亮）

## 离线模式
- 6.5 s 无声 → 帽子主动救场（预录）
- 15 s 仍无声 → `bye{silence}`
- 拔网 → 1.2 s 检测、5 s 按钮模式就绪（4 题按钮 + esp-tts）
