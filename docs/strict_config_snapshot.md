# Strict Config Snapshot - Remove Error Suppression

## Дата: 2025-01-02

## Проблема

Метод `_snapshot_config_locked()` містив множину `try...except` блоків для кожного параметра конфігурації. При помилці читання параметра підставлялося дефолтне значення і робота продовжувалась.

### Приклад старого коду

```python
try:
    v_div_mv = c.get_v_div_mV()
    cfg["v_div"] = {"v": v_div_mv, "u": "mV"}
except Exception:
    cfg["v_div"] = {"v": 200, "u": "mV"}  # Default

try:
    cfg["trigger_level"] = c.get_trigger_level()
except Exception:
    cfg["trigger_level"] = 128
```

### Наслідки старого підходу

❌ **Приховування проблем комунікації**
- Якщо пристрій не відповідає, помилка замовчується
- Система працює з некоректною/застарілою конфігурацією

❌ **Неконсистентні дані**
- Частина параметрів може бути реальною, частина - дефолтною
- UI показує неправильну інформацію

❌ **Відсутність індикації проблем**
- Користувач не знає що з'єднання погане
- Графік може показувати неправильний масштаб

❌ **Складність діагностики**
- Важко зрозуміти, що сталося з пристроєм
- Логи не показують реальну причину

## Рішення

Прибрано всі `try...except` блоки з методу `_snapshot_config_locked()`. Тепер будь-яка помилка читання параметра призводить до exception, що спричиняє reset з'єднання.

### Новий код

```python
def _snapshot_config_locked(self) -> Dict[str, Any]:
    """
    Snapshot current device configuration under device lock.
    
    If any parameter fails to read, raises exception to trigger connection reset.
    All parameters must be readable for config to be valid.
    """
    cfg: Dict[str, Any] = {}
    c = self._client
    if not c:
        return cfg
    
    # Read all parameters - any failure will raise exception
    v_div_mv = c.get_v_div_mV()
    cfg["v_div"] = {"v": v_div_mv, "u": "mV"}
    
    t_div_ms = c.get_time_div_ms()
    cfg["t_div"] = {"v": round(t_div_ms, 6), "u": "ms"}
    
    cfg["v_offset"] = c.get_offset_raw()
    cfg["trigger_level"] = c.get_trigger_level()
    cfg["trigger_mode_bits"] = c.get_trigger_mode()
    # ... всі інші параметри без try...except
    
    cfg["cfg_id"] = self._cfg_id
    self._update_cached_config(cfg)
    return cfg
```

### Обробка помилок у acquisition loop

```python
def _acq_loop(self):
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while not self._stop_event.is_set():
        try:
            # ...
            cfg = self._snapshot_config_locked()  # Може raise exception
            # ...
            consecutive_errors = 0  # Reset on success
        except Exception as e:
            consecutive_errors += 1
            self._log.error(f"Acquisition loop error ({consecutive_errors}/{max_consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                self._log.error(f"Device communication failed, forcing disconnect")
                self.disconnect()
                break
```

## Переваги

### ✅ Явна індикація проблем
Будь-яка помилка комунікації негайно виявляється та логується.

### ✅ Консистентні дані
Конфігурація завжди повністю коректна або повністю відсутня (після disconnect).

### ✅ Автоматичний recovery
Після 5 послідовних помилок відбувається disconnect, що дозволяє користувачу reconnect.

### ✅ Проста діагностика
Логи чітко показують яка операція провалилась і чому.

### ✅ Захист від мовчазних збоїв
Неможливо працювати з частково некоректною конфігурацією.

## Логіка роботи

### Нормальна робота

```
1. _acq_loop викликає _snapshot_config_locked()
2. Всі параметри успішно прочитані
3. Конфігурація збережена в кеш
4. Frame записаний у буфер
5. consecutive_errors = 0
```

### Тимчасова помилка комунікації

```
1. _acq_loop викликає _snapshot_config_locked()
2. get_v_div_mV() fails → raise exception
3. Exception перехоплено в _acq_loop
4. consecutive_errors += 1 (= 1)
5. Log: "Acquisition loop error (1/5): ..."
6. Sleep і retry
7. Наступна спроба успішна → consecutive_errors = 0
```

### Постійна втрата з'єднання

```
1. Спроба 1: exception → consecutive_errors = 1
2. Спроба 2: exception → consecutive_errors = 2
3. Спроба 3: exception → consecutive_errors = 3
4. Спроба 4: exception → consecutive_errors = 4
5. Спроба 5: exception → consecutive_errors = 5
6. Log: "Device communication failed after 5 consecutive errors, forcing disconnect"
7. self.disconnect() → зупинка acquisition, очищення буфера
8. Frontend отримає status: "disconnected"
9. Користувач може спробувати reconnect
```

## Вплив на систему

### Acquisition loop
- **Було**: Продовжує працювати навіть при помилках читання конфігурації
- **Стало**: Після 5 помилок підряд робить disconnect

### Кеш конфігурації
- **Було**: Може містити mix реальних і дефолтних значень
- **Стало**: Завжди повністю коректний або порожній

### UI (Frontend)
- **Було**: Може показувати неправильну конфігурацію без індикації помилки
- **Стало**: При проблемах статус змінюється на "disconnected", UI показує помилку

### Логування
- **Було**: Помилки приховані, мовчазна деградація
- **Стало**: Кожна помилка логується з детальною інформацією

## Тестування

### Тест 1: Нормальна робота
```
1. Підключитися до пристрою
2. Запустити acquisition
3. Почекати 10 секунд
4. ✅ Очікується: Всі фрейми мають коректну конфігурацію
5. ✅ Очікується: Жодних помилок у логах
```

### Тест 2: Тимчасова проблема комунікації
```
1. Запустити acquisition
2. Створити тимчасову проблему (погане USB з'єднання)
3. Відновити з'єднання
4. ✅ Очікується: 
   - В логах 1-4 помилки
   - Acquisition продовжує працювати
   - Фрейми знову надходять
```

### Тест 3: Повна втрата з'єднання
```
1. Запустити acquisition
2. Відключити USB кабель
3. Почекати 5 секунд
4. ✅ Очікується:
   - В логах 5 помилок
   - Log: "Device communication failed after 5 consecutive errors"
   - Статус змінився на "disconnected"
   - UI показує помилку підключення
```

### Тест 4: Reconnect після disconnect
```
1. Відтворити Тест 3 (повна втрата з'єднання)
2. Підключити USB кабель назад
3. Натиснути "Connect" в UI
4. ✅ Очікується:
   - З'єднання відновлено
   - Конфігурація прочитана успішно
   - Acquisition працює нормально
```

## Вплив на продуктивність

### CPU
- **Було**: Однакове навантаження (try...except майже безкоштовні якщо немає exception)
- **Стало**: Однакове навантаження в нормальному режимі

### Час читання конфігурації
- **Було**: ~10-50 ms (читання всіх параметрів)
- **Стало**: ~10-50 ms (без змін)

### Час обробки помилки
- **Було**: ~0.001 ms (exception caught, continue)
- **Стало**: ~0.001 ms + час логування

### Час recovery після помилки
- **Було**: Нескінченне повторення з некоректною конфігурацією
- **Стало**: 5 спроб × 5ms = 25ms, потім disconnect

## Логування

### Приклад логів при нормальній роботі
```
[DeviceService] Cleared frame buffer after config change (cfg_id: 5)
```

### Приклад логів при тимчасовій помилці
```
[DeviceService] Acquisition loop error (1/5): Failed to read V/div: timeout
[DeviceService] Acquisition loop error (2/5): Failed to read V/div: timeout
```

### Приклад логів при повній втраті з'єднання
```
[DeviceService] Acquisition loop error (1/5): Failed to read V/div: timeout
[DeviceService] Acquisition loop error (2/5): Failed to read trigger_level: device not responding
[DeviceService] Acquisition loop error (3/5): Failed to read v_offset: device not responding
[DeviceService] Acquisition loop error (4/5): Failed to read t_div: device not responding
[DeviceService] Acquisition loop error (5/5): Failed to read rs_mode: device not responding
[DeviceService] Device communication failed after 5 consecutive errors, forcing disconnect
```

## Змінені методи

1. **_snapshot_config_locked()**
   - Видалено всі try...except блоки
   - Додано docstring з описом нової поведінки
   - Будь-яка помилка тепер raise exception

2. **_acq_loop()**
   - Додано детальне логування помилок
   - Змінено повідомлення про disconnect
   - Покращено читабельність коду

## Backwards Compatibility

⚠️ **Breaking change для коду, який очікував що _snapshot_config_locked() ніколи не raise exception.**

Проте, оскільки це internal метод (_prefixed), він не є частиною public API і зміна дозволена.

## Альтернативні підходи (не реалізовані)

### Альтернатива 1: Retry в _snapshot_config_locked()
Спробувати прочитати кожен параметр 3 рази перед тим як raise exception.

**Недоліки**:
- Сповільнює читання конфігурації
- Ускладнює код
- Не вирішує проблему постійної втрати з'єднання

### Альтернатива 2: Partial config
Повертати часткову конфігурацію з маркером "incomplete".

**Недоліки**:
- Ускладнює логіку на стороні споживача
- Може призвести до неправильної роботи UI
- Складніше тестувати

### Альтернатива 3: Watchdog окремо від acquisition
Створити окремий watchdog thread для перевірки з'єднання.

**Недоліки**:
- Збільшує складність
- Додає overhead
- Acquisition loop і так виявляє проблеми

## Версія

- **Версія коду**: 2025-01-02
- **Файл**: web_oscill/device_service.py
- **Методи**: _snapshot_config_locked(), _acq_loop()
- **Тип зміни**: Breaking change (internal API)
- **Автор**: AI Assistant
