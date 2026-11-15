# 引脚表（唯一事实源）

> 首行签名格式：`FROZEN G1 YYYYMMDD <SHA256 of this file>` —— 由 A 在 G1（11/15 18:00）签字。
> 任何改动必须走 RFC，并在 `fw/main/pinmap.h` 重新生成（不要手抄）。

FROZEN G1 PENDING

| 信号 | ESP32-S3 | 对端 | 备注 |
|---|---|---|---|
| I2S0_BCLK | GPIO4 | INMP441 SCK | 16 kHz / 16 bit / 单声道 |
| I2S0_WS | GPIO5 | INMP441 WS | |
| I2S0_DIN | GPIO6 | INMP441 SD | |
| I2S1_BCLK | GPIO15 | MAX98357A BCLK | 24 kHz 输出（或 16 kHz 直出） |
| I2S1_WS | GPIO16 | MAX98357A LRC | |
| I2S1_DOUT | GPIO7 | MAX98357A DIN | |
| LED_DIN | GPIO48 | WS2812 ×8 | 限亮度 30% |
| BTN | GPIO0 | 按钮（下拉） | 短按=打断，长按 2 s=静音 |
| WEAR | GPIO10 | FPC 微动（主）+ 反射近距（辅） | 200 ms 消抖 + 5 s 冷却 |
| VBAT_ADC | GPIO1 | 1/2 分压 | 低压保护 |
| MOTOR | GPIO2 | MOSFET → 偏心马达 | 可选 |
| PWR_EN | GPIO3 | 升压使能 | 深度睡眠 |

## 采样/播放格式（冻结项）

- 上行：16 kHz、16 bit、单声道、32 ms 帧；Opus 60 ms/包
- 下行：24 kHz（或 16 kHz）、16 bit、60 ms/包
- 半双工：播放时麦克风静音
