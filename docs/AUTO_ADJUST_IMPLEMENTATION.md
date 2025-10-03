# Auto Adjust Feature - Implementation Summary

## Дата реалізації: 3 жовтня 2025

## Огляд

Реалізовано функціонал автоматичного налаштування параметрів осцилографа:
- **Auto V/div** - автомасштабування напруги
- **Auto Time/div** - автомасштабування часу
- **Auto V Offset** - автоцентрування по вертикалі
- **Auto Trigger Level** - автоналаштування рівня тригера

## Реалізовані компоненти

### Backend (Python)

#### 1. `web_oscill/auto_adjust.py` - новий модуль
**Функції:**
- `auto_adjust_v_div()` - рекурсивна оптимізація V/div (fill factor 0.2-0.8)
- `auto_adjust_t_div()` - рекурсивна оптимізація Time/div (4-8 сегментів)
- `auto_adjust_v_offset()` - центрування сигналу по вертикалі
- `auto_adjust_trigger_level()` - встановлення тригера на середину амплітуди
- `auto_adjust_multiple()` - виконання множинних налаштувань у правильному порядку
- `find_next_vdiv()`, `find_next_tdiv()` - допоміжні функції пошуку

**Константи:**
```python
VDIV_VALUES_MV = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
TDIV_VALUES_MS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]
FILL_FACTOR_MIN = 0.2
FILL_FACTOR_MAX = 0.8
SEGMENTS_COUNT_MIN = 4
SEGMENTS_COUNT_MAX = 8
MAX_ITERATIONS = 10
ITERATION_DELAY = 0.2  # seconds
```

#### 2. `web_oscill/main.py` - доданий endpoint
**Новий route:**
```python
@app.post("/api/auto")
def api_auto(types: Optional[str] = None)
```

**Параметри:**
- `types` - comma-separated list: `v_div,t_div,v_offset,trigger`
- За замовчуванням (якщо не вказано): всі типи

**Response:**
```json
{
  "success": true,
  "applied": ["v_div", "t_div"],
  "config": { /* updated config */ },
  "iterations": {
    "v_div": 3,
    "t_div": 2
  },
  "details": {
    "v_div": {
      "success": true,
      "old_value": 200,
      "new_value": 500,
      "reason": "optimal",
      "history": [...]
    }
  }
}
```

### Frontend (JavaScript)

#### 1. `verticalControl.js` - додано кнопки
**Зміни:**
- Додано параметр `onAutoVScale` в constructor
- Додано параметр `onAutoVOffset` в constructor
- Додано кнопку **"Auto"** поруч з V/div (224px)
- Додано кнопку **"Center"** поруч з Position slider

#### 2. `horizontalControl.js` - додано кнопку
**Зміни:**
- Додано параметр `onAutoTScale` в constructor
- Додано кнопку **"Auto"** поруч з Time/div (224px)

#### 3. `triggerControl.js` - додано кнопку
**Зміни:**
- Додано параметр `onAutoTrigger` in constructor
- Додано кнопку **"Auto"** поруч з Trigger Level slider

#### 4. `controlPanel.js` - підключення callbacks
**Зміни:**
- Додано параметр `onAutoAdjust` в constructor
- Передача callbacks у всі control:
  ```javascript
  onAutoVScale: () => this.onAutoAdjust('v_div')
  onAutoVOffset: () => this.onAutoAdjust('v_offset')
  onAutoTScale: () => this.onAutoAdjust('t_div')
  onAutoTrigger: () => this.onAutoAdjust('trigger')
  ```

#### 5. `app.js` - головна логіка
**Зміни:**
- Додано `this.autoAdjustInProgress` flag
- Додано параметр `onAutoAdjust` в ControlPanel constructor
- Додано метод `handleAutoAdjust(types)`:
  - Перевірка стану (device connected, не в процесі)
  - Зупинка polling під час auto-adjust
  - Виклик API `/api/auto?types=...`
  - Оновлення UI з новою конфігурацією
  - Відновлення polling після завершення
  - Логування результатів (iterations, applied types)

## Алгоритми

### Auto V/div
1. Отримати кадр даних
2. Розрахувати `fill_factor = data_v_range / full_v_range`
3. Якщо `fill_factor > 0.8`: збільшити V/div, рекурсія
4. Якщо `fill_factor < 0.2`: зменшити V/div, рекурсія
5. Інакше: оптимально, зупинка

### Auto Time/div
1. Отримати кадр даних
2. Розрахувати `segments_count` (напівперіоди сигналу)
3. Якщо `segments_count < 4`: збільшити Time/div, рекурсія
4. Якщо `segments_count > 8`: зменшити Time/div, рекурсія
5. Інакше: оптимально, зупинка

### Auto V Offset
1. Отримати кадр даних
2. Розрахувати центр: `(v_max + v_min) / 2`
3. Конвертувати у raw value (0-255)
4. Застосувати, без рекурсії

### Auto Trigger Level
1. Отримати кадр даних
2. Розрахувати середнє значення samples
3. Встановити як trigger level
4. Без рекурсії

## Порядок виконання

При множинних типах виконується у порядку:
1. **v_div** - масштаб напруги
2. **v_offset** - центрування (залежить від v_div)
3. **trigger** - рівень тригера (залежить від v_div і v_offset)
4. **t_div** - масштаб часу (незалежний)

## Захист

- Максимум 10 ітерацій на кожен тип
- Delay 200ms між ітераціями для стабілізації
- Перевірка меж списків V/div та Time/div
- Guard flag для запобігання одночасного виконання
- Зупинка/відновлення polling під час auto-adjust
- Логування всіх кроків та результатів

## Файли змінено

### Backend:
1. `web_oscill/auto_adjust.py` - **новий файл** (620 рядків)
2. `web_oscill/main.py` - додано import і endpoint `/api/auto`

### Frontend:
1. `web_oscill/static/js/modules/controls/verticalControl.js` - додано 2 кнопки
2. `web_oscill/static/js/modules/controls/horizontalControl.js` - додано 1 кнопку
3. `web_oscill/static/js/modules/controls/triggerControl.js` - додано 1 кнопку
4. `web_oscill/static/js/modules/controlPanel.js` - додано callbacks
5. `web_oscill/static/app.js` - додано метод `handleAutoAdjust()`

### Documentation:
1. `docs/auto_adjust_api.md` - **новий файл** - повна документація API

## Використання

### Приклади API запитів:

**Auto voltage scale:**
```bash
curl -X POST "http://localhost:5000/api/auto?types=v_div"
```

**Auto time scale:**
```bash
curl -X POST "http://localhost:5000/api/auto?types=t_div"
```

**Center signal vertically:**
```bash
curl -X POST "http://localhost:5000/api/auto?types=v_offset"
```

**Auto everything:**
```bash
curl -X POST "http://localhost:5000/api/auto?types=v_div,v_offset,trigger,t_div"
```

### UI кнопки:

- **Vertical section:**
  - "Auto" біля V/div → auto voltage scale
  - "Center" біля Position → center signal

- **Horizontal section:**
  - "Auto" біля Time/div → auto time scale

- **Trigger section:**
  - "Auto" біля Level → auto trigger level

## Тестування

Рекомендовані сценарії тестування:

1. **Auto V/div:**
   - Маленький сигнал (10mV) → має збільшити масштаб
   - Великий сигнал (5V) → має зменшити масштаб
   - Оптимальний сигнал → має залишити без змін

2. **Auto Time/div:**
   - Висока частота (багато циклів) → має зменшити Time/div
   - Низька частота (мало циклів) → має збільшити Time/div
   - DC сигнал (0 сегментів) → має залишити без змін

3. **Auto V Offset:**
   - Зміщений вгору сигнал → має центрувати
   - Зміщений вниз сигнал → має центрувати

4. **Auto Trigger:**
   - Будь-який сигнал → має встановити тригер на середину

5. **Multiple types:**
   - Перевірити послідовність виконання
   - Перевірити що всі зміни застосовані

## Відомі обмеження

1. Auto Time/div не працює з DC сигналами (segments_count = 0)
2. Максимум 10 ітерацій - може не знайти оптимум для дуже складних сигналів
3. Delay 200ms між ітераціями - може тривати до 2 секунд для складних випадків
4. Polling зупиняється під час auto-adjust - екран не оновлюється

## Можливі покращення

1. **UI індикатор прогресу** - показувати "Auto adjusting..." під час виконання
2. **Toast notifications** - повідомлення про результат
3. **Disable кнопок** - блокувати інші зміни під час auto-adjust
4. **Smart delay** - адаптивний delay залежно від швидкості стабілізації
5. **History tracking** - зберігати історію auto-adjust для аналізу
6. **Preset buttons** - "Auto All" для одночасного налаштування всього
7. **Config save** - зберігати оптимальні налаштування для різних сигналів

## Статус

✅ **Всі компоненти реалізовано та готові до тестування**

Потрібно протестувати на реальному пристрої для перевірки:
- Коректності алгоритмів
- Швидкодії
- Стабільності
- User experience

---

*Реалізовано відповідно до плану з `docs/auto_adjust_api.md`*
