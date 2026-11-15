# 引脚表（唯一事实源）· 第二版

> 首行签名格式：`FROZEN G1 YYYYMMDD <SHA256 of this file>` —— 由 A 在 G1 签字。
> 任何改动必须走 RFC，并在 `fw/main/pinmap.h` 重新生成（不要手抄）。
>
> 本版改动（2026-11-16，A 起草）：
> ① 删除 WEAR（GPIO10）——"戴上帽子"动作已取消，改为语音唤醒词
> ② ASR / TTS 两路 I2C 按组长驱动代码的实际值写入（原表没有这两项）
> ③ 增加"待确认"一栏，标出与驱动代码冲突或需实测的项

FROZEN G1 PENDING（待签字）

## 1. I2C 模块（以组长驱动代码为准，已可运行）

| 信号 | 引脚 | 对端 | 总线 | 备注 |
|---|---|---|---|---|
| ASR_SDA | GPIO16 | 幻尔 WonderEcho SDA | Wire（I2C0） | 100 kHz，地址自动探测 0x0F/0x34/0x33 |
| ASR_SCL | GPIO17 | 幻尔 WonderEcho SCL | Wire（I2C0） | |
| TTS_SDA | GPIO19 | XFS5152CE SDA | Wire1（I2C1） | **10 kHz**（芯片要求 ≤15 kHz） |
| TTS_SCL | GPIO18 | XFS5152CE SCL | Wire1（I2C1） | 7 位地址 0x40 |

## 2. I2S —— 麦克风（INMP441）

| 信号 | GPIO | 对端 | 备注 |
|---|---|---|---|
| I2S0_BCLK | GPIO4 | INMP441 SCK | 16 kHz / 32 bit 读，取高 16 bit |
| I2S0_WS | GPIO5 | INMP441 WS | L/R 脚接地 = 左声道 |
| I2S0_DIN | GPIO6 | INMP441 SD | |

## 3. I2S —— 喇叭（MAX98357A）

| 信号 | GPIO | 对端 | 备注 |
|---|---|---|---|
| I2S1_BCLK | GPIO15 | MAX98357A BCLK | 下行 60 ms/帧 |
| I2S1_LRC | GPIO16 | MAX98357A LRC | ⚠ **与 ASR_SDA(GPIO16) 冲突**，见"待确认" |
| I2S1_DIN | GPIO7 | MAX98357A DIN | 16 kHz（实测，见"待确认"） |

## 4. 其它

| 信号 | GPIO | 对端 | 备注 |
|---|---|---|---|
| LED_DIN | GPIO48 | WS2812 ×8 | 亮度限 30% |
| BTN | GPIO0 | 按钮（内部上拉） | 短按=打断，长按 2 s=重连/退出离线 |
| ~~WEAR~~ | ~~GPIO10~~ | ~~FPC 微动~~ | **已删除**：不再有"戴上"动作 |

## 5. 采样/播放格式（实测确认）

- 上行：16 kHz / 16 bit / 单声道 / **20 ms(320 样本)一帧**，`0x01` Opus 或 `0x04` PCM
- 下行：**16 kHz** / 16 bit / 单声道 / **60 ms(960 样本)一帧**，`0x02` 帧（OPUS 或 PCM 自动识别）
  - ⚠ `ready.audio.out` 报 `opus/24k/60ms`，但实测 1920 字节 ÷ 60 ms = 16 kHz；固件以实测为准
- 半双工：播放期间麦克风静音

## 6. 待确认（板子到手后必须实测）

| # | 项 | 现状 | 谁确认 |
|---|---|---|---|
| 1 | ASR_SDA(GPIO16) 与 SPK_LRC(GPIO16) 冲突 | 两者都用 16 | 组长：喇叭 LRC 换到别的脚（建议 GPIO1/2/3）或确认 ASR 可改脚 |
| 2 | 板子最终型号 | 可能是 C3 | 组长：C3 只有 1 个 I2S 控制器，麦克风与喇叭不能同时用 |
| 3 | INMP441 在帽内开孔后的实际 SNR | 器件 61 dB，官方建议 ≥62 | A：实测后填 |
| 4 | MAX98357A 供电 | 5V 直供还是 3.3V | 组长：确认模块电压 |

