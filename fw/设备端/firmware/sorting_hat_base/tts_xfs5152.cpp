#include "tts_xfs5152.h"

namespace voice {

namespace {

constexpr uint8_t kCmdSpeak  = 0x01;
constexpr uint8_t kCmdStop   = 0x02;
constexpr uint8_t kCmdStatus = 0x21;

// 上电后芯片要一点时间才收帧
constexpr uint32_t kBootSettleMs = 120;

inline uint32_t msPerChar(uint8_t b) { return (b >= 0x81) ? 230 : 90; }

// UTF-8 -> UTF-16（BMP，够用；4 字节的 emoji 用一个全角空格顶上，不让它把帧搞坏）
uint16_t utf8ToUtf16(const char* s, uint16_t* out, uint16_t cap) {
  uint16_t n = 0;
  const uint8_t* p = reinterpret_cast<const uint8_t*>(s);

  while (*p && n < cap) {
    const uint8_t c = *p++;
    uint32_t cp = 0;

    if (c < 0x80) {
      cp = c;
    } else if ((c & 0xE0) == 0xC0) {
      if (!*p) break;
      cp = ((uint32_t)(c & 0x1F) << 6) | (*p++ & 0x3F);
    } else if ((c & 0xF0) == 0xE0) {
      if (!p[0] || !p[1]) break;
      cp = ((uint32_t)(c & 0x0F) << 12) | ((uint32_t)(p[0] & 0x3F) << 6) | (p[1] & 0x3F);
      p += 2;
    } else if ((c & 0xF8) == 0xF0) {
      if (!p[0] || !p[1] || !p[2]) break;
      p += 3;
      cp = 0x3000;   // 超出 BMP，芯片念不了，用全角空格占位
    } else {
      continue;      // 非法字节，跳过
    }
    out[n++] = (uint16_t)cp;
  }
  return n;
}

}  // namespace

// ---------------------------------------------------------------- 通道

void XFS5152::beginI2C(TwoWire& bus, uint8_t addr7, uint32_t hz) {
  _wire = &bus;
  _addr = addr7;
  _wire->begin();
  _wire->setClock(hz);          // ≤15 kHz，手册硬要求
  delay(kBootSettleMs);
}

void XFS5152::beginUART(HardwareSerial& port, int8_t rxPin, int8_t txPin, uint32_t baud) {
  _port = &port;
  _port->begin(baud, SERIAL_8N1, rxPin, txPin);
  delay(kBootSettleMs);
}

bool XFS5152::transmit(const uint8_t* frame, uint16_t len) {
  if (_wire) {
    _wire->beginTransmission(_addr);
    // write() 有 32 字节的内部缓冲，超过会被分批，导致"一帧拆成多个事务"。
    // 所以这里有意识地分块写，块大小 < 32，但不结束事务，仍然是一个 START…STOP。
    uint16_t off = 0;
    while (off < len) {
      const uint16_t chunk = (uint16_t)((len - off) > 16 ? 16 : (len - off));
      _wire->write(frame + off, chunk);
      off = (uint16_t)(off + chunk);
    }
    return _wire->endTransmission() == 0;
  }
  if (_port) {
    _port->write(frame, len);
    _port->flush();
    return true;
  }
  return false;
}

// ---------------------------------------------------------------- 音色

void XFS5152::setStyle(uint8_t volume, uint8_t speed, uint8_t tone, int8_t speaker) {
  _volume  = volume > 10 ? 10 : volume;
  _speed   = speed  > 10 ? 10 : speed;
  _tone    = tone   > 10 ? 10 : tone;
  _speaker = (speaker < 0) ? -1 : speaker;
}

void XFS5152::markBusy(uint16_t gbkBytes) {
  _busyUntil = millis() + (uint32_t)gbkBytes * 230 + 500;   // 粗估，宁可长一点
}

// ---------------------------------------------------------------- 播报

bool XFS5152::speakGBK(const uint8_t* text, uint16_t len) {
  if (!ready() || !text || len == 0) return false;

  // 前缀：音量/语速/语调（发音人可选），12~17 字节
  char prefix[28];
  int plen;
  if (_speaker >= 0) {
    plen = snprintf(prefix, sizeof(prefix), "[v%u][s%u][t%u][m%d]",
                    _volume, _speed, _tone, _speaker);
  } else {
    plen = snprintf(prefix, sizeof(prefix), "[v%u][s%u][t%u]", _volume, _speed, _tone);
  }
  if (plen < 0) return false;

  // 帧 = FD(1) + len(2) + 编码(1) + 前缀 + 正文，整帧放在 _frame 里一次发出去
  const uint16_t used = (uint16_t)(3 + 1 + plen);
  uint16_t room = (uint16_t)(sizeof(_frame) - used);
  uint16_t textLen = len;
  if (textLen > room) {
    textLen = room;
    if (textLen & 1) textLen--;            // GBK 是双字节，别截半个字
  }

  const uint16_t dataLen = (uint16_t)(1 + plen + textLen);
  uint16_t i = 0;
  _frame[i++] = 0xFD;
  _frame[i++] = (uint8_t)(dataLen >> 8);
  _frame[i++] = (uint8_t)(dataLen & 0xFF);
  _frame[i++] = kCmdSpeak;
  _frame[i++] = (uint8_t)TTS_TEXT_ENCODING;
  memcpy(_frame + i, prefix, (size_t)plen);
  i = (uint16_t)(i + plen);
  memcpy(_frame + i, text, textLen);
  i = (uint16_t)(i + textLen);

  const bool ok = transmit(_frame, i);
  markBusy(textLen);
  return ok;
}

bool XFS5152::speakUTF8(const char* utf8) {
  if (!ready() || !utf8) return false;

  const size_t inLen = strlen(utf8);
  if (inLen == 0) return false;

  const uint16_t cap = (uint16_t)(inLen + 1);
  uint16_t* buf = static_cast<uint16_t*>(malloc(cap * sizeof(uint16_t)));
  if (!buf) return false;

  const uint16_t n = utf8ToUtf16(utf8, buf, cap);

  const uint16_t used = 3 + 1;
  uint16_t room = (uint16_t)((sizeof(_frame) - used) / 2);
  const uint16_t take = (n > room) ? room : n;

  const uint16_t dataLen = (uint16_t)(1 + take * 2);
  uint16_t i = 0;
  _frame[i++] = 0xFD;
  _frame[i++] = (uint8_t)(dataLen >> 8);
  _frame[i++] = (uint8_t)(dataLen & 0xFF);
  _frame[i++] = kCmdSpeak;
  _frame[i++] = 0x03;                       // UNICODE
  for (uint16_t k = 0; k < take; ++k) {
    const uint16_t u = buf[k];
#if TTS_UNICODE_BIG_ENDIAN
    _frame[i++] = (uint8_t)(u >> 8);
    _frame[i++] = (uint8_t)(u & 0xFF);
#else
    _frame[i++] = (uint8_t)(u & 0xFF);
    _frame[i++] = (uint8_t)(u >> 8);
#endif
  }
  free(buf);

  const bool ok = transmit(_frame, i);
  _busyUntil = millis() + (uint32_t)(take / 2 + 1) * 230 + 500;
  return ok;
}

void XFS5152::stop() {
  // 停止命令的数据区只有命令字 1 字节，所以长度字段是 0x0001，整帧 4 字节
  const uint8_t f4[4] = {0xFD, 0x00, 0x01, kCmdStop};
  transmit(f4, 4);
  _busyUntil = millis();      // 立刻解除忙状态
}

bool XFS5152::stopOk() {
  if (!ready()) return false;
  const uint8_t f4[4] = {0xFD, 0x00, 0x01, kCmdStop};
  const bool ok = transmit(f4, 4);
  _busyUntil = millis();
  return ok;
}

uint8_t XFS5152::pollStatus() {
  if (!_wire) return 0;
  const uint8_t got = _wire->requestFrom((uint16_t)_addr, (size_t)1);
  if (got != 1) return 0;
  const uint8_t v = (uint8_t)_wire->read();
  if (v == 0x41 || v == 0x45 || v == 0x4A || v == 0x4E || v == 0x4F) return v;
  return 0;
}

}  // namespace voice
