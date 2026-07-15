#!/usr/bin/env python3
"""
SP_CVT — Standalone hardware-free tests for web_oscill/converters.py.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_converters.py`. Prints PASS/FAIL per case and exits
non-zero if any case fails. Imports the REAL converters module.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

from converters import convert, parse_unit, get_voltage_mv, get_time_ms  # noqa: E402

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def expect_raises(name, exc, fn, *args, **kwargs):
    global _failures
    try:
        fn(*args, **kwargs)
    except exc:
        print(f"  [PASS] {name}")
        return
    except Exception as e:  # wrong exception type
        _failures += 1
        print(f"  [FAIL] {name} (raised {type(e).__name__}, expected {exc.__name__})")
        return
    _failures += 1
    print(f"  [FAIL] {name} (no exception raised)")


def test_convert_prefixes_quantities():
    print("convert() across prefixes/quantities:")
    check("mV -> V (1000 -> 1.0)", convert(1000, "mV", "V") == 1.0)
    check("V -> mV (1 -> 1000)", convert(1, "V", "mV") == 1000.0)
    check("kHz -> Hz (1 -> 1000)", convert(1, "kHz", "Hz") == 1000.0)
    check("s -> ms (5 -> 5000)", convert(5, "s", "ms") == 5000.0)
    check("ms -> s (250 -> 0.25)", convert(250, "ms", "s") == 0.25)
    check("uV -> mV (1500 -> 1.5)", convert(1500, "uV", "mV") == 1.5)
    # Invariant: convert(x, u, u) == x  (from_unit == to_unit early return)
    check("V -> V early return (3.3 -> 3.3)", convert(3.3, "V", "V") == 3.3)
    # Early-return path does NOT validate the unit at all: bogus identical units pass through.
    check("bogus-but-identical unit early return", convert(42, "QQ", "QQ") == 42)


def test_parse_unit():
    print("parse_unit():")
    check("'mV' -> ('V','m')", parse_unit("mV") == ("V", "m"))
    check("'V' -> ('V','_')", parse_unit("V") == ("V", "_"))
    check("'kHz' -> ('Hz','k')", parse_unit("kHz") == ("Hz", "k"))
    expect_raises("parse_unit('XYZ') raises ValueError", ValueError, parse_unit, "XYZ")


def test_get_voltage_mv():
    print("get_voltage_mv() happy path:")
    check("v_div 1 V -> 1000 mV", get_voltage_mv({"v_div": {"v": 1, "u": "V"}}) == 1000.0)
    check("v_div 500 mV -> 500 mV", get_voltage_mv({"v_div": {"v": 500, "u": "mV"}}) == 500.0)


def test_get_time_ms():
    print("get_time_ms() happy path:")
    check("t_div 1 s -> 1000 ms", get_time_ms({"t_div": {"v": 1, "u": "s"}}) == 1000.0)
    check("t_div 200 us -> 0.2 ms", get_time_ms({"t_div": {"v": 200, "u": "us"}}) == 0.2)


def test_error_cases():
    print("error cases:")
    # Incompatible quantity mix (V vs s)
    expect_raises("convert V->s raises ValueError", ValueError, convert, 1, "V", "s")
    # Bad unit string
    expect_raises("convert bad from_unit raises ValueError", ValueError, convert, 1, "ZZ", "V")
    expect_raises("convert bad to_unit raises ValueError", ValueError, convert, 1, "V", "ZZ")
    # get_voltage_mv structural errors
    expect_raises("get_voltage_mv missing key raises KeyError", KeyError, get_voltage_mv, {})
    expect_raises("get_voltage_mv non-dict entry raises TypeError", TypeError,
                  get_voltage_mv, {"v_div": 5})
    expect_raises("get_voltage_mv missing v/u raises KeyError", KeyError,
                  get_voltage_mv, {"v_div": {"v": 1}})


if __name__ == "__main__":
    print("=" * 60)
    print("SP_CVT converters tests")
    print("=" * 60)
    test_convert_prefixes_quantities()
    test_parse_unit()
    test_get_voltage_mv()
    test_get_time_ms()
    test_error_cases()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
