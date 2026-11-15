#!/usr/bin/env python3
"""生成代码检查用的大号标头（Arduino 的 String / Serial 等）。"""
import io, os

HEADERS = {}

HEADERS['WiFi.h'] = r'''#pragma once
#include "Arduino.h"
enum wl_status_t { WL_IDLE_STATUS, WL_DISCONNECTED, WL_CONNECTED };
enum wifi_mode_t { WIFI_OFF, WIFI_STA, WIFI_AP };
class IPClass { public: String toString() const { return String("10.0.0.2"); } };
class WiFiClass { public:
  void mode(wifi_mode_t){}
  void begin(const char*, const char*){}
  wl_status_t status(){ return WL_CONNECTED; }
  IPClass localIP(){ return IPClass(); }
};
extern WiFiClass WiFi;
'''

# 按 Library Registry 里 WebSockets 2.6.x 的公开签名写，不是猜的
HEADERS['WebSocketsClient.h'] = r'''#pragma once
#include "Arduino.h"
enum WStype_t { WStype_ERROR = 0, WStype_DISCONNECTED, WStype_CONNECTED, WStype_TEXT,
                WStype_BIN, WStype_FRAGMENT_TEXT_START, WStype_FRAGMENT_BIN_START,
                WStype_FRAGMENT, WStype_FRAGMENT_FIN, WStype_PING, WStype_PONG };
typedef void (*WebSocketClientEvent)(WStype_t type, uint8_t * payload, size_t length);
class WebSocketsClient { public:
  void begin(const char* host, uint16_t port, const char* url = "/", const char* protocol = "arduino");
  void onEvent(WebSocketClientEvent cbEvent);
  bool sendTXT(uint8_t* payload, size_t length = 0, bool headerToPayload = false);
  bool sendTXT(const uint8_t* payload, size_t length = 0);
  bool sendTXT(char* payload, size_t length = 0, bool headerToPayload = false);
  bool sendTXT(const char* payload, size_t length = 0);
  bool sendTXT(String& payload);
  bool sendTXT(char payload);
  bool sendBIN(uint8_t* payload, size_t length, bool headerToPayload = false);
  bool sendBIN(const uint8_t* payload, size_t length);
  void setAuthorization(const char* user, const char* password);
  void setAuthorization(const char* auth);
  void enableHeartbeat(uint32_t pingInterval, uint32_t pongTimeout, uint8_t disconnectTimeoutCount);
  void setReconnectInterval(unsigned long time);
  void loop();
};
'''

HEADERS['Wire.h'] = r'''#pragma once
#include "Arduino.h"
class TwoWire { public:
  TwoWire(int num = 0) { (void)num; }
  bool begin(int = -1, int = -1, uint32_t = 0) { return true; }
  void beginTransmission(uint8_t){}
  void write(uint8_t){}
  size_t write(const uint8_t*, size_t){ return 0; }
  uint8_t endTransmission(bool = true){ return 0; }
  uint8_t requestFrom(uint16_t, size_t){ return 0; }
  int read(){ return 0; }
  void setClock(uint32_t){}
};
extern TwoWire Wire;
'''

def write_all(outdir):
    for name, body in HEADERS.items():
        full = f'{outdir}/{name}'
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with io.open(full, 'w', encoding='utf-8') as f:
            f.write(body)


HEADERS['ArduinoJson.h'] = r'''#pragma once
#include <cstring>
enum DErr { Ok, InvalidInput };
struct DeserializationError { DErr c; operator bool() const { return c != Ok; } const char* c_str() const { return c == Ok ? "Ok" : "InvalidInput"; } };
class JV { public:
  const char* s;
  JV() : s("") {} JV(const char* c) : s(c) {}
  int operator|(int d) const { return d; }
  const char* operator|(const char* d) const { return d; }
  bool operator|(bool d) const { return d; }
  JV operator[](const char* k) const { (void)k; return JV(); }
};
template <int N> struct StaticJsonDocument { JV root; JV operator[](const char* k) { return root[k]; } };
inline DeserializationError deserializeJson(StaticJsonDocument<768>&, const uint8_t*, size_t) { return DeserializationError{Ok}; }
inline size_t serializeJson(StaticJsonDocument<96>&, char* buf, size_t n) { (void)n; buf[0] = '{'; return 1; }
'''

# ---- ESP32 板子包里的硬件 API（只保留我们用到的那几个）----
HEADERS['driver/i2s.h'] = r'''#pragma once
#include "Arduino.h"
typedef int esp_err_t;
#define ESP_OK 0
typedef enum { I2S_NUM_0 = 0, I2S_NUM_1 = 1 } i2s_port_t;
typedef enum { I2S_MODE_MASTER = 1, I2S_MODE_RX = 2, I2S_MODE_TX = 4 } i2s_mode_t;
typedef enum { I2S_BITS_PER_SAMPLE_16BIT = 16, I2S_BITS_PER_SAMPLE_32BIT = 32 } i2s_bits_per_sample_t;
typedef enum { I2S_CHANNEL_FMT_ONLY_LEFT = 0 } i2s_channel_fmt_t;
typedef enum { I2S_COMM_FORMAT_STAND_I2S = 1 } i2s_comm_format_t;
#define I2S_PIN_NO_CHANGE (-1)
#define ESP_INTR_FLAG_LEVEL1 (1 << 1)
#define pdMS_TO_TICKS(x) (x)
struct i2s_config_t {
  i2s_mode_t mode; uint32_t sample_rate; i2s_bits_per_sample_t bits_per_sample;
  i2s_channel_fmt_t channel_format; i2s_comm_format_t communication_format;
  int intr_alloc_flags; int dma_buf_count; int dma_buf_len; bool use_apll; bool tx_desc_auto_clear;
};
struct i2s_pin_config_t { int mck_io_num, bck_io_num, ws_io_num, data_out_num, data_in_num; };
inline esp_err_t i2s_driver_install(i2s_port_t, const i2s_config_t*, int, void*) { return ESP_OK; }
inline esp_err_t i2s_driver_uninstall(i2s_port_t) { return ESP_OK; }
inline esp_err_t i2s_set_pin(i2s_port_t, const i2s_pin_config_t*) { return ESP_OK; }
inline esp_err_t i2s_zero_dma_buffer(i2s_port_t) { return ESP_OK; }
inline esp_err_t i2s_read(i2s_port_t, void* dst, size_t size, size_t* read, uint32_t) { memset(dst, 1, size); *read = size; return ESP_OK; }
inline esp_err_t i2s_write(i2s_port_t, const void* src, size_t size, size_t* written, uint32_t) { (void)src; *written = size; return ESP_OK; }
inline esp_err_t i2s_start(i2s_port_t) { return ESP_OK; }
inline esp_err_t i2s_stop(i2s_port_t) { return ESP_OK; }
'''

HEADERS['Adafruit_NeoPixel.h'] = r'''#pragma once
#include "Arduino.h"
#define NEO_GRB 1
#define NEO_KHZ800 2
class Adafruit_NeoPixel { public:
  Adafruit_NeoPixel(uint16_t, int16_t = -1, int16_t = 0) {}
  void begin(){} void clear(){} void show(){} void setBrightness(uint8_t){}
  void setPixelColor(uint16_t, uint32_t){}
};
'''

# ---- 可选的 Opus 库（audio-tools）----
HEADERS['AudioTools.h'] = r'''#pragma once
#include "Arduino.h"
namespace audio_tools {
struct AudioInfo { AudioInfo(uint32_t = 44100, uint16_t = 2, uint16_t = 16) {} };
class Encoder { public:
  bool begin(AudioInfo&) { return true; } void end() {}
  size_t write(const uint8_t*, size_t n) { return n; }
  size_t readBytes(uint8_t*, size_t n) { return n; }
  int available() { return 128; }
};
class Decoder : public Encoder {};
}
'''

HEADERS['AudioTools/AudioCodecs/CodecOpus.h'] = r'''#pragma once
#include "AudioTools.h"
namespace audio_tools {
class OpusAudioEncoder : public Encoder {};
class OpusAudioDecoder : public Decoder {};
}
'''

if __name__ == '__main__':
    import sys
    write_all(sys.argv[1] if len(sys.argv) > 1 else '.')
    print('wrote', ', '.join(HEADERS))
