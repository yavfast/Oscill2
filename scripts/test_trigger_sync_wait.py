#!/usr/bin/env python3
"""
task_trigger-highqs — Standalone hardware-free test of the trigger-wait unit
conversion in web_oscill/oscill_client.py.

Per PythonTestsAreStandaloneScripts: no pytest; run as
`python3 scripts/test_trigger_sync_wait.py`. Exits non-zero on any failure.

Covers the pure math of the fix (TA/TW in units of 12×MC): the device-side
serial writes/reads in apply_sync_wait/get_data_single need real hardware and are
exercised in the manual on-device Verify step, not here.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

from oscill_client import OscillClient  # noqa: E402

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def test_sync_wait_units():
    print("_sync_wait_units — 12×MC conversion:")
    c = OscillClient.__new__(OscillClient)   # no serial / no __init__
    # 70 MHz → MC period 14.2857 ns → 1429 in 10 ps units.
    c._cpu_tick_10ps = 1429
    unit_s = 12.0 * 1429 * 1e-11             # ≈ 171.5  ns per TA/TW unit

    # A desired 0.5 s wait maps to ≈ desired / unit_s units.
    units = c._sync_wait_units(0.5)
    expected = round(0.5 / unit_s)
    check("0.5 s → correct unit count", abs(units - expected) <= 1)

    # The OLD fixed 500 units corresponds to the ~86 µs that starved the trigger.
    old_abs_s = 500 * unit_s
    check("legacy 500 units ≈ 86 µs (the bug)", 80e-6 < old_abs_s < 92e-6)

    # New default WAIT window (≥0.15 s) is orders of magnitude larger than the old 86 µs.
    new_units = c._sync_wait_units(OscillClient.TRIG_WAIT_MIN_S)
    check("min WAIT window >> legacy 500", new_units > 500 * 100)

    # Monotonic and clamped to the 4-byte register range.
    check("monotonic in desired seconds", c._sync_wait_units(1.0) > c._sync_wait_units(0.2))
    check("clamped to >=1", c._sync_wait_units(0.0) >= 1)
    check("clamped to 32-bit max", c._sync_wait_units(1e9) <= 0xFFFFFFFF)

    # Degrades safely when MC is unreadable (0) → legacy fallback, never a crash.
    c._cpu_tick_10ps = 0
    check("MC=0 → legacy 500 fallback", c._sync_wait_units(0.5) == 500)


def test_clamp_constants():
    print("trigger-wait clamp constants sane:")
    check("AUTO window < WAIT window (auto free-runs sooner)",
          OscillClient.AUTO_WAIT_MAX_S <= OscillClient.TRIG_WAIT_MAX_S)
    check("WAIT floor positive and sub-second", 0 < OscillClient.TRIG_WAIT_MIN_S < 1.0)
    check("WAIT cap at most a couple seconds", OscillClient.TRIG_WAIT_MAX_S <= 2.0)


def main():
    print("=" * 60)
    print("task_trigger-highqs — sync-wait conversion tests")
    print("=" * 60)
    test_sync_wait_units()
    test_clamp_constants()
    print("=" * 60)
    if _failures:
        print(f"RESULT: {_failures} FAILURE(S)")
        sys.exit(1)
    print("RESULT: ALL PASSED")


if __name__ == "__main__":
    main()
