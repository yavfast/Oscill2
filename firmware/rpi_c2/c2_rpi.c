// Fast C2 (Silicon Labs 2-wire) bit-bang for Raspberry Pi 4 (BCM2711), direct /dev/gpiomem.
// Goal: win the reset->FPCTL-halt race so the C8051F41x firmware can't reclaim P2.0/C2D.
// Runs SCHED_FIFO + mlockall; clock-low kept short (<~1us) to avoid spurious /RST.
//
// Wiring (BCM): C2CK=GPIO23 (=/RST), C2D=GPIO24 (=P2.0). GND common. 3.3V direct, no shifter.
// C8051F41x: DEVICEID@0x00=0x0C, REVID@0x01, FPCTL@0x02, FPDAT@0xB4. Block Read cmd=0x06.
// INS (LSB-first): DataRead=00 DataWrite=01 AddrRead=10 AddrWrite=11.  Status OK=0x0D.
//
// Build (on RPi):  gcc -O2 -o c2_rpi c2_rpi.c
// Run:  sudo ./c2_rpi id      # fast no-halt Device ID read (non-destructive)
//       sudo ./c2_rpi halt    # FPCTL halt + FPDAT Get Version + guarded Block Read (FREEZES scope)
// ERASE-SAFE: only ever issues 0x06 (Block Read); args gated on status 0x0D; count=0x10.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sched.h>
#include <time.h>

#define C2CK 23
#define C2D  24
#define GPIO_LEN 0x1000

static volatile uint32_t *gpio;

// BCM2711 GPIO register word-indices (from /dev/gpiomem base = GPFSEL0)
#define GPSET0 7
#define GPCLR0 10
#define GPLEV0 13
static inline void set_output(int p){ int i=p/10,s=3*(p%10); gpio[i]=(gpio[i]&~(7u<<s))|(1u<<s); }
static inline void set_input(int p){  int i=p/10,s=3*(p%10); gpio[i]&=~(7u<<s); }
static inline void pin_hi(int p){ gpio[GPSET0]=1u<<p; }
static inline void pin_lo(int p){ gpio[GPCLR0]=1u<<p; }
static inline int  pin_lev(int p){ return (gpio[GPLEV0]>>p)&1; }

static inline void busy_ns(long ns){
    struct timespec a,b; clock_gettime(CLOCK_MONOTONIC,&a);
    for(;;){ clock_gettime(CLOCK_MONOTONIC,&b);
        long e=(b.tv_sec-a.tv_sec)*1000000000L+(b.tv_nsec-a.tv_nsec);
        if(e>=ns) return; }
}

// C2D helpers (push-pull, like the proven Due/x893 driver)
static inline void dH(){ set_output(C2D); pin_hi(C2D); }
static inline void dL(){ set_output(C2D); pin_lo(C2D); }
static inline void dIn(){ set_input(C2D); }
static inline int  dR(){ return pin_lev(C2D); }

static long T_LOW=300, T_HIGH=500;   // ns; env C2_TLOW/C2_THIGH override (tune halt-race vs F41x)

static inline void pulse(){
    pin_lo(C2CK); busy_ns(T_LOW);
    pin_hi(C2CK); busy_ns(T_HIGH);
}
static void send_bits(unsigned v,int n){
    for(int i=0;i<n;i++){ if((v>>i)&1) dH(); else dL(); pulse(); }
}
static void c2_reset(){ pin_lo(C2CK); busy_ns(25000); pin_hi(C2CK); busy_ns(3000); }

static void c2_write_ar(unsigned a){ pulse(); send_bits(3,2); send_bits(a,8); dIn(); pulse(); }
static int  c2_read_ar(){ pulse(); send_bits(2,2); dIn(); int d=0;
    for(int i=0;i<8;i++){ pulse(); d>>=1; if(dR()) d|=0x80; } pulse(); return d; }
static int  c2_write_dr(unsigned v){ pulse(); send_bits(1,2); send_bits(0,2); send_bits(v,8); dIn();
    int ok=0; for(int i=0;i<600;i++){ pulse(); if(dR()){ok=1;break;} } pulse(); return ok; }
static int  c2_read_dr(int *out){ pulse(); send_bits(0,2); send_bits(0,2); dIn();
    int ok=0; for(int i=0;i<600;i++){ pulse(); if(dR()){ok=1;break;} }
    int d=0; if(ok){ for(int i=0;i<8;i++){ pulse(); d>>=1; if(dR()) d|=0x80; } pulse(); }
    *out=d; return ok; }

static int read_reg(unsigned c2addr,int *out){ c2_write_ar(c2addr); return c2_read_dr(out); }

// PI (halt) path
static int c2_connect(){                // C8051F41x datasheet §26.4: FPCTL enable = 0x02, 0x01 (NO 0x04)
    c2_reset();
    c2_write_ar(0x02);
    if(!c2_write_dr(0x02)) return 0;
    if(!c2_write_dr(0x01)) return 0;
    struct timespec t={0,25000000L}; nanosleep(&t,0);   // 25ms
    return 1;
}
static int poll_inbusy(){ for(int i=0;i<50000;i++){ if(!(c2_read_ar()&0x02)) return 1; } return 0; }
static int poll_outready(){ for(int i=0;i<50000;i++){ if(c2_read_ar()&0x01) return 1; } return 0; }
// C2ADD must already be FPDAT (0xB4): do ONE c2_write_ar(0xB4) before a command group,
// then only Data Write/Read + AddressRead-polls (AddressRead doesn't change C2ADD).
static int fp_wr(unsigned d){ if(!c2_write_dr(d)) return 0; return poll_inbusy(); }
static int fp_rd(int *out){ if(!poll_outready()) return 0; return c2_read_dr(out); }

// Block Read per Linux c2port __c2port_read_flash_data (verified): FPDAT once -> cmd 0x06 ->
// poll_in_busy -> status1 -> hi,lo,len (poll_in_busy each) -> status2 -> len data bytes.
// erase-safe: only 0x06 emitted; args gated on status1==0x0D; caller passes non-erase len.
static int g_dbg=0;
static int block_read(unsigned addr, unsigned char *buf, int len){
    c2_write_ar(0xB4);                             // target FPDAT once
    int w1=fp_wr(0x06);                            // Block Read cmd (+poll_in_busy)
    int st1=-1; int r1=fp_rd(&st1);                // status #1
    int wh=fp_wr((addr>>8)&0xFF), wl=fp_wr(addr&0xFF), wn=fp_wr(len&0xFF);
    int st2=-1; int r2=fp_rd(&st2);                // status #2 (after addr/len)
    if(g_dbg) printf("   [dbg] w1=%d st1=0x%02X(rd%d) wh=%d wl=%d wn=%d st2=0x%02X(rd%d)\n",
                     w1,st1&0xFF,r1,wh,wl,wn,st2&0xFF,r2);
    if(!w1) return -1;
    if(!r1) return -2;
    if(st1!=0x0D) return -3;                        // cmd not accepted
    if(!wh) return -4; if(!wl) return -5; if(!wn) return -6;
    if(!r2) return -7;
    for(int i=0;i<len;i++){ int b; if(!fp_rd(&b)) return -8; buf[i]=b; }
    return (st2==0x0D)?0:1;                          // 0 ok; 1 = data read but status2!=0x0D
}
static void dump(unsigned addr, const unsigned char*b, int n){
    for(int i=0;i<n;i+=16){ printf("  %04X:",addr+i);
        for(int j=0;j<16&&i+j<n;j++) printf(" %02X",b[i+j]);
        printf("  |");
        for(int j=0;j<16&&i+j<n;j++){ int c=b[i+j]; putchar((c>=0x20&&c<0x7e)?c:'.'); }
        printf("|\n"); }
}

// PI read commands (C2ADD must=FPDAT). READ-ONLY, target RAM/SFR (not flash → not lock-gated).
static int pi_get2(uint8_t cmd, int *a, int *b){        // Get Version 0x01 / Derivative 0x02 (2 reads)
    c2_write_ar(0xB4);
    if(!fp_wr(cmd)) return -1;
    if(!fp_rd(a))   return -2;
    return fp_rd(b)?0:-3;
}
static int pi_dread(uint8_t cmd, uint8_t addr, int *v){ // Direct 0x09 / Indirect 0x0B: read 1 byte @addr
    c2_write_ar(0xB4);
    if(!fp_wr(cmd)) return -1;
    int st=-1; if(!fp_rd(&st)) return -2;
    if(st!=0x0D) return -3;                              // command rejected -> unsupported
    if(!fp_wr(addr)) return -4;
    if(!fp_wr(0x01)) return -5;                          // length = 1
    return fp_rd(v)?0:-6;
}

static void go_realtime(){
    struct sched_param sp; sp.sched_priority=50;
    if(sched_setscheduler(0,SCHED_FIFO,&sp)!=0) fprintf(stderr,"(warn: SCHED_FIFO failed - run with sudo)\n");
    if(mlockall(MCL_CURRENT|MCL_FUTURE)!=0) fprintf(stderr,"(warn: mlockall failed)\n");
}

int main(int argc,char**argv){
    const char*mode = argc>1?argv[1]:"id";
    if(getenv("C2_TLOW"))  T_LOW =atoi(getenv("C2_TLOW"));
    if(getenv("C2_THIGH")) T_HIGH=atoi(getenv("C2_THIGH"));
    int fd=open("/dev/gpiomem",O_RDWR|O_SYNC);
    if(fd<0){ perror("open /dev/gpiomem"); return 1; }
    gpio=mmap(0,GPIO_LEN,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if(gpio==MAP_FAILED){ perror("mmap"); return 1; }
    close(fd);
    set_output(C2CK); pin_hi(C2CK);   // C2CK idle high (/RST deasserted)
    set_input(C2D);
    go_realtime();
    printf("C2 fast-C: C2CK=GPIO%d C2D=GPIO%d mode=%s\n",C2CK,C2D,mode);

    if(strcmp(mode,"halt")==0){
        T_LOW=300; T_HIGH=500;               // FAST: win the reset->halt race
        int ok=c2_connect();
        printf("c2_connect(FPCTL halt): %s\n", ok?"OK":"FAIL");
        T_LOW=2000; T_HIGH=4000;             // SLOW: reliable FPDAT (core halted, no race; F41x likes time)
        if(getenv("C2_TLOW"))  T_LOW =atoi(getenv("C2_TLOW"));    // allow override for tuning
        if(getenv("C2_THIGH")) T_HIGH=atoi(getenv("C2_THIGH"));
        int dev=-1,rev=-1; read_reg(0x00,&dev); read_reg(0x01,&rev);
        printf("halted DeviceID/Rev: 0x%02X / 0x%02X %s\n", dev&0xFF, rev&0xFF, dev==0x0C?"[0x0C OK]":"[not 0x0C]");
        printf("AR status: 0x%02X\n", c2_read_ar()&0xFF);
        c2_write_ar(0xB4);
        int ver=-1; int okv=fp_wr(0x01)&&fp_rd(&ver);
        printf("FPDAT GetVersion(0x01): %s0x%02X\n", okv?"":"(fail) ", ver&0xFF);
        unsigned addr = argc>2?(unsigned)strtol(argv[2],0,0):0x0000;
        int len = argc>3?atoi(argv[3]):64; if(len>256)len=256; if(len<1)len=64;
        unsigned char b1[256],b2[256];
        g_dbg=1;
        int r1=block_read(addr,b1,len);
        int r2=block_read(addr,b2,len);
        printf("Block Read @0x%04X len=%d : r1=%d r2=%d\n",addr,len,r1,r2);
        if(r1>=0){ printf("-- read #1 --\n"); dump(addr,b1,len); }
        if(r2>=0){ int match=(r1>=0)&&!memcmp(b1,b2,len);
            printf("-- read #2 %s --\n", match?"(IDENTICAL to #1 -> deterministic/real)":"(DIFFERS from #1 -> noise!)");
            dump(addr,b2,len); }
        if(r1>=0){ int z=1,f=1,same=1; for(int i=0;i<len;i++){ if(b1[i])z=0; if(b1[i]!=0xFF)f=0; if(b1[i]!=b1[0])same=0; }
            if(z) printf(">> all 00 -> READBACK LOCKED\n");
            else if(f) printf(">> all FF -> erased/blank region\n");
            else if(same) printf(">> all identical -> artifact\n");
            else printf(">> VARIED DATA (verify determinism above + looks like 8051 code)\n"); }
        else printf(">> block_read failed rc=%d (negative => guard/handshake; no erase possible)\n",r1);
        printf("(scope halted - power-cycle to recover)\n");
    } else if(strcmp(mode,"sweep")==0){
        // Map the readable range: low->high pages + Lock Byte region. Datasheet: lock covers
        // pages 0..n-1; pages above are C2-readable. Each addr gets a FRESH reset+halt (self-
        // recovering even if the prior read reset the device). AR-after = reset/contention indicator.
        unsigned addrs[]={0x0000,0x2000,0x4000,0x6000,0x7800,0x7C00,0x7DF0};
        printf("addr : conn st1 st2 ARaf  data[0..7]            verdict\n");
        for(unsigned k=0;k<sizeof(addrs)/sizeof(addrs[0]);k++){
            T_LOW=300; T_HIGH=500; int ok=c2_connect(); T_LOW=2000; T_HIGH=4000;
            c2_write_ar(0xB4);
            int w1=fp_wr(0x06); int st1=-1; fp_rd(&st1);
            fp_wr((addrs[k]>>8)&0xFF); fp_wr(addrs[k]&0xFF); fp_wr(0x10);
            int st2=-1; fp_rd(&st2);
            unsigned char b[16]; int got=0; for(;got<16;got++){ int v; if(!fp_rd(&v)) break; b[got]=v; }
            int arA=c2_read_ar();
            int varied=0,allff=1,all00=1; for(int i=0;i<got;i++){ if(i&&b[i]!=b[0])varied=1; if(b[i]!=0xFF)allff=0; if(b[i])all00=0; }
            const char*v = (w1==0||st1!=0x0D)?"cmd-rejected" : (got<16)?"read-fail" :
                all00?"all-00" : allff?"all-FF(blank)" : varied?"VARIED->REAL DATA?":"repeat(artifact)";
            printf("%04X :  %d   %02X  %02X  %02X  ", addrs[k], ok, st1&0xFF, st2&0xFF, arA&0xFF);
            for(int i=0;i<8&&i<got;i++) printf("%02X ", b[i]);
            for(int i=got;i<8;i++) printf(".. ");
            printf(" %s\n", v);
        }
        printf(">> VARIED at high addr = flash readable there (NOT fully locked); all cmd-rejected/fail = locked/blocked\n");
        printf("(scope halted/reset - power-cycle to recover)\n");
    } else if(strcmp(mode,"dbg")==0){
        T_LOW=300; T_HIGH=500;                          // FAST: win reset->halt race
        int ok=c2_connect();
        printf("c2_connect(FPCTL halt): %s\n", ok?"OK":"FAIL");
        T_LOW=2000; T_HIGH=4000;                        // SLOW: reliable FPDAT
        int dev=-1,rev=-1; read_reg(0x00,&dev); read_reg(0x01,&rev);
        printf("halted DeviceID/Rev: 0x%02X/0x%02X\n", dev&0xFF, rev&0xFF);
        int a=-1,b=-1;
        pi_get2(0x01,&a,&b); printf("GetVersion(0x01):    r1=0x%02X r2=0x%02X\n", a&0xFF,b&0xFF);
        a=b=-1; pi_get2(0x02,&a,&b); printf("GetDerivative(0x02): r1=0x%02X r2=0x%02X\n", a&0xFF,b&0xFF);
        struct { uint8_t a; const char*n; } D[]={{0xE0,"ACC "},{0x81,"SP  "},{0xD0,"PSW "},
            {0x80,"P0  "},{0x90,"P1  "},{0xA0,"P2  "},{0xB0,"P3  "},{0x87,"PCON"},{0x30,"R30 "},{0x00,"R00 "}};
        printf("-- Direct Read (0x09) SFR/direct-RAM --\n");
        for(unsigned i=0;i<sizeof(D)/sizeof(D[0]);i++){ int v=-1; int r=pi_dread(0x09,D[i].a,&v);
            if(r==0) printf("   %s @%02X = 0x%02X\n", D[i].n, D[i].a, v&0xFF);
            else if(r==-3){ printf("   %s @%02X : REJECTED (status!=0x0D) => 0x09 unsupported on F41x\n", D[i].n, D[i].a); break; }
            else printf("   %s @%02X : fail rc=%d\n", D[i].n, D[i].a, r); }
        uint8_t I[]={0x30,0x80,0xF0};
        printf("-- Indirect Read (0x0B) idata --\n");
        for(unsigned i=0;i<3;i++){ int v=-1; int r=pi_dread(0x0B,I[i],&v);
            if(r==0) printf("   @%02X = 0x%02X\n", I[i], v&0xFF);
            else if(r==-3){ printf("   @%02X : REJECTED => 0x0B unsupported on F41x\n", I[i]); break; }
            else printf("   @%02X : fail rc=%d\n", I[i], r); }
        printf("(scope halted - power-cycle to recover)\n");
    } else {
        for(int i=0;i<6;i++){ int dev=-1,rev=-1; c2_reset(); read_reg(0x00,&dev); read_reg(0x01,&rev);
            printf("  #%d DeviceID=0x%02X Rev=0x%02X %s\n", i, dev&0xFF, rev&0xFF,
                   dev==0x0C?"[0x0C = F41x OK!]":(dev==0xFF?"[0xFF no read]":"[?]"));
            struct timespec t={0,150000000L}; nanosleep(&t,0); }
    }
    set_output(C2CK); pin_hi(C2CK);   // leave /RST high so scope runs
    return 0;
}
