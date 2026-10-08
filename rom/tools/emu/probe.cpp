// Logs PCs whose load instructions touch the banked flash window, and bank-select writes.
#include "common.h"
static unsigned R(unsigned a){ return PinmameArmRead32(a); }
static std::map<unsigned,unsigned long> hits; static std::map<unsigned,unsigned> lastaddr;
static unsigned long nins=0;
static unsigned shiftv(unsigned w, unsigned* r){ unsigned rm=r[w&15]; unsigned sh=(w>>7)&31, ty=(w>>5)&3; if(ty==0) return rm<<sh; if(ty==1) return sh? rm>>sh:0; if(ty==2) return sh? (unsigned)((int)rm>>sh): ((int)rm<0?~0u:0); return rm; }
static void hook(unsigned pc, unsigned* r){ nins++;
  unsigned w=R(pc); unsigned rn=(w>>16)&15; unsigned base= rn==15? pc+8 : r[rn]; unsigned ea=0; bool ld=false;
  if(((w>>26)&3)==1 && (w&(1<<20))){ unsigned off= (w&(1<<25))? shiftv(w,r) : (w&0xfff); bool P=w&(1<<24), U=w&(1<<23); ea=P? (U?base+off:base-off):base; ld=true; }
  else if(((w>>25)&7)==0 && (w&(1<<20)) && (w&0x90)==0x90 && (w&0x60)){ unsigned off=(w&(1<<22))? (((w>>4)&0xf0)|(w&15)) : r[w&15]; bool P=w&(1<<24),U=w&(1<<23); ea=P?(U?base+off:base-off):base; ld=true; }
  else if(((w>>25)&7)==4 && (w&(1<<20))){ ea=base; ld=true; }
  if(ld && ea>=0x04800000 && ea<0x05000000){ hits[pc]++; lastaddr[pc]=ea; }
}
static void bus(unsigned a, unsigned d, unsigned m, int wr){ if(wr && a==0x02580000){ static unsigned last=999; if(d!=last){ last=d; } } }
int main(int argc,char**argv){
  if(start_pinmame("tf_180",hook)) return 1;
  waitemu(0.5); for(int s:{18,19,20,21}) PinmameSetSwitch(s,1);
  waitemu(6);
  for(int k=0;k<3;k++) press(PINMAME_KEYCODE_NUMBER_5);
  waitemu(emu()+3);
  press(PINMAME_KEYCODE_NUMBER_1);
  waitemu(emu()+6);
  fprintf(stderr,"emu=%f nins=%lu\n",emu(),nins); PinmameStop();
  for(auto&h:hits) printf("%08x %lu last=%08x\n",h.first,h.second,lastaddr[h.first]);
  return 0;
}
