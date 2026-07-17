// -----------------------------------------------------------------------------
// C2 DIAGNOSTIC sketch for Arduino Due → C8051F41x  — READ-ONLY, erase-safe.
// Purpose: characterise the C2 command surface, and specifically FIX Address Read
// (INS 10) which the prior session saw returning shifted bytes (turnaround off-by-one).
//
// SAFETY:
//  * The automatic loop does ONLY non-halting ops (Data Read of Device ID/Rev + AR
//    round-trip of the C2 address register). These DO NOT halt the core → the scope
//    keeps running.  No erase/write opcode exists in this sketch.
//  * FPDAT read commands (Get Version 0x01, Get Derivative 0x02, Block Read 0x06) HALT
//    the core (freezes scope, needs power-cycle) → gated behind serial 'f', never auto.
//  * Serial 'r' = release C2 (deassert /RST, free C2D) so the scope runs normally.
//
// Wiring: C2Dat(C2D)→pin24, -RFS(C2CK,=/RST)→pin22, GND↔GND. Due 3.3V direct.
// C8051F41x: DEVICEID=0x0C @0x00, REVID @0x01, FPCTL @0x02, FPDAT @0xB4. Block Read=0x06.
// INS (LSB-first): DataRead=00 DataWrite=01 AddrRead=10 AddrWrite=11.
// -----------------------------------------------------------------------------

const int C2CK = 22;   // = /RST
const int C2D  = 24;

static inline void ckLow()  { digitalWrite(C2CK, LOW); }
static inline void ckHigh() { digitalWrite(C2CK, HIGH); }
static inline void dOn()    { pinMode(C2D, OUTPUT); }
static inline void dOff()   { pinMode(C2D, INPUT); }
static inline void dOffPU() { pinMode(C2D, INPUT_PULLUP); }
static inline void dHigh()  { digitalWrite(C2D, HIGH); }
static inline void dLow()   { digitalWrite(C2D, LOW); }
static inline uint8_t dRead(){ return digitalRead(C2D) ? 1 : 0; }

static inline void pulse() { ckLow(); delayMicroseconds(1); ckHigh(); delayMicroseconds(2); }

#define C2ADD_OUTREADY 0x01
#define C2ADD_INBUSY   0x02
#define CMD_OK         0x0D

void c2Reset() { ckLow(); delayMicroseconds(25); ckHigh(); delayMicroseconds(3); }

// Address Write (INS 11b)
void c2WriteAR(uint8_t addr) {
  pulse();                               // START
  dHigh(); dOn(); pulse(); pulse();      // INS 11
  for (uint8_t i=0;i<8;i++){ if(addr&1) dHigh(); else dLow(); addr>>=1; pulse(); }
  dOff(); pulse();                       // STOP
}

// Address Read (INS 10b), parametrised turnaround.
//   turns = number of discarded turnaround clocks between INS and data (0,1,2).
//   pu    = use INPUT_PULLUP on the released line (defines float level).
uint8_t c2ReadAR_v(uint8_t turns, bool pu) {
  pulse();                               // START
  dLow(); dOn(); pulse();                // INS bit0=0
  dHigh(); pulse();                      // INS bit1=1
  if (pu) dOffPU(); else dOff();         // turnaround → input
  for (uint8_t t=0;t<turns;t++) pulse(); // discarded turnaround clock(s)
  uint8_t data=0;
  for (uint8_t i=0;i<8;i++){ pulse(); data>>=1; if(dRead()) data|=0x80; }
  pulse();                               // STOP
  dOff();
  return data;
}

// Data Write (INS 01b) + WAIT
bool c2WriteDR(uint8_t data) {
  pulse();                               // START
  dHigh(); dOn(); pulse(); dLow(); pulse();   // INS 01
  pulse(); pulse();                      // LENGTH 00
  for (uint8_t i=0;i<8;i++){ if(data&1) dHigh(); else dLow(); data>>=1; pulse(); }
  dOff();                                // WAIT
  uint8_t retry=200; do pulse(); while(--retry && !dRead());
  pulse();                               // STOP
  return retry != 0;
}

// Data Read (INS 00b) + WAIT (self-synchronising — this is the reliable primitive)
bool c2ReadDR(uint8_t *out) {
  pulse();                               // START
  dLow(); dOn(); pulse(); pulse();       // INS 00
  pulse(); pulse();                      // LENGTH 00
  dOff();                                // WAIT
  uint8_t retry=0; do pulse(); while(--retry && !dRead());
  uint8_t data=0;
  if (retry){ for(uint8_t i=0;i<8;i++){ pulse(); data>>=1; if(dRead()) data|=0x80; } pulse(); }
  *out = data;
  return retry != 0;
}

void printHex(uint8_t b){ if(b<0x10) Serial.print('0'); Serial.print(b,HEX); }

// ---- NON-HALTING diagnostics (auto loop) ----------------------------------
void diagReadState() {
  c2Reset();
  uint8_t devId=0, rev=0;
  c2WriteAR(0x00); bool okId = c2ReadDR(&devId);
  c2WriteAR(0x01); bool okRev= c2ReadDR(&rev);

  Serial.println(F("---- C2 diag (NO halt, scope safe) ----"));
  Serial.print(F("DataRead  DevID/Rev: 0x")); printHex(devId); Serial.print('/'); printHex(rev);
  Serial.println((okId && devId==0x0C) ? F("  [0x0C=F41x OK]") : F("  [??]"));

  // Address-Read round-trip sweep. Write a known value to C2ADD, read it back.
  // A correct AR returns the same byte. Two probes (0xA5,0x3C) expose shifts/inversions.
  const uint8_t probes[2] = {0xA5, 0x3C};
  for (uint8_t p=0;p<2;p++){
    Serial.print(F("  AR probe 0x")); printHex(probes[p]); Serial.print(F(" -> "));
    // turns x pullup grid
    struct { uint8_t t; bool pu; const char* name; } V[] = {
      {0,false,"t0"},{0,true,"t0pu"},{1,false,"t1"},{1,true,"t1pu"},{2,true,"t2pu"}
    };
    for (uint8_t v=0; v<5; v++){
      c2WriteAR(probes[p]);
      uint8_t r = c2ReadAR_v(V[v].t, V[v].pu);
      Serial.print(V[v].name); Serial.print('='); printHex(r);
      if (r==probes[p]) Serial.print(F("(OK)"));
      Serial.print(' ');
    }
    Serial.println();
  }
  Serial.println();
}

// ---- HALTING FPDAT tests (gated on 'f') -----------------------------------
// Uses ONLY read commands: Get Version 0x01, Get Derivative 0x02, Block Read 0x06.
// NO erase (0x03) / block-write (0x07) / page-erase (0x08) — none exist in this file.
bool c2Connect() {                       // FPCTL 0x02,0x04(halt),0x01
  c2Reset();
  c2WriteAR(0x02);
  if(!c2WriteDR(0x02)) return false;
  if(!c2WriteDR(0x04)) return false;
  delayMicroseconds(80);
  if(!c2WriteDR(0x01)) return false;
  delay(25);
  return true;
}

// AR-free FPDAT: rely purely on Data Write/Read WAIT handshakes (no Address-Read polling).
bool fpWr(uint8_t d){ c2WriteAR(0xB4); return c2WriteDR(d); }
bool fpRd(uint8_t *o){ c2WriteAR(0xB4); return c2ReadDR(o); }

// SAFEST FPDAT probe: Get Version (0x01) + Get Derivative (0x02).
// Single-byte commands, NO address/count args → NO byte in the stream can ever be an
// erase/write command code even under total desync. Proves the AR-free PI handshake.
void fpdatVersion() {
  Serial.println(F("==== FPDAT Get Version/Derivative (HALTS CORE — scope freezes) ===="));
  bool conn = c2Connect();
  Serial.print(F("Connect(FPCTL halt): ")); Serial.println(conn?F("OK"):F("FAIL"));
  if(!conn){ Serial.println(F("(no PI handshake — nothing sent)")); return; }
  uint8_t ver=0xEE, der=0xEE;
  bool okV = fpWr(0x01) && fpRd(&ver);
  Serial.print(F("GetVersion(0x01):    ")); if(okV){Serial.print(F("0x"));printHex(ver);} else Serial.print(F("<fail>")); Serial.println();
  bool okD = fpWr(0x02) && fpRd(&der);
  Serial.print(F("GetDerivative(0x02): ")); if(okD){Serial.print(F("0x"));printHex(der);} else Serial.print(F("<fail>")); Serial.println();
  Serial.println(okV||okD ? F(">> PI handshake WORKS via AR-free path") : F(">> PI handshake did NOT respond"));
  Serial.println(F("(scope halted — power-cycle to recover)"));
  Serial.println();
}

// GUARDED Block Read (0x06) — READ ONLY, erase-hardened:
//  * Aborts BEFORE sending any argument byte unless cmd 0x06 returns status 0x0D
//    (i.e. FPDAT confirmed it is in 'expecting address' state, so args can't be
//     misread as commands).
//  * count = 0x10 (never 0x08=PageErase / 0x07=BlockWrite / 0x03=DeviceErase).
//  * No erase/write opcode is emitted anywhere in this function.
void fpdatBlockRead() {
  Serial.println(F("==== Block Read @0x0000 (HALTS CORE) — guarded, erase-safe ===="));
  if(!c2Connect()){ Serial.println(F("Connect FAIL — abort")); return; }
  uint8_t st0=0;
  if(!fpWr(0x06)){ Serial.println(F("cmd 0x06 write FAIL — abort (no args sent)")); return; }
  if(!fpRd(&st0)){ Serial.println(F("status read FAIL — abort (no args sent)")); return; }
  Serial.print(F("cmd 0x06 status=0x")); printHex(st0); Serial.println();
  if(st0 != CMD_OK){
    Serial.println(F(">> status != 0x0D: PI NOT confirmed. ABORT — no addr/count sent (erase-safe)."));
    Serial.println(F("(scope halted — power-cycle to recover)"));
    return;
  }
  uint8_t st1=0, buf[16];
  bool ok = fpWr(0x00) && fpWr(0x00) && fpWr(0x10);   // addr hi=00, lo=00, count=0x10
  ok = ok && fpRd(&st1);
  if(ok) for(uint8_t i=0;i<16;i++){ if(!fpRd(&buf[i])){ ok=false; break; } }
  Serial.print(F("BlockRead @0000 st=")); printHex(st0); Serial.print('/'); printHex(st1); Serial.print(F(": "));
  if(ok){ for(uint8_t i=0;i<16;i++){printHex(buf[i]);Serial.print(' ');} } else Serial.print(F("<fail>"));
  Serial.println();
  if(ok){
    bool allz=true,allf=true; for(uint8_t i=0;i<16;i++){if(buf[i])allz=false; if(buf[i]!=0xFF)allf=false;}
    if(allz) Serial.println(F(">> all 0x00 -> READBACK LOCKED"));
    else if(allf) Serial.println(F(">> all 0xFF -> erased/no-data"));
    else Serial.println(F(">> REAL FLASH DATA -> readback NOT locked (Path A open)"));
  }
  Serial.println(F("(scope halted — power-cycle to recover)"));
  Serial.println();
}

// AR-free + FIXED-DELAY FPDAT: fixed µs delays substitute for InBusy/OutReady polls.
// Discriminator: if data bytes now VARY -> reads were racing OutReady (delays fix it).
// If still identical -> the byte pointer does not advance without the AR OutReady poll
// (hardware-blocked). Still erase-safe: only 0x06 + {0x00,0x00,0x10} emitted, guarded on 0x0D.
bool fpWrDly(uint8_t d){ c2WriteAR(0xB4); bool ok=c2WriteDR(d); delayMicroseconds(100); return ok; }
bool fpRdDly(uint8_t *o){ delayMicroseconds(500); c2WriteAR(0xB4); return c2ReadDR(o); }

void fpdatBlockReadDelayed() {
  Serial.println(F("==== Block Read @0x0000 (HALTS) — AR-free + fixed delays (wr100/rd500us) ===="));
  if(!c2Connect()){ Serial.println(F("Connect FAIL — abort")); return; }
  uint8_t st0=0;
  if(!fpWrDly(0x06)){ Serial.println(F("cmd 0x06 write FAIL — abort")); return; }
  if(!fpRdDly(&st0)){ Serial.println(F("status read FAIL — abort")); return; }
  Serial.print(F("cmd 0x06 status=0x")); printHex(st0); Serial.println();
  if(st0 != CMD_OK){
    Serial.println(F(">> status != 0x0D: ABORT — no addr/count sent (erase-safe).")); return;
  }
  uint8_t st1=0, buf[16];
  bool ok = fpWrDly(0x00) && fpWrDly(0x00) && fpWrDly(0x10);   // hi, lo, count=0x10
  ok = ok && fpRdDly(&st1);
  if(ok) for(uint8_t i=0;i<16;i++){ if(!fpRdDly(&buf[i])){ ok=false; break; } }
  Serial.print(F("st=")); printHex(st0); Serial.print('/'); printHex(st1); Serial.print(F(": "));
  if(ok){ for(uint8_t i=0;i<16;i++){printHex(buf[i]);Serial.print(' ');} } else Serial.print(F("<fail>"));
  Serial.println();
  // NO auto-verdict — identical bytes = artifact; only varied non-trivial bytes = real flash.
  bool varied=false; for(uint8_t i=1;i<16;i++) if(buf[i]!=buf[0]) varied=true;
  Serial.println(varied ? F(">> bytes VARY — candidate real data (inspect)") : F(">> bytes IDENTICAL — artifact, pointer not advancing (AR poll needed)"));
  Serial.println(F("(scope halted — power-cycle to recover)"));
  Serial.println();
}

// ---- Direct/Indirect Read/Write (0x09/0x0A/0x0B/0x0C) per AN127 §3.5/3.6 + 4.1.5/4.1.6 ----
// AR-free (fixed-delay) + guarded. RAM-ONLY targets (0x30/0x40) — never flash, never an SFR.
// Emitted bytes are only {0x09,0x0A,0x0B,0x0C,0x30,0x40,0x01,data}; none is an erase/write-flash
// opcode (0x03/0x07/0x08), so no desync can erase. Args sent only after status 0x0D.
bool piRead(uint8_t cmd, uint8_t addr, uint8_t *out, uint8_t *st) {
  if(!fpWrDly(cmd))    return false;   // Direct/Indirect Read command
  if(!fpRdDly(st))     return false;   // command status (expect 0x0D)
  if(*st != CMD_OK)    return false;   // GUARD: no args unless accepted
  if(!fpWrDly(addr))   return false;   // target address
  if(!fpWrDly(0x01))   return false;   // length = 1
  return fpRdDly(out);                  // the data byte
}
bool piWrite(uint8_t cmd, uint8_t addr, uint8_t data, uint8_t *st) {
  if(!fpWrDly(cmd))    return false;   // Direct/Indirect Write command
  if(!fpRdDly(st))     return false;   // command status (expect 0x0D)
  if(*st != CMD_OK)    return false;   // GUARD: no addr/data unless accepted
  if(!fpWrDly(addr))   return false;   // target address (RAM only)
  if(!fpWrDly(0x01))   return false;   // length = 1
  return fpWrDly(data);                 // the value (RAM write)
}

void directIndirectTest() {
  Serial.println(F("==== Direct/Indirect R/W (0x09/0x0A/0x0B/0x0C) — HALTS CORE, RAM-only, erase-safe ===="));
  if(!c2Connect()){ Serial.println(F("Connect FAIL — abort")); return; }
  uint8_t st=0, v=0;
  bool ok;
  ok = piRead(0x09, 0x30, &v, &st);
  Serial.print(F("DirectRead   (0x09) @0x30 before: ")); if(ok){Serial.print(F("0x"));printHex(v);}else Serial.print(F("<fail>")); Serial.print(F("  st=0x")); printHex(st); Serial.println();
  ok = piWrite(0x0A, 0x30, 0xA5, &st);
  Serial.print(F("DirectWrite  (0x0A) @0x30<=A5:    ")); Serial.print(ok?F("cmd-accepted"):F("<fail/not-accepted>")); Serial.print(F("  st=0x")); printHex(st); Serial.println();
  ok = piRead(0x09, 0x30, &v, &st);
  Serial.print(F("DirectRead   (0x09) @0x30 after:  ")); if(ok){Serial.print(F("0x"));printHex(v);}else Serial.print(F("<fail>")); Serial.println(v==0xA5?F("  [==A5 -> WRITE+READ VERIFIED]"):F("  [!=A5]"));
  ok = piRead(0x0B, 0x40, &v, &st);
  Serial.print(F("IndirectRead (0x0B) @0x40 before: ")); if(ok){Serial.print(F("0x"));printHex(v);}else Serial.print(F("<fail>")); Serial.print(F("  st=0x")); printHex(st); Serial.println();
  ok = piWrite(0x0C, 0x40, 0x5A, &st);
  Serial.print(F("IndirectWrite(0x0C) @0x40<=5A:    ")); Serial.print(ok?F("cmd-accepted"):F("<fail/not-accepted>")); Serial.print(F("  st=0x")); printHex(st); Serial.println();
  ok = piRead(0x0B, 0x40, &v, &st);
  Serial.print(F("IndirectRead (0x0B) @0x40 after:  ")); if(ok){Serial.print(F("0x"));printHex(v);}else Serial.print(F("<fail>")); Serial.println(v==0x5A?F("  [==5A -> WRITE+READ VERIFIED]"):F("  [!=5A]"));
  Serial.println(F(">> if 'after' reads match written or vary meaningfully -> data path works;"));
  Serial.println(F(">> if identical/stale across ops -> same OutReady(AR) blocker as Block Read."));
  Serial.println(F("(scope halted — power-cycle to recover; only RAM 0x30/0x40 touched, NO flash)"));
  Serial.println();
}

// Command-acceptance compare: reconnect (fresh PI) + send one command byte + read its status,
// for a curated SAFE set (valid reads + UNDEFINED codes). NEVER sends 0x03/0x07/0x08 and never
// sends command arguments/arming bytes → no write/erase can complete. Discriminates
// "accepted (0x0D)" vs "rejected (0x03)" per command, ruling out stale-latch artifact.
void cmdStatusCompare() {
  Serial.println(F("==== Command-acceptance compare (HALTS) — reconnect+cmd+status per probe, NO args, erase-safe ===="));
  const uint8_t cmds[] = {0x01,0x02,0x06,0x05,0x09,0x0A,0x0B,0x0C,0xFF};
  for(uint8_t i=0;i<9;i++){
    if(!c2Connect()){ Serial.println(F("Connect FAIL — abort")); return; }
    uint8_t st=0xEE;
    fpWrDly(cmds[i]); fpRdDly(&st);
    Serial.print(F("cmd 0x")); printHex(cmds[i]); Serial.print(F(" -> status 0x")); printHex(st);
    if(st==CMD_OK)      Serial.println(F("   [0x0D = ACCEPTED]"));
    else if(st==0x03)   Serial.println(F("   [0x03 = rejected]"));
    else                Serial.println(F("   [other]"));
  }
  Serial.println(F("(scope halted — power-cycle to recover; no flash touched)"));
  Serial.println();
}

void releaseC2() {
  c2Reset();                 // one reset pulse clears any FPCTL halt
  ckHigh();                  // /RST deasserted → MCU runs
  dOff();                    // release data line
  Serial.println(F(">> C2 released: /RST high, C2D input. Scope should run."));
}

void setup() {
  pinMode(C2CK, OUTPUT);
  pinMode(C2D, INPUT);
  ckHigh();
  Serial.begin(115200);
  while(!Serial && millis()<3000){}
  delay(200);
  Serial.println(F("=== Due C2 DIAG (C8051F41x). auto=safe reads; 'f'=GetVer 'b'=BlockRd 'd'=BlockRd+dly 'x'=Direct/Indirect(halt); 'r'=release ==="));
}

void loop() {
  if(Serial.available()){
    char c=Serial.read();
    if(c=='f'||c=='F') fpdatVersion();       // safest FPDAT probe (halts core)
    else if(c=='b'||c=='B') fpdatBlockRead(); // guarded Block Read (halts core)
    else if(c=='d'||c=='D') fpdatBlockReadDelayed(); // AR-free + fixed delays (halts core)
    else if(c=='x'||c=='X') directIndirectTest();    // Direct/Indirect R/W 0x09-0x0C (halts core)
    else if(c=='c'||c=='C') cmdStatusCompare();      // per-command status compare (halts core)
    else if(c=='r'||c=='R') releaseC2();
    else if(c=='s'||c=='S') diagReadState();
  }
  static unsigned long last=0;
  if(millis()-last>3000){ last=millis(); diagReadState(); }
}
