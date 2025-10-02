# API Changes - ensure_connected and renamed methods

## Нові та оновлені методи

### 1. `ensure_connected(port=None, baud=115200)` - НОВИЙ
Розумний метод підключення, який:
- Перевіряє, чи вже підключено пристрій
- Якщо підключено - повертає поточний статус (дуже швидко)
- Якщо не підключено - автоматично підключається
- Безпечно обробляє помилки підключення

**Використання:**
```python
# Просто переконайтеся, що підключено
status = service.ensure_connected()

# Або вкажіть порт вручну
status = service.ensure_connected(port="/dev/ttyUSB0")
```

**API Endpoint:**
```
POST /api/connect
```
(без параметрів для auto-connect, або з `port` та `baud` для явного підключення)

**Приклад відповіді (підключено):**
```json
{
  "status": "ok",
  "config": {...},
  "cfg_id": 0,
  "is_connected": true,
  "is_acquiring": true
}
```

**Приклад відповіді (не вдалося підключити):**
```json
{
  "status": "disconnected",
  "is_connected": false,
  "is_acquiring": false,
  "error": "Device not found"
}
```

### 2. `start()` - перейменовано з `start_acquisition()`
Коротша та зрозуміліша назва для запуску збору даних.

**Використання:**
```python
service.start()
```

**API Endpoint:**
```
POST /api/start
```

### 3. `stop()` - перейменовано з `stop_acquisition()`
Коротша та зрозуміліша назва для зупинки збору даних.

**Використання:**
```python
service.stop()
```

**API Endpoint:**
```
POST /api/stop
```

## Типові сценарії використання

### Сценарій 1: Веб-додаток запускається
```python
# При старті додатку
status = service.ensure_connected()
if status['status'] == 'ok':
    print("Ready to use")
else:
    print(f"Device not available: {status.get('error')}")
```

### Сценарій 2: Користувач хоче почати вимірювання
```python
# Переконайтеся, що підключено
service.ensure_connected()

# Почніть збір даних
service.start()

# ... збір даних ...

# Зупиніть збір даних
service.stop()
```

### Сценарій 3: Перевірка з'єднання перед операцією
```python
# Швидка перевірка (не блокує, якщо вже підключено)
status = service.ensure_connected()

if status['status'] == 'ok':
    # Виконуємо операцію
    service.apply_config({'v_div': {'v': 500, 'u': 'mV'}})
```

## Переваги нових методів

1. **ensure_connected()**:
   - Спрощує логіку підключення
   - Автоматично обробляє стан з'єднання
   - Швидкий, якщо вже підключено (< 0.01 мс)
   - Безпечний fallback при помилках

2. **start() / stop()**:
   - Коротші та зрозуміліші назви
   - Легше читаються у коді
   - Відповідають звичайним патернам API

## REST API приклади

### Підключення при потребі (auto-connect)
```bash
curl -X POST http://localhost:8000/api/connect -H "Content-Type: application/json" -d '{}'
```

### Підключення до конкретного порту
```bash
curl -X POST http://localhost:8000/api/connect \
  -H "Content-Type: application/json" \
  -d '{"port": "/dev/ttyUSB0", "baud": 115200}'
```

### Запуск збору даних
```bash
curl -X POST http://localhost:8000/api/start
```

### Зупинка збору даних
```bash
curl -X POST http://localhost:8000/api/stop
```

## Примітки

- `ensure_connected()` **не викликає повторне підключення**, якщо вже підключено
- Якщо підключення не вдається, повертається статус з помилкою (не викидається exception)
- Методи `start()` та `stop()` - лаконічні та зрозумілі назви для керування збором даних
