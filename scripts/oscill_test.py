#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
oscill_test.py — послідовний автотест базових функцій пристрою Oscill:
 1) Підключення до пристрою (auto або заданий порт)
 2) Ініціалізація базових параметрів (узято з Android/Java коду)
 3) Перебір усіх значень V/div
 4) Перебір усіх значень t/div
 5) Перевірка параметрів тригера (режими + рівні)
 6) Перевірка параметрів offset (зміщення по напрузі)
 7) Повернення до базових параметрів

Після кожної зміни параметра виконується один запит даних осцилограми.
У консоль виводяться параметри тесту та його результат.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Iterable, Optional, Tuple

# Додати корінь проєкту до PYTHONPATH, щоб імпорт працював при запуску зі scripts/
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from web_oscill.oscill_client import OscillClient
except Exception as e:  # pragma: no cover
    print("Помилка імпорту OscillClient з web_oscill.oscill_client: ", e)
    sys.exit(2)


# Значення з Android/Java коду
# V/div (Sensitivity.java)
V_DIV_MV_VALUES = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000]

# t/div (SamplingTime.java), у секундах
T_DIV_S_VALUES = [
    100e-9, 200e-9, 500e-9,
    1e-6, 2e-6, 5e-6,
    10e-6, 20e-6, 50e-6,
    100e-6, 200e-6, 500e-6,
    1e-3, 2e-3, 5e-3,
    10e-3, 20e-3, 50e-3,
    100e-3, 200e-3, 500e-3,
]


# Базові параметри (див. MainActivity.onOscillConnected)
BASE_V_DIV_MV = 200           # 200 mV/div
BASE_T_DIV_MS = 5             # 5 ms/div
BASE_OFFSET_V = 0.0           # 0 В
BASE_TRIGGER_LEVEL = 128      # 0..255
# Режим тригера (T1) з Java: фронт + гістерезис фронту, без спаду, без LFSync
# bits: [7..0] = 0 0 1 0 1 1 0 0  => 0x2C
BASE_TRIGGER_MODE = 0x2C


def scale_samples_to_mv(samples: Iterable[int], v_div_mv: Optional[int]) -> Tuple[Optional[float], Optional[float]]:
    """Повертає min/max у mV для сирих семплів, якщо відома чутливість.
    Формула узята з web_oscill.main: full_scale_mv = v_div_mv * 8.
    """
    try:
        if v_div_mv is None:
            return None, None
        samples = list(samples)
        if not samples:
            return None, None
        full_scale_mv = float(v_div_mv) * 8.0
        center = 127.5
        vals = [((s - center) / 256.0) * full_scale_mv for s in samples]
        return (min(vals), max(vals))
    except Exception:
        return None, None


def acquire_once(client: OscillClient, note: str = "", settle_ms: int = 80, optional: bool = False) -> None:
    """Запитати один кадр та вивести короткий звіт.
    Якщо optional=True, відсутність даних або помилка читання не вважається збоєм
    (корисно для тестів тригера без підключеного сигналу).
    """
    try:
        if settle_ms > 0:
            time.sleep(settle_ms / 1000.0)
        frame = client.get_frame()
        v_div_mv = client.get_v_div_mV()
        t_div_ms = client.get_time_div_ms()
        if frame is None:
            msg = f"даних немає (frame=None)" if optional else f"Немає даних (frame=None)"
            print(f"  → [{note}] {msg}; V/div={v_div_mv} mV, T/div={t_div_ms:.9f} ms")
            return
        samples = frame.get("samples", [])
        ch = frame.get("channels", 1)
        mn, mx = scale_samples_to_mv(samples, v_div_mv)
        if mn is not None and mx is not None:
            print(f"  → [{note}] OK: канали={ch}, семплів={len(samples)}, "
                  f"V/div={v_div_mv} mV, T/div={t_div_ms:.9f} ms, min={mn:.2f} mV, max={mx:.2f} mV")
        else:
            print(f"  → [{note}] OK: канали={ch}, семплів={len(samples)}, "
                  f"V/div={v_div_mv} mV, T/div={t_div_ms:.9f} ms")
    except Exception as e:
        if optional:
            print(f"  → [{note}] Зчитування пропущено (параметр перевірено): {e}")
        else:
            print(f"  → [{note}] ПОМИЛКА при зчитуванні: {e}")


def apply_base_config(client: OscillClient) -> None:
    """Встановити базові параметри та виконати один запит даних."""
    print("[БАЗОВА ІНІЦІАЛІЗАЦІЯ]")
    # Порядок як у Java (наскільки це можливо на Python бо не всі регістри експоновані):
    client.set_v_div_mV(BASE_V_DIV_MV)
    _verify_v_div(client, BASE_V_DIV_MV)

    client.set_offset_volts(BASE_OFFSET_V)
    _verify_offset(client, BASE_OFFSET_V)

    client.set_trigger_mode(BASE_TRIGGER_MODE)
    _verify_trigger_mode(client, BASE_TRIGGER_MODE)

    client.set_trigger_level(BASE_TRIGGER_LEVEL)
    _verify_trigger_level(client, BASE_TRIGGER_LEVEL)

    client.set_time_div_ms(BASE_T_DIV_MS)
    _verify_t_div_ms(client, BASE_T_DIV_MS)

    # Нормальний режим передачі/оцифровки
    try:
        client.set_rs_mode(0)
    except Exception:
        pass

    client.ensure_qs()
    acquire_once(client, note="base")


def test_all_v_div(client: OscillClient) -> None:
    print("\n[ТЕСТ V/div]")
    for mv in V_DIV_MV_VALUES:
        try:
            client.set_v_div_mV(mv)
            # Після зміни чутливості краще повернути offset у 0 В
            client.set_offset_volts(0.0)
            client.ensure_qs()
            _verify_v_div(client, mv)
            _verify_offset(client, 0.0)
            acquire_once(client, note=f"V/div={mv} mV")
        except Exception as e:
            print(f"  → [V/div={mv} mV] ПОМИЛКА встановлення: {e}")


def test_all_t_div(client: OscillClient) -> None:
    print("\n[ТЕСТ T/div]")
    for t_s in T_DIV_S_VALUES:
        t_ms = t_s * 1000
        try:
            client.set_time_div_ms(t_ms)
            # Для повільних розгорток скоротимо обсяг даних та увімкнемо паралельну передачу
            # щоб уникнути таймаутів відповіді.
            qs = 254
            rs = 0
            if t_s >= 0.5:
                qs = 16
                rs = 0b00000010  # parallel
            elif t_s >= 0.2:
                qs = 32
                rs = 0b00000010
            elif t_s >= 0.1:
                qs = 64
                rs = 0b00000010
            client.ensure_qs(qs)
            if rs:
                try:
                    client.set_rs_mode(rs)
                except Exception:
                    pass
            _verify_t_div_ms(client, t_ms)
            acquire_once(client, note=f"T/div={t_ms:g} ms")
        except Exception as e:
            print(f"  → [T/div={t_s:g} s] ПОМИЛКА встановлення: {e}")
    # Повернути RS у звичайний режим після тестів часу/діл
    try:
        client.set_rs_mode(0)
    except Exception:
        pass


def test_trigger(client: OscillClient) -> None:
    print("\n[ТЕСТ ТРИГЕРА]")
    # Набір декількох режимів (T1)
    modes = [
        (0x2C, "front+hyst"),        # базовий з Java
        (0x24, "front"),             # фронт без гістерезису
        (0x13, "back+hyst"),         # спад з гістерезисом
        (0x3F, "front+back+hyst"),   # фронт+спад, обидва з гістерезисом
    ]
    levels = [64, 128, 192]

    for mode, label in modes:
        try:
            client.set_trigger_mode(mode)
            client.ensure_qs()
            _verify_trigger_mode(client, mode)
            # При відсутності сигналу можливе очікування тригера → acquisition робимо опційно
            acquire_once(client, note=f"T1=0x{mode:02X} ({label})", optional=True)
        except Exception as e:
            print(f"  → [T1=0x{mode:02X}] ПОМИЛКА встановлення режиму: {e}")

        for lvl in levels:
            try:
                client.set_trigger_level(lvl)
                _verify_trigger_level(client, lvl)
                acquire_once(client, note=f"T1=0x{mode:02X}, level={lvl}", optional=True)
            except Exception as e:
                print(f"  → [level={lvl}] ПОМИЛКА встановлення рівня: {e}")


def test_offset(client: OscillClient) -> None:
    print("\n[ТЕСТ OFFSET (зміщення по напрузі)]")
    try:
        v_div_mv = client.get_v_div_mV()
        if not v_div_mv:
            v_div_mv = BASE_V_DIV_MV
    except Exception:
        v_div_mv = BASE_V_DIV_MV

    # В діапазоні ~±2*V/div — безпечно для більшості конфігурацій
    steps_v = [
        -2.0 * (v_div_mv / 1000.0),
        -1.0 * (v_div_mv / 1000.0),
        0.0,
        +1.0 * (v_div_mv / 1000.0),
        +2.0 * (v_div_mv / 1000.0),
    ]

    for offs_v in steps_v:
        try:
            client.set_offset_volts(offs_v)
            _verify_offset(client, offs_v)
            acquire_once(client, note=f"offset={offs_v:+.3f} V")
        except Exception as e:
            print(f"  → [offset={offs_v:+.3f} V] ПОМИЛКА встановлення: {e}")


def reset_to_base(client: OscillClient) -> None:
    print("\n[СКИДАННЯ ДО БАЗОВИХ ПАРАМЕТРІВ]")
    try:
        client.set_v_div_mV(BASE_V_DIV_MV); _verify_v_div(client, BASE_V_DIV_MV)
        client.set_time_div_ms(BASE_T_DIV_MS); _verify_t_div_ms(client, BASE_T_DIV_MS)
        client.set_offset_volts(BASE_OFFSET_V); _verify_offset(client, BASE_OFFSET_V)
        client.set_trigger_mode(BASE_TRIGGER_MODE); _verify_trigger_mode(client, BASE_TRIGGER_MODE)
        client.set_trigger_level(BASE_TRIGGER_LEVEL); _verify_trigger_level(client, BASE_TRIGGER_LEVEL)
        try:
            client.set_rs_mode(0)
        except Exception:
            pass
        client.ensure_qs()
        acquire_once(client, note="reset->base")
    except Exception as e:
        print("  → ПОМИЛКА скидання до базових параметрів:", e)


# ---------- Перевірки (read-back & assert) ----------

def _verify_v_div(client: OscillClient, expected_mv: int) -> None:
    try:
        got = int(client.get_v_div_mV())
        if got == int(expected_mv):
            print(f"  ✓ Перевірка V/div: встановлено {expected_mv} mV/div — OK")
        else:
            print(f"  ✗ Перевірка V/div: очікувалось {expected_mv} mV/div, отримано {got} mV/div — FAIL")
    except Exception as e:
        print(f"  ✗ Перевірка V/div: помилка читання — {e}")


def _verify_t_div_ms(client: OscillClient, expected_ms: float, rel_tol: float = 0.02, abs_tol: float = 1e-6) -> None:
    """Перевірка T/div з допусками (квантування по тактам)."""
    try:
        got = float(client.get_time_div_ms())
        if _is_close(got, expected_ms, rel_tol, abs_tol):
            print(f"  ✓ Перевірка T/div: встановлено ~{expected_ms:g} ms — OK (прочитано {got:g} ms)")
        else:
            print(f"  ✗ Перевірка T/div: очікувалось ~{expected_ms:g} ms, отримано {got:g} ms — FAIL")
    except Exception as e:
        print(f"  ✗ Перевірка T/div: помилка читання — {e}")


def _verify_trigger_mode(client: OscillClient, expected_bits: int) -> None:
    try:
        got = int(client.get_trigger_mode())
        if got == int(expected_bits):
            print(f"  ✓ Перевірка T1: 0x{expected_bits:02X} — OK")
        else:
            print(f"  ✗ Перевірка T1: очікувалось 0x{expected_bits:02X}, отримано 0x{got:02X} — FAIL")
    except Exception as e:
        print(f"  ✗ Перевірка T1: помилка читання — {e}")


def _verify_trigger_level(client: OscillClient, expected_lvl: int) -> None:
    try:
        got = int(client.get_trigger_level())
        if got == int(expected_lvl):
            print(f"  ✓ Перевірка S1 (level): {expected_lvl} — OK")
        else:
            print(f"  ✗ Перевірка S1 (level): очікувалось {expected_lvl}, отримано {got} — FAIL")
    except Exception as e:
        print(f"  ✗ Перевірка S1: помилка читання — {e}")


def _verify_offset(client: OscillClient, expected_v: float) -> None:
    """Перевірка offset з урахуванням кроку квантування (залежить від V/div)."""
    try:
        sens_mv = client.get_v_div_mV() or BASE_V_DIV_MV
        step_v = (sens_mv * 8.0 / 256.0) / 1000.0  # В на 1 лсб P1
        got = float(client.get_offset_volts())
        if abs(got - expected_v) <= (step_v + 1e-6):
            print(f"  ✓ Перевірка Offset: ~{expected_v:+.3f} V — OK (крок {step_v:.4f} В, прочитано {got:+.3f} V)")
        else:
            print(f"  ✗ Перевірка Offset: очікувалось ~{expected_v:+.3f} V, отримано {got:+.3f} V (крок {step_v:.4f} В) — FAIL")
    except Exception as e:
        print(f"  ✗ Перевірка Offset: помилка читання — {e}")


def _is_close(a: float, b: float, rel_tol: float, abs_tol: float) -> bool:
    return abs(a - b) <= max(abs_tol, rel_tol * max(abs(a), abs(b)))


def connect_client(port: Optional[str], baud: int, timeout: float = 2.0) -> OscillClient:
    auto = port in (None, "", "auto")
    if auto:
        port = OscillClient.auto_find_port()
        if not port:
            raise RuntimeError("Пристрій не знайдено (auto). Вкажіть порт через --port")
    client = OscillClient(port, baud=baud, timeout=timeout)
    client.open()
    # М’який reset (як у Java) і OBEX CONNECT
    client.reset()
    client.connect()
    return client


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Автотест базових функцій пристрою Oscill")
    parser.add_argument("--port", default="auto", help="Послідовний порт (наприклад, /dev/ttyUSB0) або 'auto'")
    parser.add_argument("--baud", type=int, default=115200, help="Швидкість порту, бод")
    parser.add_argument("--skip", choices=["none","vdiv","tdiv","trig","offset"], default="none",
                        help="Пропустити розділ тесту")
    args = parser.parse_args(list(argv) if argv is not None else None)

    print("[З’ЄДНАННЯ]")
    print(f"Порт: {args.port}, baud={args.baud}")
    try:
        client = connect_client(args.port, args.baud)
    except Exception as e:
        print("ПОМИЛКА підключення:", e)
        return 1

    try:
        apply_base_config(client)
        if args.skip not in ("vdiv",):
            test_all_v_div(client)
        else:
            print("[V/div] — пропущено")

        if args.skip not in ("tdiv",):
            test_all_t_div(client)
        else:
            print("[T/div] — пропущено")

        # Повернемось до базових V/T перед наступними розділами
        reset_to_base(client)

        if args.skip not in ("trig",):
            test_trigger(client)
        else:
            print("[Trigger] — пропущено")

        if args.skip not in ("offset",):
            test_offset(client)
        else:
            print("[Offset] — пропущено")

        # Завершення — повернутися до базових значень
        reset_to_base(client)
        print("\nГОТОВО ✔")
        return 0
    finally:
        try:
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
