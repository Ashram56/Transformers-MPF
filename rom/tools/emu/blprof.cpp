// BL target profiler: counts executed BL targets, distinct callers and first r0 values.
#include "common.h"
struct S{ unsigned long n=0; std::set<unsigned> callers; std::set<unsigned> r0s; };
static std::map<unsigned,S> m;
static void hook(unsigned pc, unsigned* r){
  unsigned w=PinmameArmRead32(pc);
  if(((w>>24)&0xf)==0xb && (w>>28)!=0xf){ int off=w&0xffffff; if(off&0x800000) off-=0x1000000; unsigned t=pc+8+off*4; S&s=m[t]; s.n++; if(s.callers.size()<2000) s.callers.insert(pc); if(s.r0s.size()<40) s.r0s.insert(r[0]); }
}
int main(int argc,char**argv){
  if(start_pinmame("tf_180",hook)) return 1;
  waitemu(0.5); for(int s:{18,19,20,21}) PinmameSetSwitch(s,1);
  waitemu(10);
  for(int k=0;k<3;k++) press(PINMAME_KEYCODE_NUMBER_5);
  waitemu(emu()+2); press(PINMAME_KEYCODE_NUMBER_1); waitemu(emu()+8);
  PinmameStop();
  for(auto&e:m){ printf("%08x n=%lu callers=%zu r0:",e.first,e.second.n,e.second.callers.size()); for(unsigned v:e.second.r0s) printf(" %x",v); printf("\n"); }
  return 0;
}
