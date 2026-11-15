#pragma once
#include <cstring>
#include <cstdio>
enum DErr { Ok, InvalidInput };
struct DeserializationError { DErr c; operator bool() const {return c!=Ok;} const char* c_str() const {return c==Ok?"Ok":"InvalidInput";} };
class JV { public: const char* s;
  JV():s(""){} JV(const char* c):s(c){}
  int operator|(int d) const {return d;}
  const char* operator|(const char* d) const {return d;}
  bool operator|(bool d) const {return d;}
  JV operator[](const char* k) const {return JV();}
  JV& operator=(const char* c){s=c;return *this;}
};
template<int N> struct StaticJsonDocument { JV root; JV operator[](const char* k){return root[k];} };
inline DeserializationError deserializeJson(StaticJsonDocument<768>& d, const uint8_t*, size_t){ return {Ok}; }
inline DeserializationError deserializeJson(StaticJsonDocument<96>& d, const uint8_t*, size_t){ return {Ok}; }
inline size_t serializeJson(StaticJsonDocument<96>& d, char* buf, size_t n){ (void)d; buf[0]='{';return 1; }
