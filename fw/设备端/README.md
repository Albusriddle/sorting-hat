# 分院帽 · 设备端（固件 + 硬件）

ESP32 固件部分。帽子通过手机热点连接上位机（FastAPI），
云端判出学院后由幻尔语音合成模块念出来。

---

## 目录

```
firmware/
  sorting_hat_base/     主工程（6 态状态机 + Wi-Fi/WS + TTS 播报）
  Step1_TTS_SMOKE/      冒烟测试：只验 TTS 出声，不联网
  I2C_SCAN/             排查工具：扫描两条 I2C 总线上的设备

hw/
  pinmap-v2.md          引脚表（唯一事实源）
  烧板SOP.md            90 秒重刷流程
  fw-README.md          给仓库 fw/ 目录用的说明

tools/
  check_build.py        编译检查（两套配置 + 真实 ESP32 宏，不需要 Arduino IDE）
  probe.py              扮演设备手敲协议，验证上位机是否正常
  make_stubs.py         生成编译检查用的 stub 头
  Arduino.h / ArduinoJson.h  stub 头
```

---

## 硬件

| 模块 | 型号 | 引脚 | 状态 |
|---|---|---|---|
| 主控 | ESP32-WROOM-32D | — | 已验证 |
| 语音识别 | 幻尔 LD3320A（I2C，板载 STC8G1K08） | SDA 16 / SCL 17 | **待排查**（`online=0`） |
| 语音合成 | 幻尔 CSK4002（I2C） | SDA 19 / SCL 18 | 已验证，四院全念对 |

完整引脚见 `hw/pinmap-v2.md`。

---

## 快速开始

### 1. 配置 Wi-Fi 和服务器地址

```bash
cp firmware/sorting_hat_base/secrets.h.example firmware/sorting_hat_base/secrets.h
```

然后编辑 `secrets.h`，填你自己的：

- `WIFI_SSID` / `WIFI_PASS`：手机热点名和密码
- `HOST_IP`：上位机电脑在这个热点里的 IPv4（Windows 跑 `ipconfig` 看 WLAN 那栏）

> `secrets.h` 已在 `.gitignore` 里，不会被提交。
> 没有它也能编译（自动退回模板），但连不上网。

**⚠ 热点 IP 每次重新开热点都可能变。** 连不上时先 `ipconfig` 核对，不一致就改 `secrets.h` 重烧。

### 2. 编译检查（不需要板子、不需要 Arduino IDE）

```bash
python tools/check_build.py firmware/sorting_hat_base
```

两套配置都会跑：硬件开关全关 / 全开。改完代码先跑这个。

### 3. 烧录

用 Arduino IDE，开发板选 **ESP32 Dev Module**，串口 115200。

推荐顺序：

1. 烧 `firmware/Step1_TTS_SMOKE` —— 听到"分院帽醒了"再往下走
2. 烧 `firmware/I2C_SCAN` —— 确认两个语音模块都被扫到
3. 烧 `firmware/sorting_hat_base` —— 主程序

### 4. 串口命令（没有外设时手动驱动）

| 键 | 作用 |
|---|---|
| `w` | 模拟唤醒，进入 LISTENING |
| `e` | 模拟"说完了"，触发一次完整会话 |
| `b` | 打断 |
| `x` | 进入故障态再恢复 |
| `o` | 手动进入离线模式 |
| `k` | 打印当前 VAD 能量 |
| `p` | 打印词条表 |
| `A` `B` `C` `D` | 模拟识别到第 1/2/3/4 号词条 |
| `a` / `1`-`4` | 试听开场白 / 四院预录句 |

---

## 编译开关

全部在 `firmware/sorting_hat_base/hat_config.h`，默认**全关**。

| 开关 | 作用 | 默认 |
|---|---|---|
| `HAT_ENABLE_MIC` | INMP441 麦克风（I2S） | 关 |
| `HAT_ENABLE_SPK` | MAX98357A 喇叭（I2S） | 关 |
| `HAT_ENABLE_LED` | WS2812 灯环 | 关 |
| `HAT_ENABLE_BTN` | 按钮 | 关 |
| `HAT_ENABLE_OPUS` | Opus 编解码 | 关 |
| `HAT_ENABLE_VAD` | 能量 VAD（依赖 MIC） | 关 |

**注意：** 当前板子是普通 ESP32，`PIN_LED 48` 在它上面不存在；
`PIN_MIC_SD 6` 可能被板载 flash 占用。打开这两个开关前要先改引脚。

---

## 协议

以 `host/app/protocol.py` 为准：

- 信封键是 `type`（不是老文档的 `t`）
- 上行：`0x01` Opus 或 `0x04` PCM（16 kHz / 单声道 / 20 ms）
- 下行：`0x02` + seq(u32 BE) + 载荷，**实测是 16 kHz PCM**（`ready` 报的 24k 不准确，
  固件按帧长反推采样率）
- 鉴权：WebSocket URL 带 `?token=`（`setAuthorization` 头在实测中未生效）

---

## 已知问题

| 问题 | 影响 | 状态 |
|---|---|---|
| ASR 模块 `online=0` | 唤醒词不可用，只能用串口 `w` 模拟 | 待排查接线 |
| LD3320A 词条改不了 | 唤醒词可能不是"分院帽" | 待确认烧录工具 |
| 上位机不处理 `text` 消息 | 判学院与观众说的话无关 | 待上位机侧修改 |
| 热点 IP 会变 | 连不上上位机 | 每次核对 `ipconfig` |
