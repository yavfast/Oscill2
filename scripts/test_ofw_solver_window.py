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
    print("cols 21,125 -> candidate set contains 0xc1 / 0xdf (hidden):")
    # 21/125 were promoted into ks_partial (mask 109); hide them to exercise recovery.
    anchors = {c: v for c, v in base_anchors.items() if c not in (21, 125)}
    res = _solve_L0(images, anchors)
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


def test_epilogue_prologue_signals(images, base_anchors):
    print("S-epilogue / S-prologue signals (spike §3g — soft, never-promoted):")
    # A synthetic mapped fn-start whose entry column is NOT yet known exercises both signals.
    entry_col = 200                                   # not lattice (≢6 mod8), not a vector col
    fn_addr = S.L0_LO + (entry_col - 2)               # 0x04C6 -> _l0_addr_to_col == 200
    check("chosen entry col is genuinely unknown", entry_col not in base_anchors)
    check("addr round-trips to the entry col", S._l0_addr_to_col(fn_addr) == entry_col)

    pro = S.prologue_candidates(images, base_anchors, fn_addr)
    check("prologue fires on an unknown-entry mapped fn-start", bool(pro))
    priors = pro.get("priors", [])
    p0_vals = {int(c["P"][0], 16) for c in priors}        # first byte of each 2-byte pattern
    check("prologue priors include MOV R7,DPL (AF ..)", 0xAF in p0_vals)
    check("prologue priors include PUSH ACC (C0 ..)", 0xC0 in p0_vals)
    check("every prior is a 2-byte pattern (col1 in page)", all(len(c["P"]) == 2 for c in priors))
    check("every prior yields two (col,K) pairs", all(len(c["cols"]) == 2 and len(c["K"]) == 2 for c in priors))
    check("priors are tiered by confidence", {c["confidence"] for c in priors} >= {"primary", "variant"})
    check("prologue is a PRIOR set, never a single forced pattern", len(priors) >= 3)
    # K derivation is arithmetically correct: K[entry] = C[entry] - P0
    ref = images.ref_bytes(0)
    af = next(c for c in priors if int(c["P"][0], 16) == 0xAF)
    check("K[entry] = (C[entry]-0xAF) mod 256 for the AF-82 prior",
          int(af["K"][0], 16) == (ref[entry_col] - 0xAF) & 0xFF)

    # Cross-check: entry col just before a KNOWN anchor -> 2nd byte is validated/refuted (a real filter).
    kc = min(c for c in base_anchors if c - 1 not in base_anchors and c - 1 > 2)  # known col whose pred is unknown
    x_addr = S.L0_LO + ((kc - 1) - 2)
    xpro = S.prologue_candidates(images, base_anchors, x_addr)
    if xpro:  # only if (kc-1) maps into L0
        checks = [c.get("check") for c in xpro["priors"] if "check" in c]
        check("2nd byte on a known col yields a validated/refuted cross-check",
              len(checks) == len(xpro["priors"]) and set(checks) <= {"validated", "refuted"})

    epi = S.epilogue_candidates(images, base_anchors, fn_addr)
    e_vals = {int(c["P"], 16) for c in epi.get("candidates", [])}
    check("epilogue offers RET(0x22) and RETI(0x32)", {0x22, 0x32} <= e_vals)
    check("epilogue is a variant set, never a single unique byte", len(epi.get("candidates", [])) >= 2)

    # Safety: prologue SKIPS an already-known entry column (no re-derivation of a proven byte).
    known_addr = S.L0_LO + (133 - 2)                  # col 133 = the proven trampoline LJMP opcode
    check("prologue skips a known entry column (col 133)",
          S.prologue_candidates(images, base_anchors, known_addr) == {})


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
    test_epilogue_prologue_signals(images, anchors)
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
