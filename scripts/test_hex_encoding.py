#!/usr/bin/env python3
"""
Hex sample encoding test.

FIXED (was PL_AUDIT_WEB_09): this script previously defined its OWN local
samples_to_hex/hex_to_samples and asserted against them — a false-confidence
test that never exercised the shipping code and would have stayed green even if
web_oscill/calculations.py broke. It now imports and tests the REAL
calculations.samples_to_hex / samples_from_hex.

The comprehensive round-trip / edge-case coverage lives in
scripts/test_calculations_unit.py (SP_CAL); this script keeps a focused
encoding round-trip so the historical entry point stays meaningful and passing.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_hex_encoding.py`. Prints PASS/FAIL per case, exits
non-zero on any failure.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

from calculations import samples_to_hex, samples_from_hex  # noqa: E402

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def test_roundtrip_1byte():
    print("1-byte encoding (calculations.samples_to_hex):")
    samples = [0, 15, 16, 127, 128, 200, 255]
    encoded = samples_to_hex(samples, sample_bytes=1)
    check("2 hex chars per sample", len(encoded) == len(samples) * 2)
    check("round-trip identity", samples_from_hex(encoded, sample_bytes=1) == samples)
    check("empty -> ''", samples_to_hex([], 1) == "")


def test_roundtrip_2byte():
    print("2-byte encoding (calculations.samples_to_hex):")
    samples = [0, 255, 256, 4096, 65535]
    encoded = samples_to_hex(samples, sample_bytes=2)
    check("4 hex chars per sample", len(encoded) == len(samples) * 4)
    check("round-trip identity", samples_from_hex(encoded, sample_bytes=2) == samples)
    check("empty hex -> []", samples_from_hex("", 2) == [])


if __name__ == "__main__":
    print("=" * 60)
    print("Hex encoding tests (REAL calculations module)")
    print("=" * 60)
    test_roundtrip_1byte()
    test_roundtrip_2byte()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
