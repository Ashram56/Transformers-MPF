// tf_180 display-effect tracer (port of the Tron mpf_package/tools/tracer.cpp).
// usage: tracer MODE DUR LOG DMD [deff ids...]   MODE = attract | game (force deffs during a running game)
// env POKE="addr=value[:size],..." writes RAM (size 1/2/4 bytes, default 4) just before each forced deff starts,
// so the logged printf arguments (TXTSRC ... args=) can be matched to the RAM they were read from.
#include "common.h"
// ---- tf_180 addresses (code)
#define A_TASK_SLEEP 0xacfc
#define A_DEFF_START 0x209b4      // deff_start(id, a, b)
#define A_DEFF_CORE  0x20498      // deff_start core(id, a, b, c)
#define A_SHOW_PAGES 0x20134
#define A_BMP_DRAW   0x23d28      // bitmap_draw(img, page, x, y, ...)
#define A_BMP_DRAW2  0x23c7c
#define A_BLIT       0x23ba4
#define A_BLIT2      0x23a98
#define A_SND_CALL   0x25044      // snd_resolve_call(call, handle, &idx, flag)
#define A_SND_PLAY   0x251f4      // snd_play(call)
#define A_TEXT       0x21878      // text_draw_str(str, page_addr, font, flags, x, y, color)
#define A_TEXT_FIT   0x21b90      // text_draw_str_fit(str, page_addr, font, flags, x, y, color, width)
#define A_LEFF_START 0x7c10
#define A_EVENT      0x6e50
#define A_AUDIT      0xc3c
#define R_CUR_TASK   0x314b0
#define R_ACT_DEFF   0x32464
static FILE* LOG; static FILE* DMD;
static std::vector<int> force; static size_t forceIdx=0; static std::atomic<int> forceArmed{0};
static double nextForce=0, forceT=0; static int curForce=-1; static int injecting=0; static unsigned sv[16];
struct Poke{ unsigned a,v,n; }; static std::vector<Poke> pokes;
static void do_pokes(){ for(auto&p:pokes){ for(unsigned i=0;i<p.n;i++){ if(p.n==4 && i==0 && !(p.a&3)){ PinmameArmWrite32(p.a,p.v); break; } PinmameArmWrite8(p.a+i,(p.v>>(8*i))&0xff);} } }
static unsigned r16(unsigned a){ return PinmameArmRead8(a) | (PinmameArmRead8(a+1)<<8); }
static void curdeff(unsigned &task, unsigned &did, unsigned &fn){ task=PinmameArmRead32(R_CUR_TASK); if(task){ did=r16(task+0x24); fn=PinmameArmRead32(task+4);} else {did=0;fn=0;} }
static void hook(unsigned pc, unsigned* r){
  if(curForce>=0 && !injecting && (pc==A_SHOW_PAGES || pc==A_TASK_SLEEP)){
    double t=emu(); unsigned act=r16(R_ACT_DEFF);
    if((t-forceT>0.3 && act!=(unsigned)curForce) || t-forceT>12.0){ fprintf(LOG,"%.4f FORCE_END %d active=%u\n",t,curForce,act); curForce=-1; nextForce=t+0.8; }
  }
  switch(pc){
  case A_DEFF_CORE: fprintf(LOG,"%.4f DEFF_START id=%u a=%u b=%u c=%u lr=%x\n",emu(),r[0],r[1],r[2],r[3],r[14]); break;
  case A_TASK_SLEEP: {
    double t=emu();
    if(injecting){ if(r[13]==sv[13]){ for(int i=0;i<4;i++) r[i]=sv[i]; r[14]=sv[14]; injecting=0; fprintf(LOG,"%.4f INJECT_RET\n",t);} break; }
    if(forceArmed && forceIdx<force.size() && curForce<0 && t>nextForce){
      curForce=force[forceIdx++]; forceT=t;
      for(int i=0;i<16;i++) sv[i]=r[i];
      do_pokes(); r[0]=curForce; r[1]=0; r[2]=1; r[14]=A_TASK_SLEEP; r[15]=A_DEFF_START; injecting=1;
      fprintf(LOG,"%.4f FORCE %d\n",t,curForce);
    }
    break; }
  case A_BMP_DRAW: case A_BMP_DRAW2: { unsigned tk,d,f; curdeff(tk,d,f);
    fprintf(LOG,"%.4f IMG %x img=%u page=%u x=%d y=%d task=%x deff=%u fn=%x lr=%x active=%u\n",emu(),pc,r[0],r[1],(int)r[2],(int)r[3],tk,d,f,r[14],r16(R_ACT_DEFF)); break; }
  case A_BLIT: case A_BLIT2: { unsigned tk,d,f; curdeff(tk,d,f);
    fprintf(LOG,"%.4f DRAW %x rid=%u x=%d y=%d task=%x deff=%u fn=%x lr=%x active=%u\n",emu(),pc,r16(r[0]),(int)r[2],(int)r[3],tk,d,f,r[14],r16(R_ACT_DEFF)); break; }
  case A_SHOW_PAGES: { unsigned tk,d,f; curdeff(tk,d,f); fprintf(LOG,"%.4f SHOW fg=%u bg=%u task=%x deff=%u active=%u\n",emu(),r[0],r[1],tk,d,r16(R_ACT_DEFF)); break; }
  case A_SND_CALL: { unsigned tk,d,f; curdeff(tk,d,f); fprintf(LOG,"%.4f SND call=%x deff=%u active=%u lr=%x\n",emu(),r[0],d,r16(R_ACT_DEFF),r[14]); break; }
  case A_SND_PLAY: { unsigned tk,d,f; curdeff(tk,d,f); fprintf(LOG,"%.4f SNDPLAY call=%x deff=%u active=%u lr=%x\n",emu(),r[0],d,r16(R_ACT_DEFF),r[14]); break; }
  case A_TEXT: case A_TEXT_FIT: { unsigned tk,d,f; curdeff(tk,d,f); char buf[160]; int k=0; for(;k<159;k++){ unsigned ch=PinmameArmRead8(r[0]+k); if(!ch) break; buf[k]=(ch=='\n')?'|':(ch<32||ch>126?'?':ch);} buf[k]=0;
    unsigned sp=r[13]; fprintf(LOG,"%.4f TEXT %x page=%d font=%u flags=%u x=%d y=%d color=%d w=%d deff=%u task=%x lr=%x str=\"%s\"\n",emu(),pc,(int)((r[1]-0x1080000)/0x1000),r[2],r[3]&0xff,(int)PinmameArmRead32(sp),(int)PinmameArmRead32(sp+4),(int)PinmameArmRead32(sp+8),pc==A_TEXT_FIT?(int)PinmameArmRead32(sp+12):-1,d,tk,r[14],buf); break; }
  case A_LEFF_START: fprintf(LOG,"%.4f LEFF id=%u lr=%x\n",emu(),r[0],r[14]); break;
  // text helpers called by effect code: log the message id or the format string, and the effect's own call site
  case 0x21660: case 0x215ac: case 0x217b4: case 0x2174c: case 0x21838: case 0x21a78: case 0x21b4c: {
    unsigned tk,d,f; curdeff(tk,d,f); if(!d) break;
    int isMsg = pc==0x21660||pc==0x215ac||pc==0x217b4||pc==0x2174c;
    // printf helpers: varargs are on the stack after the fixed (x, y, color[, width]) words: entry sp+12 for
    // 0x21660 / 0x21a78 (7 fixed args), sp+16 for 0x217b4 (8 fixed args); log the first 4 words
    char av[96]=""; if(pc==0x21660||pc==0x21a78||pc==0x217b4){ unsigned va=r[13]+(pc==0x217b4?16:12);
      snprintf(av,sizeof av," args=%u,%u,%u,%u",PinmameArmRead32(va),PinmameArmRead32(va+4),PinmameArmRead32(va+8),PinmameArmRead32(va+12)); }
    if(isMsg){ fprintf(LOG,"%.4f TXTSRC fn=%x deff=%u task=%x lr=%x msg=%u%s\n",emu(),pc,d,tk,r[14],r[0]&0xffff,av); break; }
    char buf[160]; int k=0; for(;k<159;k++){ unsigned ch=PinmameArmRead8(r[0]+k); if(!ch) break; buf[k]=(ch=='\n')?'|':(ch=='"'?'\'':(ch<32||ch>126?'?':ch));} buf[k]=0;
    fprintf(LOG,"%.4f TXTSRC fn=%x deff=%u task=%x lr=%x str=\"%s\"%s\n",emu(),pc,d,tk,r[14],buf,av); break; }
  case A_EVENT: fprintf(LOG,"%.4f EVENT %u\n",emu(),r[0]); break;
  case A_AUDIT: fprintf(LOG,"%.4f AUDIT %u lr=%x\n",emu(),r[0],r[14]); break;
  }
}
static unsigned char lastdmd[4096];
static void dmdcb(void* p){ if(memcmp(lastdmd,p,4096)==0) return; memcpy(lastdmd,p,4096); double t=emu(); fwrite(&t,8,1,DMD); fwrite(p,1,4096,DMD); }
int main(int argc,char**argv){
  const char* mode=argv[1]; double dur=atof(argv[2]);
  LOG=fopen(argv[3],"w"); DMD=fopen(argv[4],"wb"); g_dmd_cb=dmdcb;
  for(int i=5;i<argc;i++) force.push_back(atoi(argv[i]));
  if(getenv("POKE")){ char* e=strdup(getenv("POKE")); for(char* t=strtok(e,",");t;t=strtok(0,",")){ Poke p{0,0,4}; char* q=strchr(t,'='); if(!q) continue;
      p.a=strtoul(t,0,0); p.v=strtoul(q+1,&q,0); if(*q==':') p.n=atoi(q+1); pokes.push_back(p); } }
  if(start_pinmame("tf_180",hook)) return 1;
  waitemu(0.5); for(int s:{18,19,20,21}) PinmameSetSwitch(s,1);
  waitemu(8);
  if(!strcmp(mode,"game")){
    for(int k=0;k<4;k++) press(PINMAME_KEYCODE_NUMBER_5,0.3);
    waitemu(emu()+1); press(PINMAME_KEYCODE_NUMBER_1,0.3);
  }
  nextForce=emu()+4; forceArmed=1;
  double t0=emu();
  while(emu()<t0+dur){
    if(!force.empty() && forceIdx>=force.size() && curForce<0 && emu()>nextForce) break;
    std::this_thread::sleep_for(std::chrono::milliseconds(5)); fflush(LOG);
  }
  PinmameStop(); fclose(LOG); fclose(DMD); return 0;
}
