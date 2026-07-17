// Тимчасовий скетч: ВІДПУСТИТИ C2, щоб осцилограф працював нормально по своєму USB.
// Один reset-імпульс на C2CK(=/RST) знімає можливий halt, далі тримаємо /RST високим
// (MCU у робочому режимі) і відпускаємо C2D. Ніякого періодичного halt.
const int C2CK = 22;   // = /RST
const int C2D  = 24;

void setup() {
  Serial.begin(115200);
  pinMode(C2CK, OUTPUT);
  digitalWrite(C2CK, LOW);  delayMicroseconds(30);   // reset-імпульс > 20мкс
  digitalWrite(C2CK, HIGH);                          // /RST деасерт → MCU біжить
  pinMode(C2D, INPUT);                               // відпустити лінію даних
}

void loop() {
  Serial.println("MCU free-running: C2CK=HIGH (/RST off), C2D released. Scope should work.");
  delay(3000);
}
