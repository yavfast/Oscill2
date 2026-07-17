// -----------------------------------------------------------------------------
// C2 (Silicon Labs 2-Wire) reader for Arduino Due  →  C8051F41x
// Порт перевіреної реалізації x893/C2.Flash (AVR) на Due з ШВИДКИМ доступом до PIO:
//   такти + перемикання напряму C2D через регістри SAM3X (детерміновано, як DDR/PORT у x893);
//   digitalWrite/pinMode повільні/джитерні → ламали Address Read (turnaround без WAIT). Це фікс.
//
// Розводка: C2Dat(C2D)→пін24, -RFS(C2CK,=/RST)→пін22, GND↔GND. Due 3.3В, без level shifter.
//   Осцилограф на власному живленні; +3V3 між платами НЕ зʼєднувати.
//
// C8051F41x (datasheet §26): DEVICEID=0x0C, FPCTL@0x02, FPDAT@0xB4.
//   PI init (AN127 §3): reset → FPCTL: 0x02, 0x04(halt core), 0x01 → wait.
//   Flash Block Read = FPDAT cmd 0x06.  INS LSB-first: DR=00 DW=01 AR_rd=10 AR_wr=11.
// -----------------------------------------------------------------------------

const int C2CK = 22;   // = /RST
const int C2D  = 24;

static Pio* ckP; static uint32_t ckM;
static Pio* dP;  static uint32_t dM;

// --- pinMode/digitalWrite (єдине, що комунікує на цьому Due; register-PIO не працює).
//     Надійно для Data Read (Device ID). Address Read (без WAIT) страждає від повільного turnaround. ---
static inline void ckLow()  { digitalWrite(C2CK, LOW); }
static inline void ckHigh() { digitalWrite(C2CK, HIGH); }
static inline void dOn()    { pinMode(C2D, OUTPUT); }
static inline void dOff()   { pinMode(C2D, INPUT); }
static inline void dHigh()  { digitalWrite(C2D, HIGH); }
static inline void dLow()   { digitalWrite(C2D, LOW); }
static inline uint8_t dRead(){ return digitalRead(C2D) ? 1 : 0; }

// Pulse_C2CLK: КОРОТКИЙ LOW (лише тривалість digitalWrite ~1мкс, в межах 80нс-5мкс) → high;
// затримка у high-фазі перед семплом. Експеримент: мінімізувати LOW.
static inline void pulse() { ckLow(); delayMicroseconds(1); ckHigh(); delayMicroseconds(2); }

#define C2ADD_OUTREADY 0x01
#define C2ADD_INBUSY   0x02
#define CMD_OK         0x0D

void c2Reset() { ckLow(); delayMicroseconds(25); ckHigh(); delayMicroseconds(3); }

// Address Write (INS 11b): x893 C2_WriteAR
void c2WriteAR(uint8_t addr) {
  pulse();                       // START
  dHigh(); dOn(); pulse(); pulse();   // INS 11
  for (uint8_t i=0;i<8;i++){ if(addr&1) dHigh(); else dLow(); addr>>=1; pulse(); }
  dOff(); pulse();               // STOP
}

// Address Read (INS 10b): x893 C2_ReadAR
uint8_t c2ReadAR() {
  pulse();                       // START
  dLow(); dOn(); pulse();        // INS bit0=0
  dHigh(); pulse();              // INS bit1=1
  dOff();                        // turnaround → input
  uint8_t data=0;
  for (uint8_t i=0;i<8;i++){ pulse(); data>>=1; if(dRead()) data|=0x80; }
  pulse();                       // STOP
  return data;
}

// Data Write (INS 01b) + WAIT: x893 C2_WriteDR
bool c2WriteDR(uint8_t data) {
  pulse();                       // START
  dHigh(); dOn(); pulse(); dLow(); pulse();   // INS 01
  pulse(); pulse();              // LENGTH 00
  for (uint8_t i=0;i<8;i++){ if(data&1) dHigh(); else dLow(); data>>=1; pulse(); }
  dOff();                        // WAIT
  uint8_t retry=200; do pulse(); while(--retry && !dRead());
  pulse();                       // STOP
  return retry != 0;
}

// Data Read (INS 00b) + WAIT: x893 C2_ReadDR
bool c2ReadDR(uint8_t *out) {
  pulse();                       // START
  dLow(); dOn(); pulse(); pulse();   // INS 00
  pulse(); pulse();              // LENGTH 00
  dOff();                        // WAIT
  uint8_t retry=0; do pulse(); while(--retry && !dRead());  // retry 0→255 (як x893)
  uint8_t data=0;
  if (retry){ for(uint8_t i=0;i<8;i++){ pulse(); data>>=1; if(dRead()) data|=0x80; } pulse(); }
  *out = data;
  return retry != 0;
}

// Poll InBusy=0 / OutReady=1 через Address Read (x893 Poll_InBusy/OutReady)
bool pollInBusy()  { for(uint32_t t=0;t<50000;t++){ if(!(c2ReadAR()&C2ADD_INBUSY)) return true; delayMicroseconds(1);} return false; }
bool pollOutReady(){ for(uint32_t t=0;t<50000;t++){ if( c2ReadAR()&C2ADD_OUTREADY) return true; delayMicroseconds(1);} return false; }

// FPDAT write (+InBusy) / read (+OutReady): x893 C2_Write_FPDAT / C2_Read_FPDAT
bool fpWrite(uint8_t d){ c2WriteAR(0xB4); if(!c2WriteDR(d)) return false; return pollInBusy(); }
bool fpRead(uint8_t *out){ if(!pollOutReady()) return false; c2WriteAR(0xB4); return c2ReadDR(out); }
bool fpWriteRead(uint8_t d, uint8_t *out){ if(!fpWrite(d)) return false; return fpRead(out); }

// Reset + enable/halt PI: x893 C2_Connect_Target (FPCTL 0x02,0x04,0x01)
bool c2Connect() {
  c2Reset();
  c2WriteAR(0x02);               // FPCTL
  if(!c2WriteDR(0x02)) return false;
  if(!c2WriteDR(0x04)) return false;   // halt core
  delayMicroseconds(80);
  if(!c2WriteDR(0x01)) return false;
  delay(25);
  return true;
}

// Flash Block Read (x893 C2_Read_Memory flow): cmd 0x06 → 0x0D → hi → lo → count → 0x0D → bytes
bool flashRead(uint16_t addr, uint8_t count, uint8_t *buf, uint8_t *st) {
  uint8_t r;
  if(!fpWriteRead(0x06, &st[0])) return false;   // cmd + response (очік. 0x0D)
  if(!fpWrite((addr>>8)&0xFF)) return false;      // high addr
  if(!fpWrite(addr&0xFF))      return false;      // low addr
  if(!fpWrite(count))          return false;      // byte count
  if(!fpRead(&st[1]))          return false;      // response (очік. 0x0D)
  for(uint8_t i=0;i<count;i++){ if(!fpRead(&buf[i])) return false; }
  return true;
}

void printHex(uint8_t b){ if(b<0x10) Serial.print('0'); Serial.print(b,HEX); }

void readState() {
  // ТІЛЬКИ reset + читання ID, БЕЗ FPCTL-halt → осцилограф не застрягне (лише коротко скидається).
  c2Reset();
  uint8_t devId=0, rev=0;
  c2WriteAR(0x00); bool okId = c2ReadDR(&devId);
  c2WriteAR(0x01); bool okRev= c2ReadDR(&rev);

  Serial.println(F("---- Device ID test (no halt) ----"));
  Serial.print(F("Device ID / Rev: 0x")); printHex(devId); Serial.print(F(" / 0x")); printHex(rev);
  if (okId && devId==0x0C) Serial.println(F("   [0x0C = C8051F41x — OK!]"));
  else if (devId==0xFF || !okId) Serial.println(F("   [0xFF/timeout — нема відгуку]"));
  else Serial.println(F("   [інше значення]"));
  Serial.println();
}

void setup() {
  pinMode(C2CK, OUTPUT);
  pinMode(C2D, OUTPUT);
  ckP=g_APinDescription[C2CK].pPort; ckM=g_APinDescription[C2CK].ulPin;
  dP =g_APinDescription[C2D].pPort;  dM =g_APinDescription[C2D].ulPin;
  ckHigh(); dOff();
  Serial.begin(115200);
  while(!Serial && millis()<3000){}
  delay(200);
  Serial.println(F("=== Due C2 reader (C8051F41x), x893-port PIO — READ-ONLY ==="));
}

void loop() {
  if(Serial.available()){ char c=Serial.read(); if(c=='s'||c=='S') readState(); }
  static unsigned long last=0;
  if(millis()-last>3000){ last=millis(); readState(); }
}
