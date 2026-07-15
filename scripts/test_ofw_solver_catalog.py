#!/usr/bin/env python3
"""
OFW mask solver — catalog / report / propose tests (Phase 4 of PL_OMS).

Covers SP_OMS_05_01 (happy path: 512 records, summary sums to 512; propose gated),
SP_OMS_05_02 (determinism: two runs byte-identical; ks_partial sha256 unchanged;
known never overwritten), and SP_OMS_05_04 edge cases (erased-lattice yields no code
attack; window bound handling).

Writes the catalog to a scratch path (not the shipped firmware/ks_solver_catalog.json)
so the test is side-effect free. Per project rule PythonTestsAreStandaloneScripts.
"""

import hashlib
import json
import os
import sys
import tempfile

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'firmware'))

import ofw_mask_solver as S  # noqa: E402

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_happy_path(tmp):
    print("happy path (SP_OMS_05_01):")
    cfg = S.SolverConfig(catalog_out=os.path.join(tmp, "cat1.json"))
    catalog = S.solve(cfg)
    cols = catalog["columns"]
    check("512 column records", len(cols) == 512)
    s = catalog["meta"]["summary"]
    check("summary sums to 512", s["known"] + s["unique"] + s["variants"] + s["undeterminable"] == 512)
    check("known count == 106 (cols 2..513)", s["known"] == 106)
    check("meta.total == 514", catalog["meta"]["total"] == 514)
    return catalog


def test_known_not_overwritten(catalog):
    print("known never overwritten (SP_OMS_05_02):")
    ks = json.load(open(S._resolve("ks_partial.json")))["known"]
    ok = True
    for col_s, val in ks.items():
        col = int(col_s)
        if not (2 <= col <= 513):
            continue
        rec = catalog["columns"][str(col)]
        if rec["verdict"] != "known" or int(rec["value"], 16) != int(val, 16):
            ok = False
    check("every ks_partial col 2..513 -> known with anchor value", ok)
    # col 133 IS a known anchor in the real run -> must be `known`, not `unique`.
    check("col 133 -> known (present in ks_partial)", catalog["columns"]["133"]["verdict"] == "known")


def test_determinism(tmp):
    print("determinism + no-write (SP_OMS_05_02):")
    ks_path = S._resolve("ks_partial.json")
    before = _sha(ks_path)
    p1 = os.path.join(tmp, "d1.json")
    p2 = os.path.join(tmp, "d2.json")
    S.solve(S.SolverConfig(catalog_out=p1))
    S.solve(S.SolverConfig(catalog_out=p2))
    check("two runs byte-identical", _sha(p1) == _sha(p2))
    check("ks_partial.json sha256 unchanged", _sha(ks_path) == before)


def test_propose_gated(tmp):
    print("propose_promotions gated (SP_OMS_05_01):")
    ks_path = S._resolve("ks_partial.json")
    before = _sha(ks_path)
    # Hide col 133 so it becomes a fresh `unique` find -> a real proposal.
    hidden = os.path.join(tmp, "ks_hidden.json")
    ks = json.load(open(ks_path))
    ks["known"].pop("133", None)
    json.dump(ks, open(hidden, "w"))
    cfg = S.SolverConfig(ks_partial_path=hidden, catalog_out=os.path.join(tmp, "cat_h.json"))
    catalog = S.solve(cfg)
    anchors = S._load_anchors(cfg)
    proposals = S.propose_promotions(catalog, anchors)
    cols = {p["col"] for p in proposals}
    check("col 133 proposed as unique", 133 in cols)
    check("proposal carries value 0x29", any(p["col"] == 133 and p["value"] == "0x29" for p in proposals))
    check("ks_partial.json still unchanged after propose", _sha(ks_path) == before)


def test_edge_erased_lattice(catalog):
    print("edge cases (SP_OMS_05_04):")
    # Erased-lattice pages contribute no code attack -> no false 0xFF harvest.
    # A non-lattice, non-anchor column stays undeterminable (never fabricated as known).
    rec = catalog["columns"]["300"]
    check("col 300 (data) -> undeterminable", rec["verdict"] == "undeterminable")
    check("col 300 not fabricated as known/unique", rec["value"] is None)
    # Exhaustiveness holds where a signal fired (attacked cols have rejected sets).
    attacked = [r for r in catalog["columns"].values() if r["rejected"]]
    ok = all(len(r["candidates"]) + len({e["K"] for e in r["rejected"]}) == 256
             for r in attacked if isinstance(r["candidates"], list))
    check("attacked cols: candidates + rejected == 256", ok)


if __name__ == "__main__":
    print("=" * 60)
    print("OFW solver catalog/report/propose tests")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as tmp:
        catalog = test_happy_path(tmp)
        test_known_not_overwritten(catalog)
        test_determinism(tmp)
        test_propose_gated(tmp)
        test_edge_erased_lattice(catalog)
        print(S.report(catalog))
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
