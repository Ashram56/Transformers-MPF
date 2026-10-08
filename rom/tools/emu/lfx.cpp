// tf_180 lamp-effect (leff) capture, port of Tron's mpf_package/tools/lfx.cpp.
// Starts a game, leaves the ball in the shooter lane, then starts each leff in turn (injected leff_start
// call at task_sleep) and logs only the lamps the leff itself owns, on every lamp compositor tick.
// usage: lfx LOG MODE id[:param] ...   MODE = game | attract
#include "common.h"
// ---- tf_180 addresses (code)
#define A_TASK_SLEEP 0xacfc
#define A_LEFF_START 0x7c10
#define A_LEFF_STOP  0xb6fc
#define A_COMPOSITOR 0x73cc       // lamp compositor tick: merges base image, leff layer and layer list
#define A_COIL_PULSE 0x5e20
#define A_COIL_FN    0x5e70
#define A_COILGRP    0x5fd4
#define A_SND_CALL   0x25044
#define A_DEFF_START 0x209b4
#define R_TASK_HEAD  0x314a0      // task list head; next at +0x1c; flags u16 +2 (0x20 = leff task); leff id u16 +0x28
#define R_TASK_CUR   0x314b0
#define R_LAYERS     0x31480      // lamp layer list: image +0..0x13 (two planes of 10 bytes), mask +0x14, owner task +0x20, next +0x24
#define R_LEFF_IMG   0x36394      // shared leff layer image (two planes) and mask
#define R_LEFF_MASK  0x363a8
#define T_LEFFS      0x040cfe00   // 12-byte records {fn, u16 flags, u16 lamp group, u16 coil group, u16 prio}
static FILE* LOG;
static std::vector<int> ids, pars; static size_t idx = 0; static int curPar = -1;
static std::atomic<int> armed{0};
enum { IDLE, RUN, STOPPING };
static int st = IDLE, cur = 0, injecting = 0; static unsigned sv[16]; static double t0 = 0, nextT = 0;
static const double CAP = 12.0;
static unsigned r16(unsigned a) { return PinmameArmRead8(a) | (PinmameArmRead8(a + 1) << 8); }
static unsigned char lastOut[30]; static int haveLast = 0; static unsigned compCalls = 0;
static int curLeff() { unsigned tk = PinmameArmRead32(R_TASK_CUR); if (!tk) return 0; if (!(r16(tk + 2) & 0x20)) return 0; return r16(tk + 0x28); }
static int taskAlive(int id) { for (unsigned tk = PinmameArmRead32(R_TASK_HEAD); tk; tk = PinmameArmRead32(tk + 0x1c)) if ((r16(tk + 2) & 0x20) && r16(tk + 0x28) == (unsigned)id) return 1; return 0; }
static void sample(double t) {
  unsigned char m[10] = {0}, p[20] = {0};
  int gl = taskAlive(cur);
  unsigned grp = r16(T_LEFFS + 6 + cur * 12);
  if (gl && grp) { for (int i = 0; i < 10; i++) { unsigned char mk = PinmameArmRead8(R_LEFF_MASK + i); m[i] |= mk; for (int pl = 0; pl < 2; pl++) p[pl * 10 + i] = (p[pl * 10 + i] & ~mk) | (PinmameArmRead8(R_LEFF_IMG + pl * 10 + i) & mk); } }
  for (unsigned L = PinmameArmRead32(R_LAYERS); L; L = PinmameArmRead32(L + 0x24)) {
    unsigned ow = PinmameArmRead32(L + 0x20); if (!ow) continue;
    if (!((r16(ow + 2) & 0x20) && r16(ow + 0x28) == (unsigned)cur)) continue;
    for (int i = 0; i < 10; i++) { unsigned char mk = PinmameArmRead8(L + 0x14 + i); m[i] |= mk; for (int pl = 0; pl < 2; pl++) p[pl * 10 + i] = (p[pl * 10 + i] & ~mk) | (PinmameArmRead8(L + pl * 10 + i) & mk); } }
  unsigned char o[30]; memcpy(o, m, 10); memcpy(o + 10, p, 20);
  if (haveLast && !memcmp(o, lastOut, 30)) return; memcpy(lastOut, o, 30); haveLast = 1;
  fprintf(LOG, "%.4f F %d ", t, cur); for (int i = 0; i < 30; i++) fprintf(LOG, "%02x", o[i]); fprintf(LOG, "\n");
}
static void hook(unsigned pc, unsigned* r) {
  switch (pc) {
  case A_COMPOSITOR: { compCalls++; if (st != IDLE) { double t = emu(); sample(t);
      if (st == RUN) { int alive = taskAlive(cur);
        if (!alive && t - t0 > 0.05) { fprintf(LOG, "%.4f END %d natural\n", t, cur); st = IDLE; haveLast = 0; nextT = t + 1.0; }
        else if (t - t0 > CAP) st = STOPPING; } } break; }
  case A_TASK_SLEEP: {
    double t = emu();
    if (injecting) { if (r[13] == sv[13]) {
        if (st == RUN) { unsigned found = 0; for (unsigned tk = PinmameArmRead32(R_TASK_HEAD); tk; tk = PinmameArmRead32(tk + 0x1c)) if ((r16(tk + 2) & 0x20) && r16(tk + 0x28) == (unsigned)cur) found = tk;
          if (found && curPar >= 0) { if (curPar >= 0x10000) { PinmameArmWrite8(found + 0x30, (curPar - 0x10000) & 0xff); PinmameArmWrite8(found + 0x31, ((curPar - 0x10000) >> 8) & 0xff); } else PinmameArmWrite8(found + 0x30, curPar); }
          fprintf(LOG, "%.4f RET %d %s par=%d\n", t, cur, found ? "created" : "refused", curPar); }
        for (int i = 0; i < 4; i++) r[i] = sv[i]; r[14] = sv[14]; injecting = 0;
        if (st == STOPPING) { fprintf(LOG, "%.4f END %d cap\n", t, cur); st = IDLE; haveLast = 0; nextT = t + 1.0; } } break; }
    if (st == STOPPING) { for (int i = 0; i < 16; i++) sv[i] = r[i]; r[0] = cur; r[14] = A_TASK_SLEEP; r[15] = A_LEFF_STOP; injecting = 1; break; }
    if (armed && st == IDLE && t >= nextT && idx < ids.size()) {
      curPar = pars[idx]; cur = ids[idx++]; for (int i = 0; i < 16; i++) sv[i] = r[i]; r[0] = cur; r[14] = A_TASK_SLEEP; r[15] = A_LEFF_START; injecting = 1; st = RUN; t0 = t; haveLast = 0;
      fprintf(LOG, "%.4f BEGIN %d par=%d\n", t, cur, curPar);
    }
    break; }
  case A_COIL_PULSE: case A_COIL_FN: { int l = curLeff(); if (l) fprintf(LOG, "%.4f COIL %d coil=%u ms=%u fn=%x\n", emu(), l, r[0] & 0xff, r[1] & 0xffff, pc); break; }
  case A_COILGRP: { int l = curLeff(); if (l) fprintf(LOG, "%.4f COILGRP %d grp=%u ms=%u\n", emu(), l, r[0] & 0xffff, r[1] & 0xffff); break; }
  case A_SND_CALL: { int l = curLeff(); if (l) fprintf(LOG, "%.4f SND %d call=%x\n", emu(), l, r[0] & 0xffff); break; }
  case A_LEFF_START: { if (!injecting || r[0] != (unsigned)cur) fprintf(LOG, "%.4f LEFFSTART %u lr=%x inleff=%d\n", emu(), r[0] & 0xffff, r[14], curLeff()); break; }
  case A_DEFF_START: { int l = curLeff(); if (l) fprintf(LOG, "%.4f DEFF %u inleff=%d\n", emu(), r[0] & 0xffff, l); break; }
  }
}
int main(int argc, char** argv) {
  LOG = fopen(argv[1], "w"); const char* mode = argv[2];
  for (int i = 3; i < argc; i++) { char* c = strchr(argv[i], ':'); ids.push_back(atoi(argv[i])); if (!c) pars.push_back(-1); else if (c[1] == 'h') pars.push_back(0x10000 + atoi(c + 2)); else pars.push_back(atoi(c + 1)); }
  if (start_pinmame("tf_180", hook)) return 1;
  waitemu(0.5); for (int s : {18, 19, 20, 21, 44}) PinmameSetSwitch(s, 1);
  waitemu(8);
  if (!strcmp(mode, "game")) {
    for (int k = 0; k < 4; k++) press(PINMAME_KEYCODE_NUMBER_5, 0.3);
    waitemu(emu() + 1); press(PINMAME_KEYCODE_NUMBER_1, 0.3);
    int ej = 0; double tEnd = emu() + 8;
    while (emu() < tEnd) { if (!ej && PinmameGetSolenoid(1) > 0) { ej = 1; PinmameSetSwitch(21, 0); PinmameSetSwitch(23, 1); fprintf(LOG, "%.4f SIM eject\n", emu()); } std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
  }
  fprintf(LOG, "%.4f READY comp=%u\n", emu(), compCalls);
  for (unsigned tk = PinmameArmRead32(R_TASK_HEAD); tk; tk = PinmameArmRead32(tk + 0x1c)) if (r16(tk + 2) & 0x20) fprintf(LOG, "RUNNING leff %u prio %u flags %x\n", r16(tk + 0x28), PinmameArmRead8(tk + 0x2a), r16(tk + 0x2c));
  nextT = emu() + 0.5; armed = 1;
  while (!(idx >= ids.size() && st == IDLE)) { std::this_thread::sleep_for(std::chrono::milliseconds(20)); fflush(LOG); }
  fprintf(LOG, "%.4f DONE comp=%u\n", emu(), compCalls);
  PinmameStop(); fclose(LOG); return 0;
}
