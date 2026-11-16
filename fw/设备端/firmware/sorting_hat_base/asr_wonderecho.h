#pragma once

#include <Arduino.h>
#include <Wire.h>

namespace voice {

class WonderEcho {
 public:
  // 0x79 是官方说明书与官方 ESP32 例程（ASRcontrol.ino: I2C_ADDR 0x79）给出的地址，
  // 结果寄存器 100(0x64)。放在第一个试，命中率最高。
  static constexpr uint8_t kAddrOffic   = 0x79;
  static constexpr uint8_t kAddrOld     = 0x0F; // 老款幻尔 ASR v1.0 默认地址
  static constexpr uint8_t kAddrDefault = 0x34; // 新款 WonderEcho 默认地址
  static constexpr uint8_t kAddrAlt     = 0x33;

  explicit WonderEcho(uint8_t addr = kAddrOffic) : _addr(addr) {}

  // 自动探测顺序：0x79 (官方) -> 0x0F (老款) -> 0x34 -> 0x33
  bool begin(TwoWire& bus = Wire, int8_t sda = 16, int8_t scl = 17, uint32_t hz = 100000);

  bool    online()  const { return _online; }
  uint8_t address() const { return _addr; }

  uint8_t readRaw();
  uint8_t poll(uint32_t nowMs);
  bool broadcast(uint8_t id, bool commandWord = true);

  // ---- 词条写入（仅官方版 0x79 支持；寄存器地址取自官方 ESP32 例程）----
  // eraseWords(): 写寄存器 101，擦除全部词条，之后 delay(60) 等它完成
  // addWords():   写寄存器 160，格式 = 识别号(1B) + 拼音(汉字间用空格，如 "kai shi")
  //               词条会按调用顺序排队添加，可掉电保存
  // setMode():    写寄存器 102，1=循环识别 2=口令模式(第一个词条作唤醒) 3=按键
  bool eraseWords();
  bool addWords(uint8_t id, const char* pinyin);
  bool setMode(uint8_t mode);

  void setMinGap(uint32_t ms) { _minGap = ms; }
  void forgetLast()           { _lastId = 0x00; }

 private:
  bool probe(uint8_t addr);

  TwoWire* _bus        = nullptr;
  uint8_t  _addr;
  uint8_t  _regResult  = 0x00; // 老款默认 0x00，探测到 0x34/0x33 时自动切换为 0x64
  bool     _online     = false;
  uint8_t  _lastId     = 0x00;
  uint32_t _lastAt     = 0;
  uint32_t _minGap     = 250;
};

}  // namespace voice