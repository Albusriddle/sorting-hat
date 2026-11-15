#include "asr_wonderecho.h"

namespace voice {

bool WonderEcho::probe(uint8_t addr) {
  if (!_bus) return false;
  _bus->beginTransmission(addr);
  return _bus->endTransmission() == 0;
}

bool WonderEcho::begin(TwoWire& bus, int8_t sda, int8_t scl, uint32_t hz) {
  _bus = &bus;
  _bus->begin(sda, scl, hz);
  delay(10);

  // 按顺序探测老款(0x0F)和新款(0x34/0x33)，并自动匹配对应的结果寄存器
  uint8_t candidates[] = {_addr, kAddrOld, kAddrDefault, kAddrAlt};
  for (uint8_t alt : candidates) {
    if (probe(alt)) {
      _addr   = alt;
      _online = true;
      // 老款 0x0F 用 0x00 寄存器；新款 0x34/0x33 用 0x64 寄存器
      _regResult = (alt == kAddrOld) ? 0x00 : 0x64;
      Serial.printf("[ASR] 在 0x%02X 找到模块（结果寄存器: 0x%02X）\n", _addr, _regResult);
      return true;
    }
  }
  _online = false;
  return false;
}

uint8_t WonderEcho::readRaw() {
  if (!_online || !_bus) return 0x00;

  _bus->beginTransmission(_addr);
  _bus->write(_regResult);
  if (_bus->endTransmission(false) != 0) return 0x00;

  if (_bus->requestFrom((uint16_t)_addr, (size_t)1) != 1) return 0x00;
  return _bus->read();
}

uint8_t WonderEcho::poll(uint32_t nowMs) {
  const uint8_t v = readRaw();

  if (v == 0x00 || v == 0xFF) {
    _lastId = 0x00;
    return 0x00;
  }

  if (v == _lastId) return 0x00;
  if ((uint32_t)(nowMs - _lastAt) < _minGap) return 0x00;

  _lastId = v;
  _lastAt = nowMs;
  return v;
}

bool WonderEcho::broadcast(uint8_t id, bool commandWord) {
  if (!_online || !_bus) return false;
  if (_addr == kAddrOld) return false; // 老款纯识别模块无内置播报功能

  _bus->beginTransmission(_addr);
  _bus->write(0x6E);
  _bus->write((uint8_t)(commandWord ? 0x00 : 0xFF));
  _bus->write(id);
  return _bus->endTransmission() == 0;
}

}  // namespace voice