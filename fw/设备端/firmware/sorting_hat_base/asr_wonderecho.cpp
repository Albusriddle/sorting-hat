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

  // 按顺序探测：官方新款(0x79) -> 老款(0x0F) -> 新款(0x34/0x33)，并自动匹配结果寄存器
  uint8_t candidates[] = {_addr, kAddrOffic, kAddrOld, kAddrDefault, kAddrAlt};
  for (uint8_t alt : candidates) {
    if (probe(alt)) {
      _addr   = alt;
      _online = true;
      // 官方版(0x79)与新款(0x34/0x33)用 0x64 寄存器；老款 0x0F 用 0x00
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

// ---------------- 词条写入（官方版 0x79）----------------
// 寄存器地址来源：官方 ESP32 例程 ASRcontrol.ino
//   ASR_WORDS_ERASE_ADDR 101 / ASR_MODE_ADDR 102 / ASR_ADD_WORDS_ADDR 160
// 老款 0x0F 不支持，直接返回 false。

bool WonderEcho::eraseWords() {
  if (!_online || !_bus || _addr == kAddrOld) return false;
  _bus->beginTransmission(_addr);
  _bus->write(101);
  const bool ok = (_bus->endTransmission() == 0);
  delay(60);                       // 官方例程：擦除需要时间
  return ok;
}

bool WonderEcho::addWords(uint8_t id, const char* pinyin) {
  if (!_online || !_bus || !pinyin || _addr == kAddrOld) return false;
  _bus->beginTransmission(_addr);
  _bus->write(160);
  _bus->write(id);
  _bus->write((const uint8_t*)pinyin, strlen(pinyin));
  const bool ok = (_bus->endTransmission() == 0);
  delay(10);                       // 官方例程：每条之后等 10ms
  return ok;
}

bool WonderEcho::setMode(uint8_t mode) {
  if (!_online || !_bus || _addr == kAddrOld) return false;
  _bus->beginTransmission(_addr);
  _bus->write(102);
  _bus->write(mode);
  return _bus->endTransmission() == 0;
}

}  // namespace voice