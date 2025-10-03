# Виправлення подвоєної частоти в режимі Peak

## Дата: 2 жовтня 2025 р.

## Проблема
В режимі Peak обчислення частоти показувало **подвоєне значення** (~100 Hz замість ~50 Hz). 
Для всіх інших режимів (Normal, AVG, AVG_HIRES) частота обчислювалась правильно.

## Причина
В режимі Peak дані містять окремі масиви `samples_peak_min` та `samples_peak_max`, які зберігають мінімальні та максимальні значення для кожного семплу.

**Ключова проблема**: В Peak mode пристрій повертає **вдвічі менше семплів** (127 замість 254), оскільки кожен семпл містить мін і макс для певного інтервалу.

Початкова реалізація:
1. Використовувала `peak_min` для сегментації ✅
2. Але не враховувала, що кожен елемент peak_min покриває **подвійний часовий інтервал** ❌
3. Тому частота виходила подвоєною (127 семплів на той самий час, що 254 в NORMAL)

## Рішення
Виправлено функцію `calculate_measurements` в `web_oscill/calculations.py`:

1. Використовувати **peak_min** для сегментації (краще відображає сигнал) ✅
2. **Подвоїти time step** (`t_step_ms * 2`) в Peak mode ✅

Це враховує, що кожен елемент peak_min/peak_max покриває подвійний часовий інтервал.

### Зміни в коді

```python
# In PEAK mode with separate peak_min/peak_max arrays, each array element
# represents 2x time interval (min+max for same period), so we need to
# double the time step to get correct frequency
samples_for_freq = samples
is_peak_mode = bool(peak_min and peak_max)

if is_peak_mode:
    # In Peak mode, peak_min and peak_max have half the samples but each represents
    # the same time interval. We use peak_min for better signal representation,
    # but need to account for the doubled time step
    samples_for_freq = peak_min
    t_step_ms = t_step_ms * 2  # Each peak sample covers 2x time interval

# Use samples for more accurate segment detection
freq_period = calculate_frequency_and_period(samples_for_freq, t_step_ms)
```

### Додатково: Перевірено measurements в /api/frames
`calculate_measurements` правильно викликається в `/api/frames` для всіх фреймів.

## Результати тестування

### Синтетичні тести (test_peak_frequency_fix.py)
```
Normal Mode (no peak data):
   Expected: 100 Hz
   Measured: 101.01 Hz ✅
   Error: 1.01%

Peak Mode (with peak_min and peak_max):
   Expected: 100 Hz
   Measured: 101.01 Hz ✅ (було ~200 Hz до виправлення)
   Error: 1.01%

Comparison:
   Normal mode:  101.01 Hz
   Peak mode:    101.01 Hz
   Difference:   0.00% ✅
```

### Реальний пристрій (test_real_device_frequency.py)
```
До виправлення:
   Normal mode:  50.00 Hz
   Peak mode:    101.59 Hz  ❌ (подвоєння!)
   Ratio: 2.03x

Після виправлення:
   Normal mode:  51.20 Hz
   Average mode: 50.00 Hz
   Peak mode:    50.79 Hz  ✅
   Ratio (PEAK/NORMAL): 0.99x  ✅
```

## Переваги
- ✅ Peak mode тепер показує правильну частоту
- ✅ Результати ідентичні іншим режимам
- ✅ Відповідність Java реалізації
- ✅ Повна зворотна сумісність API

## Змінені файли
- `web_oscill/calculations.py` - виправлення в `calculate_measurements()`
- `scripts/test_peak_frequency_fix.py` - тестовий скрипт
- `docs/peak_frequency_fix.md` - ця документація

## Технічні деталі

### Структура даних Peak Mode
```python
frame = {
    "samples": [128, 130, ...],           # Усереднені значення (опціонально)
    "samples_peak_min": [118, 120, ...],  # Мінімальні значення
    "samples_peak_max": [138, 140, ...],  # Максимальні значення
    "sample_bits": 8
}
```

### Використання даних
- **Напруга (Vpp, Vmax, Vmin)**: використовуються peak_min і peak_max для точних вимірювань
- **Частота та період**: використовується **тільки peak_min** (як в Java) для уникнення подвоєння
- **Інші режими**: використовується основний масив `samples`
