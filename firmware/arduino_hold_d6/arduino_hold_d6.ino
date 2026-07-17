// SWAP TEST: drive D6 LOW, D5 HIGH. If the scope RESETS (dies on OBEX) with D6 low,
// then D6 is actually wired to -RFS(/RST) => C2CK and C2D are SWAPPED.
// If the scope stays alive with BOTH D5-low (prev test) and D6-low, then neither pin
// reaches /RST => GND not shared (or both signal wires off).  Non-destructive (reset only).
#define C2CK_BIT _BV(5)  // D5
#define C2D_BIT  _BV(6)  // D6
void setup(){
  DDRD |= C2CK_BIT; PORTD |=  C2CK_BIT;   // D5 HIGH
  DDRD |= C2D_BIT;  PORTD &= ~C2D_BIT;    // D6 LOW  (would assert /RST iff D6 is on -RFS)
  Serial.begin(115200);
}
void loop(){ Serial.println("SWAP TEST: D6=LOW D5=HIGH"); delay(1000); }
