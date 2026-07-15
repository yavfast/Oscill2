#!/usr/bin/env python3
"""
SP_CAL — Standalone hardware-free tests against the REAL web_oscill/calculations.py.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_calculations_unit.py`. Prints PASS/FAIL per case and
exits non-zero on any failure.

This replaces the false-confidence local reimplementation of hex encoding that
previously lived in scripts/test_hex_encoding.py: here we import and exercise the
actual calculations.samples_to_hex / samples_from_hex.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

from calculations import (  # noqa: E402
    samples_to_hex,
    samples_from_hex,
    samples_to_millivolts,
    calculate_segments,
    calculate_frequency_and_period,
)

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def test_hex_roundtrip():
    print("samples_to_hex / samples_from_hex round-trip:")
    # 1-byte path (uses bytes(...).hex() internally; values must be 0..255)
    s1 = [0, 1, 127, 128, 254, 255]
    hex1 = samples_to_hex(s1, sample_bytes=1)
    check("1-byte encodes 2 hex chars/sample", len(hex1) == len(s1) * 2)
    check("1-byte round-trip identity", samples_from_hex(hex1, sample_bytes=1) == s1)
    check("1-byte known encoding", samples_to_hex([0, 255], 1) == "00ff")

    # 2-byte path (big-endian, 4 hex chars/sample; values up to 65535)
    s2 = [0, 256, 1000, 65535]
    hex2 = samples_to_hex(s2, sample_bytes=2)
    check("2-byte encodes 4 hex chars/sample", len(hex2) == len(s2) * 4)
    check("2-byte round-trip identity", samples_from_hex(hex2, sample_bytes=2) == s2)
    check("2-byte known encoding", samples_to_hex([258, 255], 2) == "010200ff")

    # Empty handling
    check("empty samples -> ''", samples_to_hex([], 1) == "")
    check("empty hex -> []", samples_from_hex("", 1) == [])


def test_samples_to_millivolts():
    print("samples_to_millivolts basic scaling:")
    # v_div = 1 V = 1000 mV -> full scale 8000 mV, scale = 4000 mV, center = 127.5
    config = {"v_div": {"v": 1, "u": "V"}}
    mv = samples_to_millivolts([0, 255], sample_bits=8, config=config)
    check("s=0 -> -4000 mV", abs(mv[0] - (-4000.0)) < 1e-9)
    check("s=255 -> +4000 mV", abs(mv[1] - 4000.0) < 1e-9)
    # Midpoint code is near 0 mV
    mid = samples_to_millivolts([127, 128], sample_bits=8, config=config)
    check("codes straddle 0 mV", mid[0] < 0 < mid[1])
    # Empty list -> []
    check("empty samples -> []", samples_to_millivolts([], 8, config) == [])


def test_calculate_segments():
    print("calculate_segments basic behavior:")
    # samples vs threshold=4: [T,T,F,F,F,T,T] -> pos=[2,2], neg=[3]
    pos, neg = calculate_segments([5, 5, 1, 1, 1, 9, 9], 4)
    check("positive segment run-lengths", pos == [2, 2])
    check("negative segment run-lengths", neg == [3])
    # Empty input -> ([], [])
    check("empty -> ([], [])", calculate_segments([], 4) == ([], []))


def test_frequency_symmetric_square():
    print("calculate_frequency_and_period symmetric square wave:")
    # 10 cycles of 5 high + 5 low; avg threshold = 100.
    # period = (avg_pos + avg_neg) * t_step = (5 + 5) * 1.0 ms = 10 ms -> 100 Hz.
    samples = ([200] * 5 + [0] * 5) * 10
    result = calculate_frequency_and_period(samples, t_step_ms=1.0)
    freq = result.get("freq")
    check("freq is not None", freq is not None)
    check("freq ~= 100 Hz", freq is not None and abs(freq - 100.0) < 1e-6)
    check("period ~= 0.01 s", result.get("period") is not None
          and abs(result["period"] - 0.01) < 1e-9)


def test_frequency_asymmetric_regression_b12():
    print("REGRESSION PL_AUDIT_WEB_B12 (asymmetric duty cycle):")
    # 5 cycles of a short positive run [200,200] + a long negative run [0]*10.
    # avg threshold ~= 33. Noise filter (>= avg_segment=6) drops ALL positive runs
    # (length 2) while the negative runs (length 10) survive. Before the fix,
    # using 0 for the empty positive side produced a half-period => ~2x freq.
    # With the fix, one side being empty must yield freq is None.
    samples = ([200, 200] + [0] * 10) * 5
    result = calculate_frequency_and_period(samples, t_step_ms=1.0)
    check("freq is None (not a ~2x-inflated value)", result.get("freq") is None)
    check("period is None", result.get("period") is None)
    # segments_count is still reported (>=3) even though freq is suppressed.
    check("segments_count reported (>=3)", (result.get("segments_count") or 0) >= 3)


def test_frequency_edge_cases():
    print("calculate_frequency_and_period edge cases:")
    check("empty samples -> freq None", calculate_frequency_and_period([], 1.0).get("freq") is None)
    check("constant signal -> freq None",
          calculate_frequency_and_period([128] * 100, 0.1).get("freq") is None)


if __name__ == "__main__":
    print("=" * 60)
    print("SP_CAL calculations unit tests")
    print("=" * 60)
    test_hex_roundtrip()
    test_samples_to_millivolts()
    test_calculate_segments()
    test_frequency_symmetric_square()
    test_frequency_asymmetric_regression_b12()
    test_frequency_edge_cases()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
