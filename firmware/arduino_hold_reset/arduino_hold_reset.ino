// Тест: тримати C2CK (D5 = /RST цілі) постійно LOW → ціль має бути в reset.
#define C2CK_BIT _BV(5)   // D5
void setup(){
  DDRD |= C2CK_BIT;         // D5 output
  PORTD &= ~C2CK_BIT;       // D5 LOW → /RST asserted (hold target in reset)
  Serial.begin(115200);
}
void loop(){ Serial.println("HOLDING /RST LOW"); delay(1000); }
