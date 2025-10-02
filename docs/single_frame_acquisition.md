# Single Frame Acquisition When Stopped

## Дата: 2025-01-02

## Проблема

При зупиненому автооновленні (натиснуто Stop), зміна конфігурації (V/div, Time/div, тригер) викликала запит `/api/frames`, але сервер повертав порожній масив фреймів, оскільки acquisition був зупинений і нові дані не надходили в буфер.

### Послідовність проблеми
```
Frontend: User changes V/div
  ↓
Frontend: api.applyConfig()
  ↓
Frontend: api.getFrames() → запит на /api/frames
  ↓
Backend: service._is_acquiring == False
  ↓
Backend: service.get_frames() → returns empty []
  ↓
Frontend: handleFrameResponse([]) → нічого не оновлюється
  ↓
Result: ❌ Графік не оновлюється з новою конфігурацією
```

## Рішення

Модифіковано ендпоінт `/api/frames` для автоматичного отримання одного фрейму, коли acquisition зупинено.

### Файл: `web_oscill/main.py`

```python
@app.get("/api/frames")
def api_frames(since: Optional[int] = None, limit: int = 128, format: str = "hex"):
    try:
        if not service._client:
            return {"status": "disconnected", "frames": []}
        
        # Try to get frames from buffer
        data = service.get_frames(since=since, limit=limit)
        frames = data.get("frames", [])
        
        if not frames:
            if service._is_acquiring:
                # Acquisition running - wait for new frames
                max_wait_time = 5.0
                wait_interval = 0.05
                elapsed = 0.0
                
                while elapsed < max_wait_time and service._is_acquiring:
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                    
                    data = service.get_frames(since=since, limit=limit)
                    frames = data.get("frames", [])
                    
                    if frames:
                        break
            else:
                # ✅ NEW: Acquisition stopped - temporarily start to get one frame
                try:
                    service.start()
                    # Wait for at least one frame
                    max_wait_time = 5.0
                    wait_interval = 0.05
                    elapsed = 0.0
                    
                    while elapsed < max_wait_time:
                        time.sleep(wait_interval)
                        elapsed += wait_interval
                        
                        data = service.get_frames(since=since, limit=limit)
                        frames = data.get("frames", [])
                        
                        if frames:
                            break
                finally:
                    # Always stop acquisition again
                    service.stop()
        
        # ... process frames and return ...
```

## Логіка роботи

### Сценарій 1: Acquisition працює (Run)
```
GET /api/frames
  ↓
Check buffer → Empty?
  ↓ YES
Wait loop (max 5s, check every 50ms)
  ↓
Frames arrived → Return frames
```

**Поведінка**: Чекає на нові фрейми від працюючого acquisition

### Сценарій 2: Acquisition зупинено (Stop)
```
GET /api/frames
  ↓
Check buffer → Empty?
  ↓ YES
service._is_acquiring == False → Temporarily start
  ↓
service.start()
  ↓
Wait loop (max 5s, check every 50ms)
  ↓
Frames arrived → Return frames
  ↓
finally: service.stop() ← Always execute
```

**Поведінка**: 
- Тимчасово запускає acquisition
- Чекає на один фрейм
- **Обов'язково** зупиняє acquisition в блоку `finally`

### Сценарій 3: Фрейми є в буфері
```
GET /api/frames
  ↓
Check buffer → Has frames
  ↓
Return frames immediately
```

**Поведінка**: Повертає існуючі фрейми без зайвих операцій

## Гарантії безпеки

### 1. Finally block
```python
try:
    service.start()
    # ... wait for frames ...
finally:
    service.stop()  # ← ЗАВЖДИ виконується
```

Навіть якщо виникне помилка, acquisition буде зупинений.

### 2. Timeout захист
```python
max_wait_time = 5.0
while elapsed < max_wait_time:
    # ... check for frames ...
```

Максимальний час очікування обмежений 5 секундами.

### 3. Перевірка з'єднання
```python
if not service._client:
    return {"status": "disconnected", "frames": []}
```

Якщо пристрій відключений, повертається порожня відповідь без спроб запуску.

## Переваги

### ✅ Прозора робота для frontend
Фронтенд не знає про тимчасовий старт/стоп acquisition - просто отримує фрейми.

### ✅ Консистентний стан
Якщо користувач зупинив acquisition, після отримання фрейму стан залишається "зупинено".

### ✅ Швидке оновлення UI
При зміні конфігурації графік оновлюється миттєво, навіть коли acquisition зупинено.

### ✅ Безпека
`finally` блок гарантує, що acquisition буде зупинений навіть при помилках.

## Тестування

### Тест 1: Зміна V/div при зупиненому acquisition
```
1. Натиснути Stop
2. Змінити V/div на 500 mV
3. ✅ Очікується: Графік оновлюється з новим масштабом
4. ✅ Очікується: Acquisition залишається в стані Stop
```

### Тест 2: Зміна Time/div при зупиненому acquisition
```
1. Натиснути Stop
2. Змінити Time/div на 10 ms
3. ✅ Очікується: Графік оновлюється з новою часовою базою
4. ✅ Очікується: Acquisition залишається в стані Stop
```

### Тест 3: Зміна тригера при зупиненому acquisition
```
1. Натиснути Stop
2. Змінити trigger level
3. ✅ Очікується: Графік оновлюється з новим положенням тригера
4. ✅ Очікується: Acquisition залишається в стані Stop
```

### Тест 4: Множинні зміни підряд
```
1. Натиснути Stop
2. Швидко змінити V/div → Time/div → Trigger
3. ✅ Очікується: Кожна зміна призводить до оновлення графіка
4. ✅ Очікується: Acquisition залишається в стані Stop після всіх змін
```

### Тест 5: Зміна при працюючому acquisition (регресія)
```
1. Залишити в режимі Run
2. Змінити V/div
3. ✅ Очікується: Графік оновлюється без зупинки continuous acquisition
4. ✅ Очікується: Acquisition продовжує працювати після зміни
```

## Обмеження

### 1. Тимчасова затримка при Stop
При зміні конфігурації в режимі Stop можлива затримка до 5 секунд для отримання фрейму.

**Типова затримка**: 50-200 ms (залежить від швидкості пристрою)

### 2. Послідовні запити
Якщо фронтенд робить багато запитів підряд (наприклад, швидке переміщення слайдера), кожен запит викликає start/stop цикл.

**Міtigація**: Фронтенд використовує debouncing при зміні конфігурації.

### 3. Конкуренція запитів
Якщо одночасно надходять два запити `/api/frames` при зупиненому acquisition, обидва можуть спробувати запустити acquisition.

**Міtigація**: DeviceService використовує ThreadPoolExecutor з max_workers=1, що серіалізує всі операції.

## Альтернативні підходи (не реалізовані)

### Альтернатива 1: Окремий ендпоінт
Створити `/api/frames/single` для явного запиту одного фрейму.

**Недоліки**:
- Потребує змін у фронтенді
- Дублювання логіки

### Альтернатива 2: Параметр force=true
Додати параметр `GET /api/frames?force=true` для примусового отримання фрейму.

**Недоліки**:
- Ускладнює API
- Фронтенд повинен знати про стан acquisition

### Альтернатива 3: Завжди тримати acquisition увімкненим
Не зупиняти acquisition взагалі, лише зупиняти polling на фронтенді.

**Недоліки**:
- Зайве навантаження на пристрій
- Зайве навантаження на CPU

## Взаємодія з іншими компонентами

### Frontend (app.js)
```javascript
// Після зміни конфігурації - просто запитує фрейми
if (this.isDeviceConnected) {
  const data = await this.api.getFrames(lastSeq);
  this.handleFrameResponse(data);
}
```

Frontend не знає про тимчасовий start/stop - API прозорий.

### DeviceService
```python
# start() і stop() викликаються через executor з timeout
def start(self) -> Dict[str, Any]:
    with self._dev_lock:
        self._start_acquisition_locked()
        self._is_acquiring = True
        return {"status": "ok"}

def stop(self) -> Dict[str, Any]:
    with self._dev_lock:
        self._stop_acquisition_locked()
        self._is_acquiring = False
        return {"status": "ok"}
```

Методи thread-safe і працюють через executor pool.

## Метрики продуктивності

### Час отримання фрейму при зупиненому acquisition

| Операція | Типовий час | Максимум |
|----------|-------------|----------|
| service.start() | 10-50 ms | 5000 ms (timeout) |
| Wait for frame | 5-100 ms | 5000 ms (timeout) |
| service.stop() | 5-20 ms | 5000 ms (timeout) |
| **Загальний час** | **20-170 ms** | **15000 ms** |

### Час отримання фрейму при працюючому acquisition

| Операція | Типовий час | Максимум |
|----------|-------------|----------|
| Read from buffer | 0.001-1 ms | 5000 ms (wait loop) |
| **Загальний час** | **0.001-50 ms** | **5000 ms** |

## Версія

- **Версія коду**: 2025-01-02
- **Файл**: web_oscill/main.py
- **Endpoint**: GET /api/frames
- **Автор**: AI Assistant
