#!/usr/bin/env python3
"""
SP_AAJ — Standalone hardware-free tests for the pure step-finding logic in
web_oscill/auto_adjust.py: find_next_step / find_next_vdiv / find_next_tdiv.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_auto_adjust_steps.py`. Prints PASS/FAIL per case, exits
non-zero on any failure.

NOTE: the device-driving functions (auto_adjust_v_div / auto_adjust_t_div /
auto_adjust_v_offset / auto_adjust_trigger_level / auto_adjust_multiple) are
NOT tested here — they require a live device_service and hardware.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

from auto_adjust import (  # noqa: E402
    find_next_step,
    find_next_vdiv,
    find_next_tdiv,
    VDIV_VALUES_MV,
    TDIV_VALUES_MS,
)

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def test_vdiv_boundaries():
    print("find_next_vdiv boundaries:")
    check("min going down -> None", find_next_vdiv(VDIV_VALUES_MV[0], -1) is None)
    check("max going up -> None", find_next_vdiv(VDIV_VALUES_MV[-1], +1) is None)


def test_vdiv_mid_stepping():
    print("find_next_vdiv mid-list stepping:")
    check("100 up -> 200", find_next_vdiv(100.0, +1) == 200.0)
    check("100 down -> 50", find_next_vdiv(100.0, -1) == 50.0)
    check("min up -> 50", find_next_vdiv(20.0, +1) == 50.0)
    check("max down -> 5000", find_next_vdiv(10000.0, -1) == 5000.0)


def test_tdiv_boundaries_and_stepping():
    print("find_next_tdiv boundaries & stepping:")
    check("min going down -> None", find_next_tdiv(TDIV_VALUES_MS[0], -1) is None)
    check("max going up -> None", find_next_tdiv(TDIV_VALUES_MS[-1], +1) is None)
    check("1 up -> 2", find_next_tdiv(1, +1) == 2)
    check("1 down -> 0.5", find_next_tdiv(1, -1) == 0.5)


def test_not_in_list_closest_branch():
    print("find_next_step not-in-list closest-value branch:")
    # 150 is not a valid V/div step; +1 finds closest LARGER, -1 closest SMALLER.
    check("150 up -> 200 (closest larger)", find_next_vdiv(150.0, +1) == 200.0)
    check("150 down -> 100 (closest smaller)", find_next_vdiv(150.0, -1) == 100.0)
    # Not-in-list with nothing in the requested direction -> None.
    check("above-max up -> None", find_next_vdiv(99999.0, +1) is None)
    check("below-min down -> None", find_next_vdiv(1.0, -1) is None)
    # Not-in-list but there IS something below when going up above everything's floor.
    check("below-min up -> 20 (closest larger)", find_next_vdiv(1.0, +1) == 20.0)


def test_find_next_step_direct():
    print("find_next_step direct on a custom list:")
    values = [1.0, 2.0, 4.0, 8.0]
    check("exact mid up", find_next_step(values, 2.0, +1) == 4.0)
    check("exact mid down", find_next_step(values, 4.0, -1) == 2.0)
    check("top up -> None", find_next_step(values, 8.0, +1) is None)
    check("bottom down -> None", find_next_step(values, 1.0, -1) is None)
    check("not-in-list up (3 -> 4)", find_next_step(values, 3.0, +1) == 4.0)
    check("not-in-list down (3 -> 2)", find_next_step(values, 3.0, -1) == 2.0)


if __name__ == "__main__":
    print("=" * 60)
    print("SP_AAJ auto_adjust step-finding tests")
    print("=" * 60)
    test_vdiv_boundaries()
    test_vdiv_mid_stepping()
    test_tdiv_boundaries_and_stepping()
    test_not_in_list_closest_branch()
    test_find_next_step_direct()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
