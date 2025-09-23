# Web-версія Oscill2: архітектура та технічний опис

Мета: надати вебзастосунок для роботи з пристроєм Oscill через протокол OBEX:
- Backend (Python): драйвер/клієнт OBEX для обміну з пристроєм, REST/WS API.
- Frontend (Web): відображення осцилограм у браузері з елементами керування як у осцилографі.

Документація протоколу: див. docs/protocol/protocol.md (імена властивостей/регістрів/команд і кодування ідентичні Oscill.java).

## 1. Архітектура системи

Компоненти:
- Device Connector (Python)
  - Реалізація OBEX поверх послідовного транспорту (pyserial/pyserial-asyncio).
  - Підтримка розширених заголовків 0x70/0x71/0x72/0x49/0xB0/0xF0/0xF1.
  - Клас OscillClient з інтерфейсом, сумісним з Oscill.java (імена регістрів/властивостей).
- Backend API (Python, FastAPI)
  - REST: підключення, читання властивостей/регістрів, запис регістрів, команди “C”/“D”, швидкість.
  - WebSocket: потокова передача вибірок (паралельний/ROLL), події стану.
  - Менеджер сесій: ексклюзивний доступ до пристрою, черги, блокування, таймаути.
- Acquisition Pipeline
  - Цикли оцифровки, обробка Continue, буферизація (кільцева черга), прорідження/агрегація для відображення.
- Frontend (SPA: React/Vue)
  - Полотно відображення (Canvas/WebGL) з курсорами/масштабуванням/панорамуванням.
  - Панелі керування: розгортка (TS/RS/QS/TC/TD), канал (O1/V1/P1/M1), тригер (RT/TA/TW/T1/S1), команди, з’єднання.
  - Стани та телеметрія: статус пристрою, помилки, затримки, FPS.

Потік даних:
Browser UI ←(WS/JSON або WS/Binary)— Backend ←(OBEX)— Oscill.

## 2. Backend: дизайн і реалізація

Технології:
- Python 3.11+, FastAPI, Uvicorn.
- pyserial (або pyserial-asyncio) для RS232/USB CDC.
- starlette.websockets для WS.
- optional: NumPy для обробки/децимації; orjson/uvicorn[standard] для продуктивності.

Слой драйвера (oscill/driver.py):
- Session: керує OBEX Connect/Disconnect, 0x91 (Oscill_speed), 0x92 (resend), Abort.
- Headers/encoding: big-endian, 0xF0 (2B-as-4B), 0xF1 (4B), 0xB1 (1B), 0xB0 (checksum, опційно).
- Властивості: GET з 0x70="NAME".
- Регістри: GET/PUT з 0x71="NAME" + значення у 0xB1/0xF0/0xF1; повертати фактичні значення з Response.
- Команди:
  - “C” (PUT 0x72="C").
  - “D” (GET 0x72="D") — прийом 0x49 з Success/Continue, разбирання атрибутів і масивів.
- Обробка помилок: 0xD0 (повтор запиту один раз), 0x92 (resend), таймаути лінку, backoff.

Менеджер пристрою (oscill/manager.py):
- Singleton DeviceManager або пул (якщо кілька девайсів).
- Стани: disconnected/connecting/connected/busy/roll.
- Блокування: один клієнт володіє пристроєм (lease з таймаутом/heartbeats).
- Кільцевий буфер для ROLL/паралельної передачі, backpressure для WS клієнтів.

Обробка оцифровки:
- Single-shot: виклик “D”, чекання Success з 0x49, повернення JSON/бінарних масивів.
- ROLL/паралельна: фоновий таск читає Continue до зупинки або Abort; транслює кадри у WS.

API-шари (FastAPI):
- Валідація через Pydantic схемами; типи узгоджені з протоколом (uint8/uint16/uint32, int16).
- Централізована обробка помилок (HTTPException + код/повідомлення протоколу).

## 3. API специфікація

Базовий шлях: /api

Сесія:
- POST /api/connect { port, baud? } → { status, hw, sw, vnm, vsn }
- POST /api/disconnect → { status }
- POST /api/speed { coef:uint8 } → { speed_bps:int }

Властивості/регістри:
- GET /api/properties → { name:value, … } (параметр names[] підтримується)
- GET /api/registers → { name:value, … } (параметр names[])
- PUT /api/registers/{name} { value } → { name, value_actual }
  - value кодується відповідно до розміру: 1/2/4 байти; для signed int16 значення -32768..32767.
- GET /api/limits → агреговані межі: { TOl, TMl/TMh, TPl, QSh, TCh, TDl/TDh, V1l/V1h, P1l/P1h, … }

Команди:
- POST /api/commands/calibrate → 202 Accepted | 200 OK
- POST /api/commands/acquire { mode:"single"|"roll", channels:[1], rs, ts, qs, tc?, td?, m1?, ap?, ar?, rt?, ta?, tw? } → 
  - single: 200 { meta, channels:[{ attrs, bytes_per_sample, samples:Array|base64 }] }
  - roll: 202 { stream:"/ws/acquire" }

Потоки (WebSocket):
- WS /ws/acquire?ch=[1]&viewport=px&strategy=minmax|mean&fps=60
  - Сервер надсилає кадри:
    {
      "ts": <ms>,
      "attrs": { mode, parallel, roll, trig, channels },
      "ch1": { "bps": 1|2, "count": N, "format": "i8|i16|u8", "data": <binary|base64>, "gain": V1, "offset": P1 },
      "timebase": { "TS": <uint32>, "TC": <uint16>, "TD": <uint32> }
    }
  - Бінарний режим WS (permessage-deflate) бажаний; JSON+base64 — fallback.

Помилки:
- 408 LinkTimeout, 422 ValidationError, 424 DeviceBusy, 502 ObexError(code=0xD0/…).
- Тіло помилки: { code, message, details? }.

## 4. Frontend: дизайн

Технології:
- SPA (React + Vite або Vue 3 + Vite).
- Стейт-менеджмент (Redux Toolkit / Pinia).
- Canvas 2D (швидкий старт) або WebGL (при високій частоті кадрів).
- WebSocket для потоків, REST для налаштувань.

Компоненти:
- ConnectionPanel: вибір порта/швидкості, статус.
- TimebaseControls: TS, RS, QS, TC, TD, режими (single/auto/normal/roll).
- ChannelControls (CH1): O1 (вкл/земля/фільтри), V1 (чутливість), P1 (зміщення), M1 (режим).
- TriggerControls: RT/TA/TW, T1 (фронт/спад/гістерезис/ВЧ/НЧ), S1 (рівень).
- AcquisitionControls: Start/Stop, Single, Calibrate, Measure.
- WaveformView: масштабування колесом, панорамування, два курсори ΔT/ΔV, маркери тригера/центру.
- MeasurementsPanel: RMS/Max/Min/Avg/Period/Frequency (локально над видимою частиною або сервером).

Візуалізація:
- Вхідні дані 1 або 2 байти/вибірку.
- Серверне прорідження:
  - min/max агрегування по колонах пікселів (зберігає піки).
  - mean для усередненого режиму.
- Кадрування ~30–60 FPS; адаптивний FPS при слабкому CPU/мережі.

UX-деталі:
- Валідація діапазонів за властивостями (QSh, P1h/P1l, V1h/V1l, TDl/TDh).
- Після запису регістра — читання фактичного значення (відображати реальний стан).
- Негайна індикація режимів (realtime/стробо/паралельна/ROLL).

## 5. Відповідність протоколу

- Імена: 0x70 property, 0x71 register, 0x72 command (“C”/“D”), 0x49 body — строго як у docs/protocol/protocol.md.
- Кодування: big-endian; 0xF0 — 2 байти передані як 4; 0xF1 — 4 байти; 0xB1 — 1 байт; знакові 2 байти — two’s complement.
- Швидкість: 0x91 (speed=1842000/coef), повтор Response: 0x92.
- Помилки: 0xD0 при спотворенні request; допустимий одноразовий повтор.

## 6. Дані та моделі

Pydantic-схеми:
- PropertyValue { name:str, type:"u8|u16|u32|i16|ascii4", value:int|str }
- RegisterValue { name:str, type:… , requested?:int|str, actual:int|str }
- AcquisitionMeta { mode, parallel, roll, trig, channels, TS, QS, TC, TD, bytes_per_sample }
- AcquisitionFrame { meta:AcquisitionMeta, ch1:{ bps, count, format, data } }

Внутрішні структури:
- FrameBuffer (кільцева), з backpressure (скидання найстаріших).
- Downsampler(strategy: minmax|mean, viewport_px).

## 7. Конкурентність і продуктивність

- Один потік/таск на виділене послідовне з’єднання.
- Асинхронна обробка OBEX: читання → парсинг заголовків → перевірка checksum → публікація в чергу.
- Відокремити I/O (async) від CPU (децимація) — через asyncio.Queue / ThreadPoolExecutor.
- Ліміти:
  - ROLL: обмежити кадр N≈2–8k вибірок/канал, 20–60 FPS.
  - Динамічне зменшення QS або підвищення TS при нестачі пропускної здатності.
- Стиснення WS (permessage-deflate), gzip для REST single-shot.

## 8. Безпека, розгортання, DevOps

- CORS з білим списком походжень.
- Auth: токен (Bearer) або API key; RBAC (операції керування тільки авторизованим).
- TLS через реверс-проксі (Nginx/Traefik).
- Логи: структуровані (JSON), рівні (DEBUG/INFO/WARN/ERROR), трасування пакетів (за потреби).
- Docker:
  - backend (uvicorn), frontend (статичний бандл), nginx.
  - docker-compose.yml з томом для конфігурацій.
- Моніторинг: Prometheus метрики (латентності, FPS, drop rate), Sentry для помилок.

## 9. Тестування

- Емулятор пристрою:
  - Сервер-обробник OBEX-пакетів зі скриптованими відповідями (Success/Continue/No Content/Error).
  - Запис/відтворення сесій з реального пристрою.
- Unit-тести:
  - Кодування/декодування 0xB1/0xF0/0xF1, checksum 0xB0.
  - Парсинг 0x49 (атрибути та масиви).
- Інтеграційні:
  - Повні потоки: Connect → Get(VNM/…) → Put(MC/TS/…) → Get(“D”).
  - ROLL: Continue-ланцюжок, Abort, відновлення.
- E2E (Playwright/Cypress): керування з UI, перевірка хвильових форм.

## 10. Типові потоки

Single-shot:
1) POST /api/connect
2) PUT /api/registers/MC, TS, RS, M1, QS, TC/TD, RT (+TA/TW)
3) POST /api/commands/acquire { mode:"single" }
4) Отримати масиви; відобразити; курсори/вимірювання.

ROLL:
1) Налаштування як вище; RS з біт2=1 (ROLL або паралельна)
2) POST /api/commands/acquire { mode:"roll" }
3) Під’єднатися до /ws/acquire; отримувати кадри до зупинки
4) Зупинка: Abort (від менеджера) або розрив WS.

Калібрування:
- POST /api/commands/calibrate → оновити межі (V1h/V1l, P1h/P1l), відобразити реальні значення.

## 11. Розширення

- Підтримка кількох каналів (CH2..CH4), якщо апаратно доступно.
- Збереження трейсів (CSV/JSON/RAW), скріншоти.
- Автопідбір тригера/масштабу.
- Математичні канали (CH_MATH), FFT.
- Потік запису на диск у ROLL.

Джерело істини для імен і форматів — Oscill.java і docs/protocol/protocol.md.
