# 烧板 SOP（90 秒内完成一次重刷）

> 给任何人照做的步骤。板子到手第一次用，先走一遍，确认能独立完成。

---

## 准备（一次性）

1. 装 Arduino IDE 2.x
2. 板子管理器装 `esp32`（作者 Espressif Systems）
3. 库管理器装 `WebSockets`（Markus Sattler）、`ArduinoJson`（Benoit Blanchon）
4. 装驱动：CH340 / CP210x（板子型号决定）
5. 打开 `fw/sorting_hat_base/sorting_hat_base.ino`

---

## 每次重刷

```
① 打开固件目录      fw/sorting_hat_base/
② 确认 secrets.h    WIFI_SSID / WIFI_PASS / HOST_IP 正确
③ 板子选型          工具 → 开发板 → ESP32S3 Dev Module
④ 串口选型          工具 → 端口 → 插上板子后多出来的那个 COM
⑤ 上传              点 → 按钮，等到 "Done uploading"
⑥ 开串口监视器       波特率 115200
```

**总耗时：约 90 秒**（编译 + 上传 + 等串口）。

---

## 上传失败对照表

| 报错 | 原因 | 处理 |
|---|---|---|
| `Failed to connect to ESP32` | 板子没进下载模式 | 按住 BOOT 键，点上传，出现 `Connecting...` 后松开 |
| `No serial data received` | 端口选错 | 重新确认 COM 号 |
| `Serial port busy` | 串口监视器开着 | 关掉监视器再上传 |
| `A fatal error occurred: Could not open` | 驱动没装 | 装 CH340 或 CP210x |
| 上传成功但没日志 | 波特率不对 | 改成 115200 |

---

## 上电自检（每次刷完看这几行）

```
===== sorting hat · base =====
[BOOT] asr=ok tts=ok mic=off spk=off led=off btn=off opus=off
（听到开场白）
[NET] wifi...... ok ip=192.168.x.x
[NET] ws begin <电脑在热点里的 IP>:8443（上行 PCM 0x04）
[NET] connected
[NET] sid=s-xxxxxxxx
```

**逐行含义：**

| 行 | 含义 | 不对怎么办 |
|---|---|---|
| `asr=ok` | 幻尔 ASR 认到了 | `off` → 检查 SDA16/SCL17 接线、5V、共地 |
| `tts=ok` | XFS5152 认到了 | `off` → 检查 SDA19/SCL18 接线 |
| `mic/spk/led/btn` | 对应编译开关状态 | `off` 是没开开关，不是故障 |
| `[NET] wifi ... ok ip=` | 连上热点 | `FAIL` → SSID/密码错 |
| `[NET] sid=` | 收到上位机的 ready | 没有 → 电脑 IP 错 / 防火墙 / 上位机没跑 |

---

## 烧之前 30 秒检查

- [ ] 上位机跑着（`python tasks.py up` 那个窗口）
- [ ] 电脑和你手机在同一个热点（`ipconfig` 确认 `<电脑在热点里的 IP>` 还在）
- [ ] 代理 / VPN 已关闭
- [ ] 手机热点电量够（断网会造成假故障）
