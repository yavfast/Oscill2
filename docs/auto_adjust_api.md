# API Auto Adjust - Автоматичне налаштування параметрів

## Огляд

API команда `/auto` для автоматичного підбору оптимальних параметрів осцилографа: масштаб напруги, масштаб часу, вертикальне позиціювання та рівень тригера.

## API Endpoint

```
POST /auto?type=v_div,t_div
```

### Query параметри

- `type` - список типів автоналаштувань (через кому): 
  - `v_div` - автомасштабування напруги (V/div)
  - `t_div` - автомасштабування часу (Time/div)
  - `v_offset` - автоцентрування по вертикалі
  - `trigger` - автоналаштування рівня тригера

### Response

```json
{
  "success": true,
  "applied": ["v_div", "t_div"],
  "config": { /* оновлена конфігурація */ },
  "iterations": {
    "v_div": 3,
    "t_div": 2
  },
  "details": {
    "v_div": {
      "old_value": 200,
      "new_value": 500,
      "reason": "optimal"
    },
    "t_div": {
      "old_value": 5,
      "new_value": 2,
      "reason": "optimal"
    }
  }
}
```

---

## Алгоритми автоналаштування

### 1. Auto V/div (Voltage Scale) - `type=v_div`

**Мета:** Автоматично підібрати масштаб напруги так, щоб сигнал займав 20-80% екрану по вертикалі.

**Алгоритм:**

1. **Отримати поточні дані:**
   - Запитати один кадр даних з пристрою (`device_service.acquire_single_frame()`)
   - Розрахувати measurements через `calculate_measurements()`

2. **Розрахувати діапазони:**
   - `full_v_range_mv` = `v_div × 8` (8 поділок екрану)
   - `v_data_max_mv` = `abs(measurements['v_max']['v'])`
   - `v_data_min_mv` = `abs(measurements['v_min']['v'])`
   - `data_v_range_mv` = `2 × max(v_data_max_mv, v_data_min_mv)` (подвоєна максимальна амплітуда від центру)

3. **Розрахувати коефіцієнт заповнення:**
   - `fill_factor` = `data_v_range_mv / full_v_range_mv`

4. **Прийняти рішення:**
   - Якщо `fill_factor > 0.8` → сигнал занадто великий:
     - Знайти наступний більший V/div у списку `VDIV_VALUES_MV`
     - Застосувати через `device_service.set_config()`
     - **РЕКУРСІЯ:** повторити алгоритм (макс 10 ітерацій)
   
   - Якщо `fill_factor < 0.2` → сигнал занадто малий:
     - Знайти наступний менший V/div у списку
     - Застосувати конфігурацію
     - **РЕКУРСІЯ:** повторити алгоритм
   
   - Інакше (`0.2 ≤ fill_factor ≤ 0.8`):
     - Оптимальний масштаб знайдено, зупинитись

5. **Захист:**
   - Максимум 10 ітерацій
   - Не виходити за межі списку V/div
   - Таймаут між ітераціями 200-300ms для стабілізації

**Константи:**
```python
VDIV_VALUES_MV = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]
FILL_FACTOR_MIN = 0.2
FILL_FACTOR_MAX = 0.8
MAX_ITERATIONS = 10
```

---

### 2. Auto Time/div (Time Base) - `type=t_div`

**Мета:** Автоматично підібрати масштаб часу так, щоб на екрані було видно 4-8 повних циклів сигналу.

**Алгоритм:**

1. **Отримати поточні дані:**
   - Запитати кадр з пристрою
   - Розрахувати частоту через `calculate_frequency_from_segments()`

2. **Отримати кількість сегментів:**
   - `segments_count` = `freq_data['segments_count']`
   - Сегмент = напівперіод сигналу (перехід через середнє значення)

3. **Прийняти рішення:**
   - Якщо `segments_count < 4` → занадто мало циклів на екрані:
     - Знайти наступний більший Time/div у списку `TDIV_VALUES_MS`
     - Застосувати конфігурацію (збільшити час на поділку = показати більше часу)
     - **РЕКУРСІЯ:** повторити алгоритм
   
   - Якщо `segments_count > 8` → занадто багато циклів:
     - Знайти наступний менший Time/div
     - Застосувати конфігурацію (зменшити час на поділку = показати менше часу)
     - **РЕКУРСІЯ:** повторити алгоритм
   
   - Інакше (`4 ≤ segments_count ≤ 8`):
     - Оптимальна кількість циклів, зупинитись

4. **Особливості:**
   - Якщо `segments_count == 0` → сигнал не детектується:
     - Використати середнє значення Time/div зі списку (5 ms)
     - Не робити ітерацій

5. **Захист:**
   - Максимум 10 ітерацій
   - Не виходити за межі списку T/div
   - Таймаут між ітераціями

**Константи:**
```python
TDIV_VALUES_MS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]
SEGMENTS_COUNT_MIN = 4
SEGMENTS_COUNT_MAX = 8
MAX_ITERATIONS = 10
```

---

### 3. Auto V Offset (Vertical Position) - `type=v_offset`

**Мета:** Автоматично центрувати сигнал по вертикалі на екрані.

**Алгоритм:**

1. **Отримати поточні дані:**
   - Запитати кадр з пристрою
   - Отримати `v_min_mv` та `v_max_mv` з measurements

2. **Розрахувати центр сигналу:**
   - `signal_center_mv` = `(v_max_mv + v_min_mv) / 2`
   - Це зміщення сигналу відносно нуля

3. **Розрахувати необхідний offset:**
   - Потрібно зсунути сигнал так, щоб `signal_center_mv` був у центрі екрану (0V)
   - `target_offset_mv` = `-signal_center_mv`

4. **Конвертувати у native value:**
   - `v_div_mv` = поточний V/div
   - `full_range_mv` = `v_div_mv × 8`
   - `offset_normalized` = `target_offset_mv / full_range_mv` (діапазон -0.5 .. +0.5)
   - `v_offset_raw` = `128 + offset_normalized × 256` (128 = центр, діапазон 0-255)
   - Clamp до [0, 255]

5. **Застосувати:**
   - Встановити `v_offset` через конфігурацію
   - **Без рекурсії** - одна ітерація достатньо

**Константи:**
```python
V_OFFSET_MIN = 0
V_OFFSET_MAX = 255
V_OFFSET_CENTER = 128
```

---

### 4. Auto Trigger Level - `type=trigger`

**Мета:** Автоматично встановити рівень тригера на 50% амплітуди сигналу.

**Алгоритм:**

1. **Отримати поточні дані:**
   - Запитати кадр з пристрою
   - Отримати `v_min_mv` та `v_max_mv` з measurements

2. **Розрахувати середній рівень:**
   - `trigger_level_mv` = `(v_max_mv + v_min_mv) / 2`
   - Це середина між піками сигналу

3. **Конвертувати у native value (0-255):**
   - Формула залежить від поточного V/div та V offset
   - `v_div_mv` = поточний V/div
   - `full_range_mv` = `v_div_mv × 8`
   - `center_offset_mv` = `(v_offset_raw - 128) / 256 × full_range_mv`
   - `trigger_normalized` = `(trigger_level_mv - center_offset_mv) / full_range_mv + 0.5`
   - `trigger_raw` = `trigger_normalized × 256`
   - Clamp до [0, 255]

4. **Застосувати:**
   - Встановити trigger level через конфігурацію
   - **Без рекурсії** - одна ітерація

**Альтернативний підхід (простіший):**
- Якщо samples доступні напряму:
  - `samples_avg` = середнє значення всіх samples
  - `trigger_raw` = `samples_avg` (вже в діапазоні 0-255 для 8-bit)

**Константи:**
```python
TRIGGER_LEVEL_MIN = 0
TRIGGER_LEVEL_MAX = 255
```

---

## Порядок виконання типів

При множинних типах виконувати у правильному порядку:

1. **v_div** - спочатку масштаб напруги
2. **v_offset** - потім центрування (залежить від v_div)
3. **trigger** - потім рівень тригера (залежить від v_div і v_offset)
4. **t_div** - останнім часовий масштаб (не залежить від інших)

**Обґрунтування:**
- V offset залежить від поточного V/div
- Trigger level залежить від V/div та V offset
- T/div незалежний, може бути будь-коли

---

## Frontend зміни

### 1. Додати Auto кнопки в UI

**verticalControl.js:**
- Додати кнопку "Auto" поруч з V/div +/- кнопками
- При натисканні викликати `this.onAutoVScale?.()`

**horizontalControl.js:**
- Додати кнопку "Auto" поруч з T/div +/- кнопками
- При натисканні викликати `this.onAutoTScale?.()`

**Додаткові кнопки:**
- У verticalControl: "Center" для auto v_offset
- У triggerControl: "Auto Level" для auto trigger

### 2. Додати обробники в ControlPanel

**controlPanel.js** - додати callbacks:
- `onAutoVScale: () => this.handleAutoAdjust('v_div')`
- `onAutoTScale: () => this.handleAutoAdjust('t_div')`
- `onAutoVOffset: () => this.handleAutoAdjust('v_offset')`
- `onAutoTrigger: () => this.handleAutoAdjust('trigger')`

### 3. Імплементація в App

**app.js** - нова функція:
```javascript
async handleAutoAdjust(types) {
  // 1. Показати індикатор завантаження
  // 2. Викликати POST /auto?type=...
  // 3. Дочекатись відповіді
  // 4. Оновити UI через updateControls()
  // 5. Сховати індикатор
}
```

### 4. Індикатор стану Auto

Показувати процес автоналаштування:
- Toast notification: "Auto-adjusting V/div..."
- Disable кнопок під час виконання
- Progress indicator

### 5. Комбіновані режими

**"Auto All" кнопка:**
- Викликати `/auto?type=v_div,t_div,v_offset,trigger`
- Одночасно налаштувати всі параметри

---

## Захист та помилки

### Обмеження:
1. Максимум 10 ітерацій на кожен тип
2. Таймаут запиту 30 секунд
3. Перевірка наявності сигналу (якщо segments_count=0, не міняти t_div)
4. Перевірка валідності measurements

### Коди помилок:
- `"no_signal"` - сигнал не детектується
- `"max_iterations"` - досягнуто ліміт ітерацій
- `"device_error"` - помилка пристрою
- `"invalid_type"` - невідомий тип автоналаштування

---

## Логування

Записувати в лог для кожного auto adjust:
- Початкові значення
- Кінцеві значення
- Кількість ітерацій
- Час виконання
- Fill factor / segments count на кожній ітерації

Приклад:
```
[AUTO] v_div: 200mV -> 500mV (3 iterations, 1.2s)
  iter 1: fill=0.95 -> increase
  iter 2: fill=0.45 -> optimal
```

---

## Приклади використання

### Автомасштабування напруги
```bash
curl -X POST "http://localhost:5000/auto?type=v_div"
```

### Автомасштабування часу
```bash
curl -X POST "http://localhost:5000/auto?type=t_div"
```

### Повне автоналаштування
```bash
curl -X POST "http://localhost:5000/auto?type=v_div,v_offset,trigger,t_div"
```

### Центрування сигналу
```bash
curl -X POST "http://localhost:5000/auto?type=v_offset"
```
