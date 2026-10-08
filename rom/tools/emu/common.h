#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <chrono>
#include <vector>
#include <atomic>
#include <set>
#include <map>
#include "libpinmame.h"
extern "C" {
void PinmameSetArmHook(void (*h)(unsigned int, unsigned int*));
void PinmameSetBusHook(void (*h)(unsigned int, unsigned int, unsigned int, int));
unsigned int PinmameArmRead32(unsigned int a);
unsigned int PinmameArmRead8(unsigned int a);
void PinmameArmWrite32(unsigned int a, unsigned int d);
void PinmameArmWrite8(unsigned int a, unsigned int d);
double PinmameEmuTime();
}
static std::atomic<int> keys[512];
static int PINMAMECALLBACK IsKeyPressed(PINMAME_KEYCODE k, void*){ return (int)k<512 ? keys[(int)k].load():0; }
static void PINMAMECALLBACK OnState(int, void*){}
static void PINMAMECALLBACK OnLog(PINMAME_LOG_LEVEL l, const char* f, va_list a, void*){ if(l==PINMAME_LOG_LEVEL_ERROR){vfprintf(stderr,f,a);fprintf(stderr,"\n");}}
static void PINMAMECALLBACK OnDisplayAvailable(int, int, PinmameDisplayLayout*, void*){}
static void (*g_dmd_cb)(void*)=0;
static void PINMAMECALLBACK OnDisplayUpdated(int, void* p, PinmameDisplayLayout* L, void*){ if(p&&L->width==128&&L->height==32&&g_dmd_cb) g_dmd_cb(p); }
static double emu(){ return PinmameEmuTime(); }
static void waitemu(double t){ while(emu()<t) std::this_thread::sleep_for(std::chrono::milliseconds(1)); }
static void press(int key,double dt=0.25){ keys[key]=1; waitemu(emu()+dt); keys[key]=0; waitemu(emu()+0.1); }
static int start_pinmame(const char* set, void (*hook)(unsigned,unsigned*)){
  static PinmameConfig c = { PINMAME_AUDIO_FORMAT_INT16, 44100, "", OnState, OnDisplayAvailable, OnDisplayUpdated, NULL, NULL, NULL, NULL, NULL, NULL, IsKeyPressed, OnLog, NULL };
  snprintf((char*)c.vpmPath,PINMAME_MAX_PATH,"%s/.pinmame/",getenv("HOME"));
  PinmameSetConfig(&c); PinmameSetHandleKeyboard(1); PinmameSetHandleMechanics(0); PinmameSetDmdMode(PINMAME_DMD_MODE_RAW);
  if(hook) PinmameSetArmHook(hook);
  if(PinmameRun(set)!=PINMAME_STATUS_OK){ fprintf(stderr,"run fail\n"); return 1; }
  while(!PinmameIsRunning()) std::this_thread::sleep_for(std::chrono::milliseconds(10));
  return 0;
}
