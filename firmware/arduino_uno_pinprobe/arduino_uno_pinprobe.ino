// D5/D6 health self-test + hold for voltmeter.
// Self-test: drive each pin LOW then HIGH, read PIND back. Healthy pin reads its own level.
// Then hold the normal operating state: C2CK(D5)=OUTPUT HIGH (~5V, holds /RST high = scope runs),
// C2D(D6)=INPUT no-pull-up (the read state) and print digitalRead(D6) so we see what the line does.
// NOTE: the self-test briefly drives D5(=/RST) low -> a short scope reset (harmless).
#define C2CK_BIT _BV(5)   // D5 = C2CK (=/RST)
#define C2D_BIT  _BV(6)   // D6 = C2D

uint8_t selftest(uint8_t bit){
  uint8_t m = _BV(bit), ok = 1;
  DDRD |= m;  PORTD &= ~m; delayMicroseconds(80); if(  PIND & m ) ok = 0;   // drive LOW  -> expect 0
  PORTD |= m;              delayMicroseconds(80); if(!(PIND & m)) ok = 0;   // drive HIGH -> expect 1
  DDRD &= ~m; PORTD &= ~m;                                                  // release (input, no pull-up)
  return ok;
}

void setup(){
  Serial.begin(115200);
  delay(300);
  Serial.println(F("=== D5/D6 pin health self-test ==="));
  uint8_t d5 = selftest(5);
  uint8_t d6 = selftest(6);
  Serial.print(F("D5 (C2CK): ")); Serial.println(d5 ? F("OK - drives 0 & 1, reads both -> NOT burnt") : F("FAULTY"));
  Serial.print(F("D6 (C2D):  ")); Serial.println(d6 ? F("OK - drives 0 & 1, reads both -> NOT burnt") : F("FAULTY"));
  // Hold normal operating state:
  DDRD |= C2CK_BIT; PORTD |= C2CK_BIT;    // C2CK = OUTPUT HIGH (~5V is NORMAL: /RST deasserted)
  DDRD &= ~C2D_BIT; PORTD &= ~C2D_BIT;    // C2D  = INPUT, no pull-up (the read state)
}

void loop(){
  Serial.print(F("HOLD: D5=OUT HIGH(~5V=normal /RST-high)  D6=IN no-pullup, digitalRead(D6)="));
  Serial.println((PIND & C2D_BIT) ? 1 : 0);
  delay(1500);
}
