# Oscill2 Web API Reference

## Нові та спрощені endpoints (v2)

### Підключення

#### `POST /api/connect`
Підключення до пристрою або перевірка підключення.

**Варіанти використання:**

1. **Auto-connect** (автоматичне виявлення):
```bash
curl -X POST http://localhost:8000/api/connect \
  -H "Content-Type: application/json" \
  -d '{}'
```

2. **Explicit connect** (явне підключення до порту):
```bash
curl -X POST http://localhost:8000/api/connect \
  -H "Content-Type: application/json" \
  -d '{"port": "/dev/ttyUSB0", "baud": 115200}'
```

**Параметри запиту:**
```json
{
  "port": "string | null",  // Порт (null або відсутній = auto-detect)
  "baud": 115200            // Швидкість (опціонально, за замовчуванням 115200)
}
```

**Відповідь (успіх):**
```json
{
  "status": "ok",
  "port": "/dev/ttyUSB0",
  "config": {...},
  "cfg_id": 0,
  "is_connected": true,
  "is_acquiring": true
}
```

**Відповідь (вже підключено):**
```json
{
  "status": "ok",
  "config": {...},
  "cfg_id": 0,
  "is_connected": true,
  "is_acquiring": true
}
```

**Відповідь (помилка):**
```json
{
  "detail": "Device not found"
}
```

---

#### `POST /api/disconnect`
Відключення від пристрою.

```bash
curl -X POST http://localhost:8000/api/disconnect
```

**Відповідь:**
```json
{
  "status": "ok"
}
```

---

### Керування збором даних

#### `POST /api/start`
Запуск збору даних.

```bash
curl -X POST http://localhost:8000/api/start
```

**Відповідь:**
```json
{
  "status": "ok"
}
```

---

#### `POST /api/stop`
Зупинка збору даних.

```bash
curl -X POST http://localhost:8000/api/stop
```

**Відповідь:**
```json
{
  "status": "ok"
}
```

---

### Отримання інформації

#### `GET /api/status`
Отримання поточного статусу (швидко, з кешу).

```bash
curl -X GET http://localhost:8000/api/status
```

**Відповідь (підключено):**
```json
{
  "status": "ok",
  "config": {
    "v_div": {"v": 200, "u": "mV"},
    "t_div": {"v": 5.0, "u": "ms"},
    "v_offset": 128,
    "trigger_level": 128,
    "trigger_mode": {"v": 44, "u": "bits"},
    "trigger_slope": "Rising",
    "coupling": "DC",
    "filters": {"high": false, "low": false},
    "sw_mode": "NORMAL",
    "sync_type": "AUTO",
    "cfg_id": 0,
    ...
  },
  "cfg_id": 0,
  "is_connected": true,
  "is_acquiring": true
}
```

**Відповідь (відключено):**
```json
{
  "status": "disconnected",
  "is_connected": false,
  "is_acquiring": false
}
```

---

#### `GET /api/frames?since=0&limit=128&format=hex`
Отримання фреймів з буфера.

**Параметри:**
- `since` (опціонально): Повернути фрейми з seq > since
- `limit` (опціонально): Максимальна кількість фреймів (за замовчуванням 128)
- `format` (опціонально): "hex" (компактно) або "array" (за замовчуванням "hex")

```bash
curl -X GET "http://localhost:8000/api/frames?since=0&limit=10&format=hex"
```

**Відповідь:**
```json
{
  "config": {...},
  "frames": [
    {
      "seq": 1,
      "time": 1696251234.567,
      "cfg_id": 0,
      "channels": 1,
      "samples_hex": "80817f7e...",
      "samples_peak_min_hex": "7f7e7d...",
      "samples_peak_max_hex": "81828384...",
      "measurements": {
        "freq": {"v": 1000.0, "u": "Hz"},
        "period": {"v": 0.001, "u": "s"},
        "v_pp": {"v": 0.5, "u": "V"},
        "v_max": {"v": 0.25, "u": "V"},
        "v_min": {"v": -0.25, "u": "V"},
        "v_avg": {"v": 0.0, "u": "V"}
      }
    },
    ...
  ],
  "newest_seq": 1234,
  "format": "hex"
}
```

---

### Конфігурація

#### `POST /api/config`
Зміна конфігурації пристрою.

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "v_div": {"v": 500, "u": "mV"},
    "t_div": {"v": 10, "u": "ms"},
    "trigger_level": 128,
    "trigger_slope": "Rising",
    "coupling": "DC"
  }'
```

**Параметри запиту:**
```json
{
  "v_div": {"v": number, "u": "mV|V"},           // Вертикальна чутливість
  "t_div": {"v": number, "u": "ms|us|s"},        // Горизонтальна розгортка
  "v_offset": number | {"v": number},            // Вертикальне зміщення (0-255)
  "t_offset": number | {"v": number, "u": "samples"},  // Горизонтальне зміщення
  "trigger_level": number,                       // Рівень тригера (0-255)
  "trigger_mode": "Auto|Normal|Single",          // Режим тригера
  "trigger_slope": "Rising|Falling|Both|None",   // Фронт тригера
  "coupling": "DC|AC|GND",                       // Тип входу
  "filter_high": boolean,                        // Високочастотний фільтр
  "filter_low": boolean,                         // Низькочастотний фільтр
  "sw_mode": "NORMAL|AVG|AVG_HIRES|PEAK|PEAK_HI", // Режим обробки
  "sync_type": "AUTO|WAIT_TIMEOUT|FREE|WAIT",    // Тип синхронізації
  "sync_front": boolean,                         // Синхронізація по передньому фронту
  "sync_back": boolean                           // Синхронізація по задньому фронту
}
```

**Відповідь:**
```json
{
  "status": "ok",
  "config": {...},
  "cfg_id": 1,
  "warnings": []
}
```

---

---

## Типовий сценарій використання

```bash
# 1. Підключитися (auto-detect)
curl -X POST http://localhost:8000/api/connect -d '{}'

# 2. Перевірити статус
curl -X GET http://localhost:8000/api/status

# 3. Налаштувати параметри
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"v_div": {"v": 500, "u": "mV"}, "t_div": {"v": 10, "u": "ms"}}'

# 4. Запустити збір
curl -X POST http://localhost:8000/api/start

# 5. Отримати дані
curl -X GET "http://localhost:8000/api/frames?limit=10"

# 6. Зупинити збір
curl -X POST http://localhost:8000/api/stop

# 7. Відключитися
curl -X POST http://localhost:8000/api/disconnect
```

---

## Особливості

- **Швидкість**: `GET /api/status` виконується < 0.001с (читає з кешу)
- **Таймаути**: Всі операції з пристроєм мають таймаут 5 секунд
- **Thread-safe**: Всі endpoints можна викликати паралельно
- **Автопідключення**: `POST /api/connect` без параметрів автоматично знаходить пристрій
