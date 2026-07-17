// -----------------------------------------------------------------------------
// C2 DIAGNOSTIC for Arduino UNO (ATmega328) -> C8051F41x  — READ-ONLY, erase-safe.
// x893 fast AVR primitives (direct PORTD/DDRD/PIND — reliable Address Read on AVR).
//
// Wiring (refined, empirical): Uno D5(C2CK/=RST)--[1.2k]--RFS ; D6(C2D)--[1.2k]--C2Dat ;
//   GND<->GND direct ; +3V3 NOT connected (scope self-powered). CH340: read serial dtr=False.
//
// SAFETY:
//  * auto-loop = NON-halt only: Data-Read Device ID/Rev (tests C2D read) + AR round-trip.
//    Does NOT halt the core -> scope keeps running.
//  * 'b' = HALT + guarded Block Read (0x06) — freezes scope until power-cycle. Erase-hardened:
//    args sent only after cmd status 0x0D; count=0x10 (never 0x08/0x07/0x03). No erase opcode here.
//  * 'r' = release C2 (/RST high, C2D input) so scope runs.
// C8051F41x: DEVICEID@0x00=0x0C, REVID@0x01, FPCTL@0x02, FPDAT@0xB4, Block Read=0x06.
// -----------------------------------------------------------------------------

#define C2CK_BIT  _BV(5)    // PortD5 = Arduino D5 (= /RST)
#define C2D_BIT   _BV(6)    // PortD6 = Arduino D6

#define FPDAT_ADDR     0xB4
#define C2ADD_OUTREADY 0x01
#define C2ADD_INBUSY   0x02
#define CMD_OK         0x0D

static inline void ckLow()  { PORTD &= ~C2CK_BIT; }
static inline void ckHigh() { PORTD |=  C2CK_BIT; }
static inline void dOn()    { DDRD  |=  C2D_BIT; }
static inline void dOff()   { PORTD &= ~C2D_BIT; DDRD &= ~C2D_BIT; }   // input, no pull-up (x893)
static inline void dHigh()  { PORTD |=  C2D_BIT; }
static inline void dLow()   { PORTD &= ~C2D_BIT; }
static inline uint8_t dRead(){ return (PIND & C2D_BIT) ? 1 : 0; }

uint8_t g_lo=3, g_hi=4;                        // adjustable clock (rule out RC/timing on C2D read)
static inline void pulse() {
  PORTD &= ~C2CK_BIT; for(uint8_t i=0;i<g_lo;i++) delayMicroseconds(1);
  PORTD |=  C2CK_BIT; for(uint8_t i=0;i<g_hi;i++) delayMicroseconds(1);
}

void c2Reset() {
  cli();
  DDRD |= C2CK_BIT;
  ckLow();  delayMicroseconds(20);
  ckHigh(); delayMicroseconds(2);
  sei();
}

void c2WriteAR(uint8_t addr) {
  cli();
  pulse();
  dHigh(); dOn(); pulse(); pulse();      // INS 11
  for (uint8_t i=0;i<8;i++){ if(addr&1) dHigh(); else dLow(); addr>>=1; pulse(); }
  dOff(); pulse();
  sei();
}
uint8_t c2ReadAR() {                       // returns PI STATUS byte (AN127 §1.2.1)
  cli();
  pulse();
  dLow(); dOn(); pulse();                  // INS bit0=0
  dHigh(); pulse();                        // INS bit1=1
  dOff();
  uint8_t data=0;
  for (uint8_t i=0;i<8;i++){ pulse(); data>>=1; if(dRead()) data|=0x80; }
  pulse();
  sei();
  return data;
}
bool c2WriteDR(uint8_t data) {
  cli();
  pulse();
  dHigh(); dOn(); pulse(); dLow(); pulse();   // INS 01
  pulse(); pulse();                            // LENGTH 00
  for (uint8_t i=0;i<8;i++){ if(data&1) dHigh(); else dLow(); data>>=1; pulse(); }
  dOff();
  uint8_t retry=200; do pulse(); while(--retry && !dRead());
  pulse();
  sei();
  return retry!=0;
}
bool c2ReadDR(uint8_t *out) {
  cli();
  pulse();
  dLow(); dOn(); pulse(); pulse();  // INS 00
  pulse(); pulse();                 // LENGTH 00
  dOff();
  uint8_t retry=0; do pulse(); while(--retry && !dRead());
  uint8_t data=0;
  if (retry){ for(uint8_t i=0;i<8;i++){ pulse(); data>>=1; if(dRead()) data|=0x80; } pulse(); }
  sei();
  *out = data;
  return retry!=0;
}

// InBusy/OutReady polling via Address Read (x893 — works on AVR)
bool pollInBusy()  { for(uint32_t t=0;t<50000;t++){ if(!(c2ReadAR()&C2ADD_INBUSY)) return true; } return false; }
bool pollOutReady(){ for(uint32_t t=0;t<50000;t++){ if( c2ReadAR()&C2ADD_OUTREADY) return true; } return false; }
bool fpWrite(uint8_t d){ c2WriteAR(FPDAT_ADDR); if(!c2WriteDR(d)) return false; return pollInBusy(); }
bool fpRead(uint8_t *out){ if(!pollOutReady()) return false; c2WriteAR(FPDAT_ADDR); return c2ReadDR(out); }
bool fpWriteRead(uint8_t d, uint8_t *out){ if(!fpWrite(d)) return false; return fpRead(out); }

bool c2Connect() {                          // FPCTL 0x02,0x04(halt),0x01
  c2Reset();
  c2WriteAR(0x02);
  if(!c2WriteDR(0x02)) return false;
  if(!c2WriteDR(0x04)) return false;
  delayMicroseconds(80);
  if(!c2WriteDR(0x01)) return false;
  delay(25);
  return true;
}

void printHex(uint8_t b){ if(b<0x10) Serial.print('0'); Serial.print(b,HEX); }

// ---- NON-HALT auto diagnostics (scope-safe) ----
void diagNoHalt() {
  c2Reset();
  uint8_t devId=0, rev=0;
  c2WriteAR(0x00); bool okId = c2ReadDR(&devId);   // Data Read -> tests C2D READ at 1.2k
  c2WriteAR(0x01); bool okRev= c2ReadDR(&rev);
  Serial.println(F("---- Uno C2 diag (NO halt, scope safe) ----"));
  Serial.print(F("DataRead DevID/Rev: 0x")); printHex(devId); Serial.print('/'); printHex(rev);
  Serial.println((okId && devId==0x0C) ? F("  [0x0C=F41x OK -> C2D READ WORKS]") : (devId==0xFF? F("  [0xFF -> C2D read still stuck]") : F("  [??]")));
  // AR round-trip: AN127 -> Address Read returns PI STATUS (idle ~0x00), not the written byte.
  c2WriteAR(0xA5); uint8_t s1=c2ReadAR();
  c2WriteAR(0x3C); uint8_t s2=c2ReadAR();
  Serial.print(F("AR status after WR 0xA5 / 0x3C: 0x")); printHex(s1); Serial.print(F(" / 0x")); printHex(s2);
  Serial.println((s1==s2) ? F("  [consistent (status, not addr)]") : F("  [inconsistent -> AR frame suspect]"));
  Serial.println();
}

// ---- GATED: HALT + guarded Block Read (erase-safe) ----
void blockReadGuarded() {
  Serial.println(F("==== Uno Block Read @0x0000 x16 (HALTS CORE — scope freezes) — guarded ===="));
  if(!c2Connect()){ Serial.println(F("Connect FAIL — abort")); return; }
  uint8_t st0=0;
  if(!fpWrite(0x06)){ Serial.println(F("cmd 0x06 write FAIL — abort (no args)")); return; }
  if(!fpRead(&st0)){  Serial.println(F("status read FAIL — abort (no args)")); return; }
  Serial.print(F("cmd 0x06 status=0x")); printHex(st0); Serial.println();
  if(st0 != CMD_OK){
    Serial.println(F(">> status != 0x0D: PI not confirmed. ABORT — no addr/count sent (erase-safe)."));
    Serial.println(F("(scope halted — power-cycle to recover)")); return;
  }
  uint8_t st1=0, buf[16];
  bool ok = fpWrite(0x00) && fpWrite(0x00) && fpWrite(0x10);   // hi, lo, count=0x10 (NOT 0x08)
  ok = ok && fpRead(&st1);
  if(ok) for(uint8_t i=0;i<16;i++){ if(!fpRead(&buf[i])){ ok=false; break; } }
  Serial.print(F("BlockRead st=")); printHex(st0); Serial.print('/'); printHex(st1); Serial.print(F(": "));
  if(ok){ for(uint8_t i=0;i<16;i++){printHex(buf[i]);Serial.print(' ');} } else Serial.print(F("<fail>"));
  Serial.println();
  if(ok){
    bool allz=true,allf=true,vary=false;
    for(uint8_t i=0;i<16;i++){ if(buf[i])allz=false; if(buf[i]!=0xFF)allf=false; if(buf[i]!=buf[0])vary=true; }
    if(allz) Serial.println(F(">> all 0x00 -> READBACK LOCKED"));
    else if(allf) Serial.println(F(">> all 0xFF -> erased/no-data"));
    else if(!vary) Serial.println(F(">> all identical (non-00/FF) -> likely ARTIFACT, not real flash"));
    else Serial.println(F(">> VARIED REAL DATA -> readback NOT locked (Path A OPEN!)"));
  }
  Serial.println(F("(scope halted — power-cycle to recover)"));
  Serial.println();
}

// Pin input-buffer self-test: drive each PORTD pin low/high and read PIND back.
// A healthy pin reads its own driven level (low->0, high->1). If D6 can't read its own
// LOW, its input buffer is damaged -> move C2D to a spare pin that PASSes.
// Only D6 is wired (to C2D); D7/D4/D3/D2 are tested unconnected (buffer check only).
// C2CK (D5) is NOT touched -> target not reset/clocked. Non-halt, safe.
void pinSelfTest() {
  Serial.println(F("---- PORTD input self-test (drive & read own level) ----"));
  const uint8_t bits[] = {6,7,4,3,2};
  const __FlashStringHelper* names[] = {F("D6 (C2D now)"),F("D7"),F("D4"),F("D3"),F("D2")};
  for(uint8_t i=0;i<5;i++){
    uint8_t m = _BV(bits[i]);
    DDRD |= m;  PORTD &= ~m; delayMicroseconds(50); uint8_t lo=(PIND&m)?1:0;
    PORTD |= m;              delayMicroseconds(50); uint8_t hi=(PIND&m)?1:0;
    DDRD &= ~m; PORTD &= ~m;                        // restore: input, no pull-up
    Serial.print(names[i]); Serial.print(F(": low->")); Serial.print(lo);
    Serial.print(F(" high->")); Serial.print(hi);
    Serial.println((lo==0&&hi==1)?F("   [input OK]"):F("   [INPUT FAULTY!]"));
  }
  dOff();
  Serial.println(F(">> if D6 FAULTY & a spare is OK -> move C2D wire there (я оновлю пін у скетчі)."));
  Serial.println(F(">> if D6 OK -> пін не винен; ціль не драйвить C2D low (не рівень/пін, а сигнал цілі)."));
  Serial.println();
}

void releaseC2() {
  c2Reset();
  DDRD |= C2CK_BIT; ckHigh();          // /RST high -> MCU runs
  dOff();                              // release C2D
  Serial.println(F(">> C2 released: /RST high, C2D input. Scope should run."));
}

void setup() {
  DDRD |= C2CK_BIT; PORTD |= C2CK_BIT;  // C2CK output, idle high
  dOff();
  Serial.begin(115200);
  delay(200);
  Serial.println(F("=== UNO C2 DIAG (C8051F41x) READ-ONLY. auto=Device ID+AR (no halt); 'b'=BlockRead(halt); 'r'=release ==="));
}

void loop() {
  if(Serial.available()){
    char c=Serial.read();
    if(c=='b'||c=='B') blockReadGuarded();
    else if(c=='r'||c=='R') releaseC2();
    else if(c=='s'||c=='S') diagNoHalt();
    else if(c=='p'||c=='P') pinSelfTest();
    else if(c=='1'){ g_lo=3;  g_hi=4;  Serial.println(F(">> clock=normal 3/4us")); }
    else if(c=='2'){ g_lo=20; g_hi=30; Serial.println(F(">> clock=slow 20/30us")); }
    else if(c=='3'){ g_lo=60; g_hi=90; Serial.println(F(">> clock=vslow 60/90us")); }
  }
  static unsigned long last=0;
  if(millis()-last>3000){ last=millis(); diagNoHalt(); }
}
