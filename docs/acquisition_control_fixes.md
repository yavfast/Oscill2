# Acquisition Control Fixes

## Дата: 2025-01-02

## Проблеми

### 1. Відсутність оновлення UI при зміні конфігурації в режимі паузи
**Проблема**: Коли автооновлення зупинено (натиснуто Stop), зміна конфігурації (наприклад, V/div, Time/div, тригер) не оновлювала графік на екрані.

**Причина**: Код запитував один фрейм тільки якщо polling НЕ був активний (`!wasPolling`), але правильніше перевіряти чи acquisition зупинено (`!this.isRunning`).

### 2. Неможливість повторного запуску після зупинки
**Проблема**: Після натискання Stop і потім Start, автооновлення не відновлювалося - графік залишався "замороженим".

**Причина**: Метод `onAcquisitionChange()` викликав `api.start()` і встановлював `this.isRunning = true`, але НЕ запускав polling через `startPolling()`. Polling залишався зупиненим.

## Рішення

### Файл: `web_oscill/static/app.js`

#### 1. Виправлення оновлення UI при зміні конфігурації

```javascript
async onConfigChange(changes) {
  const wasPolling = !!this.pollInterval;
  if (wasPolling) {
    this.stopPolling();
  }
  
  try {
    const response = await this.api.applyConfig(changes);
    
    if (response.config) {
      // ... update config ...
    }
    
    // ✅ ВИПРАВЛЕНО: Завжди запитуємо фрейм після зміни конфігурації
    if (this.isDeviceConnected) {
      console.log('[App] Requesting frame after config change (isRunning:', this.isRunning, ')');
      try {
        const lastSeq = this.api.getLastSeq();
        const data = await this.api.getFrames(lastSeq);
        this.handleFrameResponse(data);
      } catch (e) {
        console.error('Frame request after config change failed:', e);
      }
    }
    
    // Resume polling if needed
    if (wasPolling && this.isDeviceConnected && this.isRunning) {
      this.startPolling();
    }
  } catch (e) {
    // ... error handling ...
  }
}
```

**Зміни**:
- Видалено умову `!this.isRunning` - тепер запит фрейму виконується завжди
- При зміні конфігурації **завжди** запитується один фрейм для негайного оновлення UI
- Не залежить від стану acquisition (Run/Stop) - UI оновлюється миттєво в обох випадках
- Якщо acquisition працює (`Run`), після отримання фрейму polling відновлюється і продовжує роботу

#### 2. Виправлення повторного запуску acquisition

```javascript
// ❌ БУЛО (синхронний, не запускав polling):
onAcquisitionChange(action) {
  if (action === 'run') {
    this.isRunning = true;
    this.api.start().catch(e => console.error('Start acquisition error:', e));
  } else if (action === 'stop') {
    this.isRunning = false;
    this.api.stop().catch(e => console.error('Stop acquisition error:', e));
  }
}

// ✅ СТАЛО (async, запускає/зупиняє polling):
async onAcquisitionChange(action) {
  if (action === 'run') {
    console.log('[App] Starting acquisition...');
    try {
      await this.api.start();
      this.isRunning = true;
      this.startPolling(); // ← ДОДАНО
      console.log('[App] Acquisition started and polling resumed');
    } catch (e) {
      console.error('Start acquisition error:', e);
    }
  } else if (action === 'stop') {
    console.log('[App] Stopping acquisition...');
    try {
      await this.api.stop();
      this.isRunning = false;
      this.stopPolling(); // ← ДОДАНО
      console.log('[App] Acquisition stopped and polling paused');
    } catch (e) {
      console.error('Stop acquisition error:', e);
    }
  } else if (action === 'single') {
    this.acquireSingleFrame();
  }
}
```

**Зміни**:
- Метод став `async` для правильного очікування відповіді від сервера
- При `action === 'run'`: додано `this.startPolling()` після успішного старту
- При `action === 'stop'`: додано `this.stopPolling()` після успішної зупинки
- Додано логування для відстеження стану
- Тепер послідовність правильна: Start → запустити acquisition на сервері → запустити polling

## Тестування

### Тест 1: Зміна конфігурації при зупиненому acquisition
1. Натиснути **Stop** (зупинити автооновлення)
2. Змінити V/div або Time/div
3. ✅ **Очікуваний результат**: Графік оновлюється відразу з новою конфігурацією
4. ✅ **Раніше**: Графік не оновлювався до натискання Start

### Тест 2: Повторний запуск acquisition
1. Відкрити веб-інтерфейс (автоматичний старт)
2. Натиснути **Stop** → автооновлення зупиняється
3. Натиснути **Start** → автооновлення відновлюється
4. ✅ **Очікуваний результат**: Графік оновлюється в реальному часі
5. ✅ **Раніше**: Графік залишався "замороженим"

### Тест 3: Багаторазове перемикання Start/Stop
1. Натиснути **Stop** → **Start** → **Stop** → **Start** (кілька разів)
2. ✅ **Очікуваний результат**: Кожне натискання працює коректно
3. Polling запускається/зупиняється відповідно до стану

### Тест 4: Зміна конфігурації при працюючому acquisition
1. Залишити acquisition у режимі **Run**
2. Змінити конфігурацію
3. ✅ **Очікуваний результат**: 
   - Polling зупиняється на час оновлення конфігурації
   - Конфігурація застосовується
   - Polling відновлюється автоматично
   - Графік продовжує оновлюватися

## Логіка роботи

### Режим Run (автооновлення активне)
```
User clicks Start
  ↓
api.start() → Server starts acquisition
  ↓
this.isRunning = true
  ↓
this.startPolling() → Start interval 100ms
  ↓
Every 100ms: api.getFrames(since) → Update UI
```

### Режим Stop (автооновлення зупинено)
```
User clicks Stop
  ↓
api.stop() → Server stops acquisition
  ↓
this.isRunning = false
  ↓
this.stopPolling() → Clear interval
  ↓
UI shows last frame (frozen)
```

### Зміна конфігурації (незалежно від стану)
```
User changes config (e.g., V/div, Time/div, Trigger)
  ↓
stopPolling() → Pause updates (if running)
  ↓
api.applyConfig() → Apply changes on server
  ↓
api.getFrames(lastSeq) → Request ONE frame immediately
  ↓
handleFrameResponse() → Update UI with new config
  ↓
Check: was polling && isRunning?
  ↓ YES
startPolling() → Resume continuous updates
  ↓ NO
UI shows updated frame (frozen at new config)
```

**Ключова зміна**: Запит фрейму виконується **завжди** після зміни конфігурації, незалежно від стану Run/Stop. Це забезпечує:
- ✅ Миттєве оновлення UI в режимі Stop
- ✅ Миттєве оновлення UI в режимі Run (без очікування наступного циклу polling)
- ✅ Відсутність "запізнення" при зміні параметрів

## Поведінка кнопок

| Стан | Start Button | Stop Button | Single Button |
|------|--------------|-------------|---------------|
| **Disconnected** | Disabled | Disabled | Disabled |
| **Connected + Stop** | Enabled | Disabled | Enabled |
| **Connected + Run** | Disabled | Enabled | Disabled |
| **Single acquisition** | Disabled | Disabled | Disabled |

## Залежні компоненти

- `web_oscill/static/app.js` - Головний контролер
- `web_oscill/static/js/modules/api.js` - API клієнт
- `web_oscill/static/js/modules/controlPanel.js` - Панель керування
- `web_oscill/device_service.py` - Сервіс на backend
- `web_oscill/main.py` - API endpoints `/api/start`, `/api/stop`

## Відомі обмеження

1. При поганому з'єднанні з пристроєм, Start може не спрацювати - потрібна обробка помилки з retry
2. Якщо сервер падає під час acquisition, фронтенд залишиться в стані "Run" - потрібен watchdog

## Майбутні покращення

- [ ] Додати індикатор "завантаження" під час apply config
- [ ] Додати retry логіку для start/stop при помилках
- [ ] Додати watchdog для перевірки з'єднання кожні N секунд
- [ ] Зберігати стан Run/Stop в localStorage для відновлення після перезавантаження

## Версія

- **Версія коду**: 2025-01-02
- **Автор виправлень**: AI Assistant
- **Тестування**: Manual
