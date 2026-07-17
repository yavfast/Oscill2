// Повністю відпустити C2 (обидві лінії high-Z) — нуль впливу Uno; плата сама керує /RST.
#define C2CK_BIT _BV(5)
#define C2D_BIT  _BV(6)
void setup(){
  // короткий reset-імпульс, щоб зняти можливий FPCTL-halt, потім повністю відпустити
  DDRD |= C2CK_BIT; PORTD &= ~C2CK_BIT; delayMicroseconds(50); PORTD |= C2CK_BIT; delay(5);
  DDRD &= ~(C2CK_BIT | C2D_BIT);          // обидва входи (high-Z)
  PORTD &= ~(C2CK_BIT | C2D_BIT);         // без pull-up
  Serial.begin(115200);
}
void loop(){ Serial.println("C2 fully released (hi-Z)"); delay(2000); }
