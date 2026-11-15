#pragma once

#include <Arduino.h>
#include <Wire.h>

namespace voice {

class WonderEcho {
 public:
  static constexpr uint8_t kAddrOld     = 0x0F; // 老款幻尔 ASR v1.0 默认地址
  static constexpr uint8_t kAddrDefault = 0x34; // 新款 WonderEcho 默认地址
  static constexpr uint8_t kAddrAlt     = 0x33;

  explicit WonderEcho(uint8_t addr = kAddrOld) : _addr(addr) {}

  // 自动探测顺序：指定地址 -> 0x0F (老款) -> 0x34 (新款) -> 0x33
  bool begin(TwoWire& bus = Wire, int8_t sda = 16, int8_t scl = 17, uint32_t hz = 100000);

  bool    online()  const { return _online; }
  uint8_t address() const { return _addr; }

  uint8_t readRaw();
  uint8_t poll(uint32_t nowMs);
  bool broadcast(uint8_t id, bool commandWord = true);

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