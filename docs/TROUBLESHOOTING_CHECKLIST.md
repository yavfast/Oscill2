# ✅ Швидкий Checklist: Графік не відображається

## Перевірте по черзі:

### 1️⃣ Сервер працює?
```bash
curl -I http://localhost:8000/api/status
```
✅ Має повернути `HTTP/1.1 200 OK`

### 2️⃣ API повертає дані?
```bash
./scripts/diagnose_hex.sh
```
✅ Всі пункти мають бути зелені (✓)

### 3️⃣ Очистіть кеш браузера
- **Windows/Linux**: `Ctrl + F5` або `Ctrl + Shift + R`
- **Mac**: `Cmd + Shift + R`
- **Або**: Відкрийте DevTools (F12) → Network → галочка "Disable cache"

### 4️⃣ Перевірте консоль браузера (F12)
Відкрийте Console tab і подивіться на помилки.

**Має бути**:
```
[API] Decoding 1 hex frames
```

**Не має бути**:
```
❌ TypeError: hexStr.substr is not a function
❌ Failed to decode frame
```

### 5️⃣ Тестова сторінка
Відкрийте: http://localhost:8000/static/test_hex.html

✅ Всі 4 тести мають бути зелені

### 6️⃣ Перевірте Network tab (F12)
- Клацніть Network tab
- Оновіть сторінку (F5)
- Знайдіть запит `/api/frames`
- Перевірте Response → має бути `samples_hex`

### 7️⃣ Якщо все ще не працює - Rollback
Тимчасово вимкніть hex encoding:

У файлі `/web_oscill/static/js/modules/api.js`:
```javascript
constructor() {
  this.useHexFormat = false;  // Змінити true на false
}
```

Збережіть, очистіть кеш, оновіть сторінку.

---

## 🆘 Якщо нічого не допомагає

1. Запустіть повну діагностику:
```bash
./scripts/diagnose_hex.sh > diagnostic_report.txt
```

2. Зберіть Console log з браузера (F12 → Console → Right click → Save as...)

3. Перевірте файл логу:
```bash
tail -100 /hdd/PROJECTS/Oscill2/web_oscill.log
```

4. Перезапустіть сервер:
```bash
pkill -f "uvicorn.*web_oscill.main"
./web_oscill.sh
```

---

**Найчастіша причина**: Кеш браузера  
**Рішення**: Ctrl+F5 або Ctrl+Shift+R
