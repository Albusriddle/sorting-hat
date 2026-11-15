// ============================================================
// tts_xfs5152.h  ——  幻尔语音合成模块（XFS5152CE / 科大讯飞）驱动
//
// 这块芯片同时支持 UART / I2C / SPI（官方手册 6 章），幻尔的不同批次
// 模块只引出其中一种，所以驱动做成两条通道，编译期不选、运行期选：
//   beginI2C(两线, 0x40)   —— 你手上这块（只有 SCL/SDA，没有 TXD/RXD）
//   beginUART(串口, rx, tx) —— 如果有天换到 UART 版模块
//
// 两种通道发的是**同一套帧**：
//   ｜0xFD｜len_H｜len_L｜数据区｜
//   len = 数据区字节数 = 命令字(1) + 参数，不含 0xFD 和长度两字节
//   0x01 合成：参数 = 编码格式(1) + 文本   编码 0x00 GB2312 / 0x01 GBK / 0x02 BIG5 / 0x03 UNICODE
//   0x02 停止：无参数
//   0x03 暂停 / 0x04 恢复 / 0x21 状态查询 / 0x88 省电 / 0xFF 唤醒（官方手册表 11）
//
// I2C 三个硬约束（官方手册 6.2 节，违反必失败）：
//   ① 7 位地址是 0x40（手册上写的 0x80 是含读写位的 8 位地址）
//   ② 总线速率 **≤ 15 kHz**，所以本驱动默认 10 kHz，不是 400 kHz
//   ③ 一帧必须在一个完整的 START…STOP 事务里发完，中间不能断开
//
// 音色不走命令字，走文本内联标记：
//   [v0-10] 音量   [s0-10] 语速   [t0-10] 语调   [m0-53] 发音人
// ============================================================
#pragma once

#include <Arduino.h>
#include <Wire.h>

// 文本编码：0x00 GB2312 / 0x01 GBK / 0x03 UNICODE
// 台词表是 GBK 编出来的，所以默认 0x01；若模块不认，改成 0x00 再试
#ifndef TTS_TEXT_ENCODING
#define TTS_TEXT_ENCODING 0x01
#endif

// UNICODE 模式（speakUTF8 用）的字节序：多数讯飞芯片是小端。
// 如果发出的是满屏乱码或干脆不响，把这里改成 1 试大端。
#ifndef TTS_UNICODE_BIG_ENDIAN
#define TTS_UNICODE_BIG_ENDIAN 0
#endif

// I2C 时钟：手册要求 ≤15 kHz。10 kHz 下 30 字节一帧约 27 ms，够用。
#ifndef TTS_I2C_HZ
#define TTS_I2C_HZ 10000
#endif

namespace voice {

class XFS5152 {
 public:
  // ---- 通道 ----
  // I2C 版模块：两线 + 7 位地址。begin 之后驱动自己负责 setClock。
  void beginI2C(TwoWire& bus, uint8_t addr7 = 0x40, uint32_t hz = TTS_I2C_HZ);

  // UART 版模块：rxPin 接模块 TXD，txPin 接模块 RXD
  void beginUART(HardwareSerial& port, int8_t rxPin, int8_t txPin, uint32_t baud = 9600);

  bool ready() const { return _wire != nullptr || _port != nullptr; }
  bool isI2C() const { return _wire != nullptr; }

  // ---- 音色 ----
  // speaker < 0 表示不带 [m] 标记
  void setStyle(uint8_t volume, uint8_t speed, uint8_t tone, int8_t speaker = -1);

  // ---- 播报 ----
  bool speakGBK(const uint8_t* text, uint16_t len);   // 台词表走这条（最稳）
  bool speakUTF8(const char* utf8);                   // 现场转码，走 UNICODE
  void stop();
  bool stopOk();

  // ---- 状态 ----
  // 芯片没有引出可靠的 R/B 脚，忙闲按字数估算（宁可长一点）
  bool     busy(uint32_t nowMs) const { return (int32_t)(_busyUntil - nowMs) > 0; }
  uint32_t busyUntil()          const { return _busyUntil; }
  void     waitDone()                 { while (busy(millis())) delay(10); }

  // 试着读芯片回传：0x4E 正在合成 / 0x4F 空闲 / 0x41 收到正确命令帧 / 0x45 错误帧
  // 只有 I2C 通道能读；读不到返回 0（模块没引出回传也正常，别当故障）
  uint8_t pollStatus();

 private:
  bool transmit(const uint8_t* frame, uint16_t len);
  void markBusy(uint16_t gbkBytes);

  TwoWire*        _wire = nullptr;
  HardwareSerial* _port = nullptr;
  uint8_t         _addr = 0x40;

  uint8_t  _volume  = 6;      // 0-10
  uint8_t  _speed   = 5;      // 0-10
  uint8_t  _tone    = 3;      // 0-10，3 偏低沉，配"帽子"的声线
  int8_t   _speaker = -1;
  uint32_t _busyUntil = 0;
  uint8_t  _frame[288]{};     // I2C 必须整帧一次发完，所以要缓冲
};

}  // namespace voice
