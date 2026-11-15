// 语法检查用的最小 Arduino 桩（不参与固件构建，只给宿主机 g++ 用）
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>

#define SERIAL_8N1 0x800001c
#define HEX 16

class String {
 public:
  String() {}
  String(const char* s) : s_(s ? s : "") {}
  unsigned length() const { return (unsigned)s_.size(); }
  char operator[](unsigned i) const { return s_[i]; }
  String& operator+=(char c) { s_ += c; return *this; }
  const char* c_str() const { return s_.c_str(); }
 private:
  std::string s_;
};

struct SerialClass {
  void begin(unsigned long) {}
  int available() { return 0; }
  int read() { return -1; }
  void printf(const char*, ...) {}
  void println(const char* = "") {}
  void print(const char* = "") {}
  void print(int, int = 10) {}
  void println(int, int = 10) {}
};

class HardwareSerial {
 public:
  void begin(unsigned long, uint32_t, int8_t, int8_t) {}
  size_t write(uint8_t) { return 1; }
  size_t write(const uint8_t*, size_t) { return 0; }
  void flush() {}
};

extern SerialClass Serial;
extern HardwareSerial Serial1;

inline void delay(unsigned long) {}
inline unsigned long millis() { return 0; }

#ifndef constrain
#define constrain(x, a, b) ((x) < (a) ? (a) : ((x) > (b) ? (b) : (x)))
#endif

// ---- Arduino 数字 IO（板子包的 API）----
#define INPUT 0x01
#define OUTPUT 0x03
#define INPUT_PULLUP 0x05
#define HIGH 0x1
#define LOW 0x0
inline void pinMode(int, int) {}
inline int digitalRead(int) { return 1; }
inline void digitalWrite(int, int) {}
