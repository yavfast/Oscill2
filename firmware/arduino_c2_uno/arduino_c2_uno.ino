// -----------------------------------------------------------------------------
// C2 reader for Arduino UNO (ATmega328) → C8051F41x
// Використовує ПЕРЕВІРЕНІ швидкі AVR-примітиви з x893/C2.Flash (прямий PORTD/DDRD/PIND —
// на AVR це працює надійно, на відміну від Due) + простий авто-вивід стану.
//
// ⚠️ Uno = 5В, а C2D=P2.0 НЕ 5V-толерантний (max ~3.6В). Тому C2 лінії — ЧЕРЕЗ РЕЗИСТОРИ:
//   Uno D5 (C2CK) --[1.2к]-- плата -RFS (C2CK/=RST)   ← 1.2к, НЕ 3.3к (емпірично: 3.3к клок не доходив)
//   Uno D6 (C2D)  --[1.2к]-- плата C2Dat (C2D=P2.0)   ← так само 1.2к (C2D-read ще не підтверджено)
//   Uno GND ------------------ плата GND   (напряму, без резистора)
//   Осцилограф на власному живленні; +3V3 між платами НЕ зʼєднувати.
//   Резистор обмежує струм у P2.0 через ESD-діоди чипа (~1.2мА при 5В/1.2к — безпечно).
//   Альтернатива для чистих фронтів (особливо двонапр. C2D): level shifter BSS138.
//
// C8051F41x: DEVICEID=0x0C, FPCTL@0x02 (enable 0x02,0x04,0x01), FPDAT@0xB4, Block Read=0x06.
// -----------------------------------------------------------------------------

#define C2CK_BIT  _BV(5)    // PortD5 = Arduino D5
#define C2D_BIT   _BV(6)    // PortD6 = Arduino D6

#define FPDAT_ADDR   0xB4   // C8051F41x
#define C2ADD_OUTREADY 0x01
#define C2ADD_INBUSY   0x02

static inline void ckLow()  { PORTD &= ~C2CK_BIT; }
static inline void ckHigh() { PORTD |=  C2CK_BIT; }
static inline void dOn()    { DDRD  |=  C2D_BIT; }                     // driver on (output)
static inline void dOff()   { PORTD &= ~C2D_BIT; DDRD &= ~C2D_BIT; }   // input, no pull-up (x893)
static inline void dHigh()  { PORTD |=  C2D_BIT; }
static inline void dLow()   { PORTD &= ~C2D_BIT; }
static inline uint8_t dRead(){ return (PIND & C2D_BIT) ? 1 : 0; }

// СПОВІЛЬНЕНИЙ такт: даємо RC-колу (1.2к + ємність /RST) час зарядитись. LOW ≤5мкс (AN127).
static inline void pulse() {
  PORTD &= ~C2CK_BIT;
  delayMicroseconds(3);        // low ~3мкс
  PORTD |=  C2CK_BIT;
  delayMicroseconds(4);        // high settle + data-valid для F41x
}

void c2Reset() {
  cli();
  DDRD |= C2CK_BIT;                 // C2CK driver on
  ckLow();  delayMicroseconds(20);  // /RST low > 20мкс
  ckHigh(); delayMicroseconds(2);
  sei();
}

// Address Write (INS 11b) — x893 C2_WriteAR
void c2WriteAR(uint8_t addr) {
  cli();
  pulse();                          // START
  dHigh(); dOn(); pulse(); pulse(); // INS 11
  for (uint8_t i=0;i<8;i++){ if(addr&1) dHigh(); else dLow(); addr>>=1; pulse(); }
  dOff(); pulse();                  // STOP
  sei();
}

// Address Read (INS 10b) — x893 C2_ReadAR
uint8_t c2ReadAR() {
  cli();
  pulse();                          // START
  dLow(); dOn(); pulse();           // INS bit0=0
  dHigh(); pulse();                 // INS bit1=1
  dOff();                           // turnaround
  uint8_t data=0;
  for (uint8_t i=0;i<8;i++){ pulse(); data>>=1; if(dRead()) data|=0x80; }
  pulse();                          // STOP
  sei();
  return data;
}

// Data Write (INS 01b) + WAIT — x893 C2_WriteDR
bool c2WriteDR(uint8_t data) {
  cli();
  pulse();                          // START
  dHigh(); dOn(); pulse(); dLow(); pulse();   // INS 01
  pulse(); pulse();                 // LENGTH 00
  for (uint8_t i=0;i<8;i++){ if(data&1) dHigh(); else dLow(); data>>=1; pulse(); }
  dOff();                           // WAIT
  uint8_t retry=200; do pulse(); while(--retry && !dRead());
  pulse();                          // STOP
  sei();
  return retry!=0;
}

// Data Read (INS 00b) + WAIT — x893 C2_ReadDR
bool c2ReadDR(uint8_t *out) {
  cli();
  pulse();                          // START
  dLow(); dOn(); pulse(); pulse();  // INS 00
  pulse(); pulse();                 // LENGTH 00
  dOff();                           // WAIT
  uint8_t retry=0; do pulse(); while(--retry && !dRead());  // 0→255
  uint8_t data=0;
  if (retry){ for(uint8_t i=0;i<8;i++){ pulse(); data>>=1; if(dRead()) data|=0x80; } pulse(); }
  sei();
  *out = data;
  return retry!=0;
}

bool pollInBusy()  { for(uint32_t t=0;t<50000;t++){ if(!(c2ReadAR()&C2ADD_INBUSY)) return true; delayMicroseconds(1);} return false; }
bool pollOutReady(){ for(uint32_t t=0;t<50000;t++){ if( c2ReadAR()&C2ADD_OUTREADY) return true; delayMicroseconds(1);} return false; }

bool fpWrite(uint8_t d){ c2WriteAR(FPDAT_ADDR); if(!c2WriteDR(d)) return false; return pollInBusy(); }
bool fpRead(uint8_t *out){ if(!pollOutReady()) return false; c2WriteAR(FPDAT_ADDR); return c2ReadDR(out); }
bool fpWriteRead(uint8_t d, uint8_t *out){ if(!fpWrite(d)) return false; return fpRead(out); }

// Reset + enable/halt PI (FPCTL 0x02,0x04,0x01) — x893 C2_Connect_Target
bool c2Connect() {
  c2Reset();
  c2WriteAR(0x02);
  if(!c2WriteDR(0x02)) return false;
  if(!c2WriteDR(0x04)) return false;   // halt core
  delayMicroseconds(80);
  if(!c2WriteDR(0x01)) return false;
  delay(25);
  return true;
}

// Flash Block Read (x893 C2_Read_Memory) : cmd 0x06 → status 0x0D → hi → lo → count → 0x0D → bytes
bool flashRead(uint16_t addr, uint8_t count, uint8_t *buf, uint8_t *st) {
  if(!fpWriteRead(0x06,&st[0])) return false;
  if(!fpWrite((addr>>8)&0xFF)) return false;
  if(!fpWrite(addr&0xFF))      return false;
  if(!fpWrite(count))          return false;
  if(!fpRead(&st[1]))          return false;
  for(uint8_t i=0;i<count;i++){ if(!fpRead(&buf[i])) return false; }
  return true;
}

void printHex(uint8_t b){ if(b<0x10) Serial.print('0'); Serial.print(b,HEX); }

void readState() {
  bool conn = c2Connect();
  uint8_t devId=0, rev=0;
  c2WriteAR(0x00); bool okId=c2ReadDR(&devId);
  c2WriteAR(0x01); bool okRev=c2ReadDR(&rev);
  c2WriteAR(0xA5); uint8_t rt=c2ReadAR();

  Serial.println(F("---- C2 state ----"));
  Serial.print(F("Connect: ")); Serial.println(conn?F("OK"):F("FAIL"));
  Serial.print(F("Device ID / Rev: 0x")); printHex(devId); Serial.print(F(" / 0x")); printHex(rev); Serial.println();
  Serial.print(F("AR round-trip A5: 0x")); printHex(rt); Serial.println(rt==0xA5?F("  [OK]"):F("  [FAIL]"));

  uint8_t buf[16], st[2]={0,0};
  bool okBR = flashRead(0x0000,16,buf,st);
  Serial.print(F("Flash @0000 (st ")); printHex(st[0]); Serial.print('/'); printHex(st[1]); Serial.print(F("): "));
  if(okBR){ for(uint8_t i=0;i<16;i++){printHex(buf[i]);Serial.print(' ');} } else Serial.print(F("<fail>"));
  Serial.println();
  if(okBR){
    bool allz=true,allf=true; for(uint8_t i=0;i<16;i++){if(buf[i])allz=false; if(buf[i]!=0xFF)allf=false;}
    if(allz) Serial.println(F(">> усе 0x00 → READBACK ЗАБЛОКОВАНО."));
    else if(allf) Serial.println(F(">> усе 0xFF → стерто/помилка."));
    else Serial.println(F(">> РЕАЛЬНІ ДАНІ flash → readback НЕ заблоковано! (Path A відкрито)"));
  }
  Serial.println();
}

void setup() {
  DDRD |= C2CK_BIT; PORTD |= C2CK_BIT;   // C2CK output, idle high
  dOff();                                // C2D input
  Serial.begin(115200);
  delay(200);
  Serial.println(F("=== UNO C2 reader (C8051F41x), x893 AVR primitives ==="));
}

void loop() {
  if(Serial.available()){ char c=Serial.read(); if(c=='s'||c=='S') readState(); }
  static unsigned long last=0;
  if(millis()-last>3000){ last=millis(); readState(); }
}
