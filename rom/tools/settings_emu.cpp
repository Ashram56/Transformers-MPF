// settings_emu: drive the real Transformers Pro 1.80 ROM (tf_180, libpinmame + ARM hook) to verify pricing,
// audits, adjustment labels, factory defaults and the runtime service menus.
// Port of Tron's rom_data/tools/settings_emu.cpp with this ROM's addresses (call injection through the
// task_sleep 0xacfc hijack, as in tools/emu/lfx.cpp).
//
// Build: g++ -O2 -std=c++17 -I$PINMAME/src/libpinmame settings_emu.cpp -L$PINMAME/build \
//          -lpinmame -lpthread -Wl,-rpath,$PINMAME/build -o settings_emu
// Run:   PINMAME_NOJIT=1 ./settings_emu script.txt out.log
//        (fresh NVRAM per run: a temp vpm folder with roms -> ~/.pinmame/roms is made and removed)
//
// Script commands (one per line, # comments):
//   wait S                   let S emulated seconds pass
//   key K [ms]               press PinMAME key code K (3..6 = coin 1..4, 1 = start)
//   sw N [ms]                pulse switch N
//   adjset ID V              set an adjustment through the ROM's adj_set 0x43c (events 4/5 run)
//   adjpoke ID V             write the adjustment NVRAM word + ~checksum8 directly
//   call FN a0 a1 a2 a3      inject a call, print r0
//   callstr FN x0 x1 x2 x3   inject FN; a literal B is the scratch buffer; print r0 and the string in it
//   fmt FN V...              callstr FN B V for each V (adjustment formatter output)
//   audit N [SEL]            audit_value 0x1074(N, SEL=0xc0) and its text from formatter 0x40cc5e0[type]
//   menu N                   build menu N with 0xeb3c (as the service shell does) and print the item ids
//   stack V0 V1 ..           words placed at the injected call's sp (stack arguments 5..)
//   poke ADDR V [1|2|4]      write memory
//   country N                store country N in NVRAM 0x21100d8 {u8 country, u8 done, ~checksum16 0x1c50}
//                            and run the factory reset 0x728 (all adjustments to 0x3d8 defaults)
//   peek ADDR LEN            hex dump
//   credits                  print the credit-system NVRAM record 0x2111008 {s32 ladder pos, u8 credits}
//   dumpram FILE             write RAM 0x30000-0x40000 to FILE
//   adjlog 0|1               log adj_get 0x340 calls
//   mark TEXT
// Logged automatically: coin task create 0x4164, coin task 0x3f00, audit_add 0xc3c,
// event_post 0x6e50 events 0x19/0x1a (credit added / coin without credit).
#include <cstdio>
#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <mutex>
#include <atomic>
#include <condition_variable>
#include <sstream>
#include "libpinmame.h"
extern "C" {
void PinmameSetArmHook(void (*h)(unsigned int, unsigned int*));
unsigned int PinmameArmRead32(unsigned int a);
unsigned int PinmameArmRead8(unsigned int a);
void PinmameArmWrite32(unsigned int a, unsigned int d);
void PinmameArmWrite8(unsigned int a, unsigned int d);
double PinmameEmuTime();
}
// ---- TF OS addresses (code)
enum : unsigned {
  A_TASK_SLEEP = 0xacfc, A_TASK_CUR = 0x314b0, A_ADJ_GET = 0x340, A_ADJ_DEFAULT = 0x3d8, A_ADJ_SET = 0x43c,
  A_FACTORY = 0x728, A_AUDIT_ADD = 0xc3c, A_AUDIT_VALUE = 0x1074, A_CHECKSUM16 = 0x1c50, A_COUNTRY = 0x5350,
  A_EVENT_POST = 0x6e50, A_COIN_CREATE = 0x4164, A_COIN_TASK = 0x3f00, A_MENU_BUILD = 0xeb3c,
  T_ADJ = 0x040cb20c, T_AUDIT = 0x040cd5a4, T_AUDIT_FMT = 0x040cc5e0, NV_CREDITS = 0x2111008, NV_COUNTRY = 0x21100d8,
};
static unsigned SCR_SP = 0x3f400, SCR_BUF = 0x3ee80;
static FILE* OUT;
static std::mutex mu;
static void emit(const char* fmt, ...) {
  va_list ap; va_start(ap, fmt);
  std::lock_guard<std::mutex> g(mu);
  fprintf(OUT, "%.4f ", PinmameEmuTime()); vfprintf(OUT, fmt, ap); fprintf(OUT, "\n"); fflush(OUT);
  va_end(ap);
}
static unsigned r8(unsigned a){ return PinmameArmRead8(a); }
static unsigned r32(unsigned a){ return PinmameArmRead32(a); }

// ---- call injection
static std::atomic<int> injReq{0}, injDone{0};
static unsigned injFn, injArgs[4], injRet; static int injActive = 0; static unsigned sv[16];
static std::vector<unsigned> stackArgs;
static std::atomic<int> adjlog{0};

static std::mutex gmu; static std::condition_variable gcv;
static double target = 0; static bool parked = false; static bool gateOn = false;
static void gate() {
  if (!gateOn) return;
  double t = PinmameEmuTime();
  std::unique_lock<std::mutex> lk(gmu);
  if (t < target) return;
  parked = true; gcv.notify_all();
  gcv.wait(lk, [&]{ return PinmameEmuTime() < target || !gateOn; });
  parked = false;
}
static void hook(unsigned pc, unsigned* r) {
  switch (pc) {
  case A_COIN_CREATE: emit("coin_task_create task=0x%x r1=%u slot=%u credsys=%u lr=0x%x", r[0] & 0xffff, r[1] & 0xff, r[2], r[3] & 0xff, r[14]); break;
  case A_COIN_TASK: { unsigned tk = r32(A_TASK_CUR); emit("coin_task_run slot=%u credsys=%u", r32(tk + 0x38), r8(tk + 0x30)); break; }
  case A_AUDIT_ADD: emit("audit_add counter=%u n=%d lr=0x%x", r[0] & 0xffff, (int)r[1], r[14]); break;
  case A_EVENT_POST: if ((r[0] & 0xffff) == 0x19 || (r[0] & 0xffff) == 0x1a) emit("event_post 0x%x arg0=0x%x lr=0x%x", r[0] & 0xffff, r32(r[1]), r[14]); break;
  case A_ADJ_GET: if (adjlog) emit("adj_get id=%u lr=0x%x", r[0] & 0xffff, r[14]); break;
  case A_TASK_SLEEP:
    if (injActive) {
      if (r[13] == SCR_SP) { injRet = r[0]; for (int i = 0; i < 16; i++) r[i] = sv[i]; injActive = 0; injDone = 1; }
      return;
    }
    if (injReq) {
      injReq = 0;
      for (int i = 0; i < 16; i++) sv[i] = r[i];
      for (int i = 0; i < 4; i++) r[i] = injArgs[i];
      for (size_t i = 0; i < stackArgs.size(); i++) PinmameArmWrite32(SCR_SP + 4 * i, stackArgs[i]);
      r[13] = SCR_SP; r[14] = A_TASK_SLEEP; r[15] = injFn; injActive = 1;
      return;
    }
    gate(); break;
  }
}
static std::atomic<int> keys[256];
int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE k, void*) { return (int)k < 256 ? keys[(int)k].load() : 0; }
void PINMAMECALLBACK OnDisplayAvailable(int, int, PinmameDisplayLayout*, void*) {}
void PINMAMECALLBACK OnDisplayUpdated(int, void*, PinmameDisplayLayout*, void*) {}
void PINMAMECALLBACK OnState(int, void*) {}
void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL l, const char* f, va_list a, void*) { if (l == PINMAME_LOG_LEVEL_ERROR) { vfprintf(stderr, f, a); fprintf(stderr, "\n"); } }

// ---- minimal ball simulation (from tf_ref.cpp): trough 18-21, shooter 23, Optimus Prime down 44
static int sol[64], prevs[64]; static int trough = 4, shooter = 0, inplay = 0;
static double shooterAt = 0;
static void setTrough() { for (int i = 0; i < 4; i++) PinmameSetSwitch(21 - i, i < trough ? 1 : 0); }
static void sim_step() {
  double t = PinmameEmuTime();
  for (int i = 1; i < 40; i++) sol[i] = PinmameGetSolenoid(i);
  if (sol[1] > 0 && prevs[1] == 0 && trough > 0 && !shooter) { trough--; setTrough(); shooter = 1; shooterAt = t; PinmameSetSwitch(23, 1); }
  if (sol[2] > 0 && prevs[2] == 0 && shooter) { shooter = 0; inplay++; PinmameSetSwitch(23, 0); }
  if (shooter && t - shooterAt > 1.0) { shooter = 0; inplay++; PinmameSetSwitch(23, 0); }
  for (int i = 0; i < 64; i++) prevs[i] = sol[i] > 0;
}
static double emu() { return PinmameEmuTime(); }
static void step_to(double t) {
  while (emu() < t) {
    double nt = emu() + 0.005; if (nt > t) nt = t;
    std::unique_lock<std::mutex> lk(gmu); target = nt; parked = false; gcv.notify_all();
    gcv.wait(lk, [&]{ return parked; });
    lk.unlock(); sim_step();
  }
}
static unsigned do_call(unsigned fn, unsigned a0, unsigned a1, unsigned a2, unsigned a3) {
  injFn = fn; injArgs[0] = a0; injArgs[1] = a1; injArgs[2] = a2; injArgs[3] = a3; injDone = 0; injReq = 1;
  double t0 = emu();
  while (!injDone && emu() - t0 < 2.0) step_to(emu() + 0.005);
  if (!injDone) emit("call 0x%x TIMEOUT", fn);
  return injRet;
}
static int keycode(int k) {
  switch (k) { case 1: return PINMAME_KEYCODE_NUMBER_1; case 2: return PINMAME_KEYCODE_NUMBER_2; case 3: return PINMAME_KEYCODE_NUMBER_3;
    case 4: return PINMAME_KEYCODE_NUMBER_4; case 5: return PINMAME_KEYCODE_NUMBER_5; case 6: return PINMAME_KEYCODE_NUMBER_6;
    case 7: return PINMAME_KEYCODE_NUMBER_7; case 8: return PINMAME_KEYCODE_NUMBER_8; case 9: return PINMAME_KEYCODE_NUMBER_9;
    case 0: return PINMAME_KEYCODE_NUMBER_0; }
  return -1;
}
static std::string rdstr(unsigned a) {
  std::string s; for (int k = 0; k < 200; k++) { char c = (char)r8(a + k); if (!c) break; if (c == '\n') s += '|'; else if (c == '"') s += '\''; else s += c; } return s;
}
static void clrbuf() { for (int k = 0; k < 128; k++) PinmameArmWrite8(SCR_BUF + k, 0); }

int main(int argc, char** argv) {
  if (argc < 3) { fprintf(stderr, "usage: settings_emu script.txt out.log\n"); return 2; }
  FILE* sc = fopen(argv[1], "r"); if (!sc) { perror(argv[1]); return 1; }
  OUT = fopen(argv[2], "w");
  if (getenv("SCR_SP")) SCR_SP = strtoul(getenv("SCR_SP"), 0, 0);
  if (getenv("SCR_BUF")) SCR_BUF = strtoul(getenv("SCR_BUF"), 0, 0);
  PinmameConfig c = { PINMAME_AUDIO_FORMAT_INT16, 44100, "", OnState, OnDisplayAvailable, OnDisplayUpdated, NULL, NULL, NULL, NULL, NULL, NULL, IsKeyPressed, OnLog, NULL };
  std::string base = getenv("TMPDIR") ? getenv("TMPDIR") : "/tmp";
  std::string tmpl = base + "/tf_settings_XXXXXX"; std::vector<char> tb(tmpl.begin(), tmpl.end()); tb.push_back(0);
  char* dir = mkdtemp(tb.data()); if (!dir) { perror("mkdtemp"); return 1; }
  std::string roms = std::string(getenv("HOME")) + "/.pinmame/roms";
  std::string cmd = std::string("mkdir -p ") + dir + "/nvram && ln -s " + roms + " " + dir + "/roms";
  if (system(cmd.c_str()) != 0) return 1;
  snprintf((char*)c.vpmPath, PINMAME_MAX_PATH, "%s/", dir);
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(1); PinmameSetHandleMechanics(0);
  PinmameSetArmHook(hook);
  if (PinmameRun("tf_180") != PINMAME_STATUS_OK) { fprintf(stderr, "run fail\n"); return 1; }
  while (!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  while (emu() < 0.3) std::this_thread::sleep_for(std::chrono::milliseconds(2));
  { std::unique_lock<std::mutex> lk(gmu); target = emu() + 0.01; gateOn = true; }
  PinmameSetSwitch(44, 1);   // Optimus Prime starts down
  setTrough();
  step_to(8.0);
  emit("ready dip0=0x%x", PinmameGetDIP(0));
  char line[1024];
  while (fgets(line, sizeof line, sc)) {
    char* h = strchr(line, '#'); if (h) *h = 0;
    std::istringstream is(line); std::string cm; if (!(is >> cm)) continue;
    if (cm == "wait") { double s; is >> s; step_to(emu() + s); }
    else if (cm == "key") { int k; double ms = 150; is >> k >> ms; int kc = keycode(k); emit("key %d", k);
      keys[kc] = 1; step_to(emu() + ms / 1000.0); keys[kc] = 0; step_to(emu() + 0.25); }
    else if (cm == "sw") { int n; double ms = 100; is >> n >> ms; PinmameSetSwitch(n, 1); step_to(emu() + ms / 1000.0); PinmameSetSwitch(n, 0); step_to(emu() + 0.1); }
    else if (cm == "drain") { if (inplay > 0) { inplay--; trough++; setTrough(); emit("drain in_play=%d", inplay); step_to(emu() + 0.1); } }
    else if (cm == "adjlog") { int v; is >> v; adjlog = v; }
    else if (cm == "stack") { stackArgs.clear(); std::string t; while (is >> t) stackArgs.push_back((unsigned)strtoll(t.c_str(), 0, 0)); }
    else if (cm == "adjpoke") { unsigned id; int v; is >> id >> v; unsigned p = r32(T_ADJ + id * 32);
      PinmameArmWrite32(p, (unsigned)v); unsigned char s = 0; for (int i = 0; i < 4; i++) s += ((unsigned)v >> (8*i)) & 0xff; PinmameArmWrite8(p + 4, (unsigned char)~s);
      emit("adjpoke %u=%d", id, v); }
    else if (cm == "adjset") { unsigned id; int v; is >> id >> v; do_call(A_ADJ_SET, id, (unsigned)v, 0, 0); emit("adjset %u=%d -> adj_get=%d", id, v, (int)do_call(A_ADJ_GET, id, 0, 0, 0)); }
    else if (cm == "call") { std::string f, t; unsigned a[4] = {0,0,0,0}; is >> f; for (int k = 0; k < 4 && (is >> t); k++) a[k] = (unsigned)strtoll(t.c_str(), 0, 0);
      unsigned fn = strtoul(f.c_str(), 0, 16); unsigned rv = do_call(fn, a[0], a[1], a[2], a[3]); emit("call 0x%x(%d,%d,%d,%d) = %d (0x%x)", fn, (int)a[0], (int)a[1], (int)a[2], (int)a[3], (int)rv, rv); }
    else if (cm == "callstr") { std::string f, t; unsigned a[4] = {0,0,0,0}; is >> f; int bi = 0;
      for (int k = 0; k < 4 && (is >> t); k++) { if (t == "B") { a[k] = SCR_BUF; bi = k; } else a[k] = (unsigned)strtoll(t.c_str(), 0, 0); }
      unsigned fn = strtoul(f.c_str(), 0, 16); clrbuf();
      unsigned rv = do_call(fn, a[0], a[1], a[2], a[3]); emit("callstr 0x%x(%d,%d,%d,%d) buf=r%d = %d \"%s\"", fn, (int)a[0], (int)a[1], (int)a[2], (int)a[3], bi, (int)rv, rdstr(SCR_BUF).c_str()); }
    else if (cm == "fmt") { std::string f, t; is >> f; unsigned fn = strtoul(f.c_str(), 0, 16);
      while (is >> t) { int v = (int)strtoll(t.c_str(), 0, 0); clrbuf(); unsigned rv = do_call(fn, SCR_BUF, (unsigned)v, 0, 0);
        emit("fmt 0x%x %d = %d \"%s\"", fn, v, (int)rv, rdstr(SCR_BUF).c_str()); } }
    else if (cm == "audit") { unsigned n, sel = 0xc0; is >> n; std::string t; if (is >> t) sel = strtoul(t.c_str(), 0, 0);
      unsigned v = do_call(A_AUDIT_VALUE, n, sel, 0, 0); unsigned ty = r32(T_AUDIT + n * 16 + 8) & 0xffff; unsigned f = r32(T_AUDIT_FMT + 4 * ty);
      clrbuf(); if (f) do_call(f, SCR_BUF, v, sel, 0);
      emit("audit %u sel=0x%x type=%u value=%d text=\"%s\"", n, sel, ty, (int)v, rdstr(SCR_BUF).c_str()); }
    else if (cm == "menu") { unsigned n; is >> n; for (int k = 0; k < 128; k++) PinmameArmWrite8(SCR_BUF + k, 0);
      unsigned cnt = do_call(A_MENU_BUILD, n, SCR_BUF, 0, 0); std::string s; char b[16];
      for (unsigned k = 0; k < cnt && k < 60; k++) { snprintf(b, sizeof b, "%s%u", k ? "," : "", r8(SCR_BUF + 2*k) | (r8(SCR_BUF + 2*k + 1) << 8)); s += b; }
      emit("menu %u count=%u items=%s", n, cnt, s.c_str()); }
    else if (cm == "poke") { std::string f; unsigned v, sz = 1; is >> f >> v >> sz; unsigned a = strtoul(f.c_str(), 0, 16);
      if (sz == 4) PinmameArmWrite32(a, v); else if (sz == 2) { PinmameArmWrite8(a, v & 0xff); PinmameArmWrite8(a + 1, (v >> 8) & 0xff); } else PinmameArmWrite8(a, v);
      emit("poke 0x%x=%u size %u", a, v, sz); }
    else if (cm == "country") { unsigned c; is >> c;
      PinmameArmWrite8(NV_COUNTRY, c); PinmameArmWrite8(NV_COUNTRY + 1, 1); unsigned ck = ~do_call(A_CHECKSUM16, NV_COUNTRY, 2, 0, 0) & 0xffff;
      PinmameArmWrite8(NV_COUNTRY + 2, ck & 0xff); PinmameArmWrite8(NV_COUNTRY + 3, ck >> 8); do_call(A_FACTORY, 0, 0, 0, 0);
      emit("country %u -> 0x5350 returns %u", c, do_call(A_COUNTRY, 0, 0, 0, 0) & 0xff); }
    else if (cm == "peek") { std::string f; unsigned n; is >> f >> n; unsigned a = strtoul(f.c_str(), 0, 16); std::string s; char b[8];
      for (unsigned k = 0; k < n; k++) { snprintf(b, sizeof b, "%02x", r8(a + k)); s += b; if (k % 4 == 3) s += ' '; } emit("peek 0x%x %s", a, s.c_str()); }
    else if (cm == "credits") { emit("credits pos=%d credits=%u chk=0x%02x", (int)r32(NV_CREDITS), r8(NV_CREDITS + 4), r8(NV_CREDITS + 5)); }
    else if (cm == "dumpram") { std::string fn; is >> fn; FILE* f = fopen(fn.c_str(), "wb"); for (unsigned a = 0x30000; a < 0x40000; a++) fputc(r8(a), f); fclose(f); emit("dumpram %s", fn.c_str()); }
    else if (cm == "mark") { std::string rest; std::getline(is, rest); emit("mark%s", rest.c_str()); }
    else fprintf(stderr, "unknown command: %s\n", cm.c_str());
  }
  step_to(emu() + 0.2);
  emit("end");
  { std::unique_lock<std::mutex> lk(gmu); gateOn = false; gcv.notify_all(); }
  PinmameStop(); fclose(OUT);
  std::string rm = std::string("rm -rf ") + dir; if (system(rm.c_str())) {}
  return 0;
}
