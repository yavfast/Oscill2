// Uno: відпустити C2, щоб осцилограф працював. Один reset-імпульс (зняти halt) →
// тримати C2CK(/RST) високим (MCU біжить) → C2D у вхід (відпустити).
#define C2CK_BIT _BV(5)   // D5
#define C2D_BIT  _BV(6)   // D6
void setup(){
  DDRD |= C2CK_BIT;
  PORTD &= ~C2CK_BIT; delayMicroseconds(30);   // reset > 20мкс
  PORTD |= C2CK_BIT;                            // /RST деасерт → MCU працює
  DDRD &= ~C2D_BIT; PORTD &= ~C2D_BIT;         // C2D вхід (відпустити)
  Serial.begin(115200);
}
void loop(){ Serial.println("C2 released - scope free"); delay(2000); }
