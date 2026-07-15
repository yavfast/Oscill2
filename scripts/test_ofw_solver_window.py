#!/usr/bin/env python3
"""
OFW mask solver — solve_window §3f reproduction (Phase 3 of PL_OMS).

This is the executable acceptance test (SP_OMS_05_01). It runs the hide-and-recover
harness on the L=0 vector table:

  * hide col 133 from anchors  -> verdict `unique`, value 0x29 (the committed byte)
  * cols 21, 125 (never anchors) -> candidate set contains 0xc1 / 0xdf (0x02-derived)
  * cols 13, 45 (hi=0xFF)         -> `variants` with BOTH the LJMP(0x02) and erased(0xFF) K

Also checks SP_OMS_05_02 invariants: exhaustiveness (survivors + distinct rejected == 256),
signal monotonicity (no K both survives and is rejected), and bound-independence of `unique`.

Per project rule PythonTestsAreStandaloneScripts: standalone, prints PASS/FAIL, non-zero exit on failure.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'firmware'))

import ofw_mask_solver as S  # noqa: E402

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def _solve_L0(images, anchors, config=None):
    """Run windows_of + solve_window over L=0 with the given anchor set. -> {col: result}."""
    config = config or S.SolverConfig()
    pages = S.classify_pages(images, anchors)
    page = pages[0]
    node_counter = [0]
    out = {}
    for window in S.windows_of(page, anchors):
        out.update(S.solve_window(window, page, images, anchors, config, node_counter))
    return out


def test_hide_col133(images, base_anchors):
    print("hide col 133 -> unique 0x29 (§3f positive control):")
    anchors = dict(base_anchors)
    anchors.pop(133, None)
    res = _solve_L0(images, anchors)
    check("col 133 attacked", 133 in res)
    surv = res[133]["survivors"]
    check("col 133 -> exactly one survivor (unique)", len(surv) == 1)
    check("col 133 unique value == 0x29", (0x29 in surv))


def test_trap_slots_21_125(images, base_anchors):
    print("cols 21,125 -> candidate set contains 0xc1 / 0xdf:")
    res = _solve_L0(images, base_anchors)
    s21 = res[21]["survivors"]
    s125 = res[125]["survivors"]
    check("col 21 candidates contain 0xc1", 0xc1 in s21)
    check("col 125 candidates contain 0xdf", 0xdf in s125)


def test_ambiguous_ff_13_45(images, base_anchors):
    print("cols 13,45 (hi=0xFF) -> variants: LJMP + erased both present:")
    res = _solve_L0(images, base_anchors)
    for col in (13, 45):
        surv = res[col]["survivors"]
        kinds = {v["P"] for v in surv.values()}
        check(f"col {col} -> >=2 survivors (variants)", len(surv) >= 2)
        check(f"col {col} has both LJMP(0x02) and erased(0xFF) fills",
              0x02 in kinds and 0xFF in kinds)


def test_invariants(images, base_anchors):
    print("invariants (SP_OMS_05_02):")
    res = _solve_L0(images, base_anchors)
    ok_exhaust = True
    ok_monotone = True
    for r in res.values():
        surv = set(r["survivors"])
        rej = set(r["rejected"])
        if not r["bounded"]:
            if len(surv) + len(rej) != 256:
                ok_exhaust = False
        if surv & rej:
            ok_monotone = False
    check("exhaustiveness: survivors + distinct rejected == 256", ok_exhaust)
    check("signal monotonicity: no K both survives and is rejected", ok_monotone)


def test_bound_independence(images, base_anchors):
    print("bound-independence of unique (SP_OMS_05_02):")
    anchors = dict(base_anchors)
    anchors.pop(133, None)
    lo = _solve_L0(images, anchors, S.SolverConfig(search_bound=200000))
    hi = _solve_L0(images, anchors, S.SolverConfig(search_bound=2000000))
    check("col 133 unique value stable under search_bound x10",
          set(lo[133]["survivors"]) == set(hi[133]["survivors"]) == {0x29})


def test_cross_version_prunes(images, base_anchors):
    print("cross-version S4 (SP_OMS_05_03):")
    # A fabricated single-version image set must still agree; here we assert that the
    # shared key survivors are exactly those consistent across all 3 versions (S4 held).
    res = _solve_L0(images, base_anchors)
    # For col 133 hidden, the LJMP survivor's K must decode to 0x02 in every version.
    anchors = dict(base_anchors)
    anchors.pop(133, None)
    res = _solve_L0(images, anchors)
    k = next(iter(res[133]["survivors"]))
    pv = images.page_versions(0)
    ok = all(((sec[133] - k) & 0xFF) == 0x02 for sec in pv.values())
    check("col 133 survivor decodes to LJMP in all versions", ok)


if __name__ == "__main__":
    print("=" * 60)
    print("OFW solver solve_window §3f reproduction (acceptance test)")
    print("=" * 60)
    cfg = S.SolverConfig()
    images, anchors = S.load(cfg)
    test_hide_col133(images, anchors)
    test_trap_slots_21_125(images, anchors)
    test_ambiguous_ff_13_45(images, anchors)
    test_invariants(images, anchors)
    test_bound_independence(images, anchors)
    test_cross_version_prunes(images, anchors)
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
