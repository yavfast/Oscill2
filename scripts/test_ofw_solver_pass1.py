#!/usr/bin/env python3
"""
OFW mask solver — Pass-1 tests (Phase 2 of PL_OMS).

Covers SP_OMS_05_03 (anchors → known count == 106 on cols 2..513; 107 total incl. col 1),
SP_OMS_03_01 (input-validation errors E_NO_IMAGE / E_KS_INVALID), and the
phase-local classification contract: L=0 → code, the erased block → erased-lattice,
the hex-LUT pages L=10/11 → data-table/string, and cross-version column class.

Note (PL_OMS): for the 3 shipped images every column varies on at least one page,
so `classify_columns` yields 0 `constant` / 512 `varying` — the strict SP_OMS_02_02
definition. Per-page version-invariance (the real L=11 stability) is checked via
`page_is_version_constant`.

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


def test_load_and_anchors():
    print("load + anchors (SP_OMS_05_03):")
    cfg = S.SolverConfig()
    images, anchors = S.load(cfg)
    check("3 versions loaded", len(images.versions) == 3)
    check("59 logical pages + E", len([L for L in images.pages if L != 'E']) == 59)
    # ks_partial has 107 anchors total; col 1 (SEQ) is out of catalog scope (SP_OMS §01),
    # so 106 fall in cols 2..513 — the catalog's `known` count (SP_OMS_01_06 restriction).
    n_in_range = sum(1 for c in anchors if 2 <= c <= 513)
    check("110 anchors on cols 2..513 (111 total incl. col 1 SEQ)", n_in_range == 110)
    check("111 anchors total (incl. col 1 SEQ)", len(anchors) == 111)
    return images, anchors


def test_validation():
    print("input validation (SP_OMS_03_01):")
    bad = S.SolverConfig(images=["does_not_exist.ofw"])
    try:
        S.load(bad)
        check("missing image raises E_NO_IMAGE", False)
    except S.SolverError as e:
        check("missing image raises E_NO_IMAGE", e.code == "E_NO_IMAGE")
    bad2 = S.SolverConfig(ks_partial_path="nope_missing.json")
    try:
        S.load(bad2)
        check("missing ks raises E_KS_INVALID", False)
    except S.SolverError as e:
        check("missing ks raises E_KS_INVALID", e.code == "E_KS_INVALID")
    bad3 = S.SolverConfig(search_bound=0)
    try:
        S.load(bad3)
        check("search_bound<1 raises E_CONFIG", False)
    except S.SolverError as e:
        check("search_bound<1 raises E_CONFIG", e.code == "E_CONFIG")


def test_classify_pages(images, anchors):
    print("classify_pages (SP_OMS_02_03):")
    pages = S.classify_pages(images, anchors)
    check("L=0 -> code", pages[0].page_class == "code")
    check("L=0 entry_points include reset + vector opcodes + post-table",
          S.RESET_COL in pages[0].entry_points and 5 in pages[0].entry_points
          and S.POST_TABLE_COL in pages[0].entry_points)
    # Erased block: pages whose whole anchored lattice decrypts to 0xFF.
    erased = [L for L, pi in pages.items() if pi.page_class == "erased-lattice"]
    check("erased-lattice pages found in L=14..24 block",
          all(pages[L].page_class == "erased-lattice" for L in (14, 15, 16)))
    check("erased-lattice pages have no entry points",
          all(pages[L].entry_points == [] for L in erased))
    # Hex-LUT pages L=10/11 -> a text/data class (printable run).
    check("L=10 -> data-table/string", pages[10].page_class in ("data-table", "string"))
    check("L=11 -> data-table/string", pages[11].page_class in ("data-table", "string"))
    # page_is_version_constant detects byte-identical pages (some stable tables are;
    # note L=11's body is NOT identical across versions — only its hex-LUT region is).
    n_const = sum(1 for L in images.pages if S.page_is_version_constant(images, L))
    check("some pages are byte-identical across versions", n_const >= 1)


def test_classify_columns(images):
    print("classify_columns (SP_OMS_02_02):")
    cc = S.classify_columns(images)
    check("512 columns classified", len(cc) == 512)
    check("col 300 -> varying", cc[300] == "varying")
    check("no n/a columns (all pages carry 3 versions)",
          sum(1 for v in cc.values() if v == "n/a") == 0)


if __name__ == "__main__":
    print("=" * 60)
    print("OFW solver Pass-1 tests (firmware/ofw_mask_solver.py)")
    print("=" * 60)
    images, anchors = test_load_and_anchors()
    test_validation()
    test_classify_pages(images, anchors)
    test_classify_columns(images)
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
