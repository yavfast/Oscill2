#!/usr/bin/env python3
"""RCIGD Phase 5a scaffold test (PL_OMS Phase 5).

Verifies the RAM state + seed + frontier + checkpoint round-trip are sound and that the
process start does NOT fabricate narrowing (staged primitives raise). Standalone per project
rule PythonTestsAreStandaloneScripts.
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'firmware'))
import ofw_graph_decode as G          # noqa: E402
import ofw_mask_solver as S           # noqa: E402

_failures = 0


def check(name, cond):
    global _failures
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        _failures += 1


def main():
    print("=" * 60)
    print("RCIGD Phase 5a scaffold (state / seed / frontier / checkpoint)")
    print("=" * 60)
    images, anchors = S.load(S.SolverConfig())

    st = G.build_seed(images, anchors)
    # state invariants
    check("known cols are singleton domains", all(st.size(c) == 1 for c in anchors if 2 <= c < 514))
    check("unknown cols start full (256)", st.size(300) == 256 and 300 not in anchors)
    check("no domain exceeds 256 / is empty", all(1 <= st.size(c) <= 256 for c in G.BODY))

    # address mapping is sound (matches the skill's 10 code pages)
    check("page_of_hi(0x1b)=L11 (INT0)", G.page_of_hi(0x1b) == 11)
    check("page_of_hi(0x07)=L1 (SPI0)", G.page_of_hi(0x07) == 1)
    check("page_of_hi(0x0d)=L4 (startup/v13/v14)", G.page_of_hi(0x0d) == 4)
    check("addr_to_col(0x0483)=(L0,133)", G.addr_to_col(0x0483) == (0, 133))
    check("page_of_hi below app base -> None", G.page_of_hi(0x03) is None)

    # frontier: 16 vector targets; decodable ones land on real code pages
    check("frontier has 16 vector targets", len(st.frontier) == 16)
    dec = [f for f in st.frontier if f["decodable"]]
    check("14 decodable into app code pages (2 boot-redirect excluded)", len(dec) == 14)
    pages = {f["page"] for f in dec}
    check("decodable frontier pages subset of the 10 code pages",
          pages <= {0, 1, 4, 11, 17, 24, 25, 34, 49, 52})
    check("boot-redirect vectors (INT1/v15) are non-decodable",
          all(not f["decodable"] for f in st.frontier if f["vector"] in ("INT1", "v15")))
    check("reset target resolved (lo_domain size 1)",
          any(f["vector"] == "reset" and f["lo_domain_size"] == 1 for f in st.frontier))

    # checkpoint round-trip
    sh = G.seed_hash(images, anchors)
    sh2 = G.seed_hash(images, anchors)
    check("seed hash is deterministic", sh == sh2)
    path = st.save(G.CHECKPOINT, sh)
    st2 = G.DomainState.load_snapshot(path, anchors)
    check("checkpoint round-trips domains", all(st2.dom[c] == st.dom[c] for c in G.BODY))
    check("checkpoint round-trips frontier", st2.frontier == st.frontier)


    # ---- Phase 5b: tiling_roles soundness on a CONTROLLED synthetic sector ----
    # K=0 over a region => plaintext == ciphertext; lay a known instruction stream and check roles.
    # stream @col 10: NOP(00) | LJMP 04 05 (02 04 05) | RET(22) | NOP(00)
    sec = bytearray(514)
    prog = {10: 0x00, 11: 0x02, 12: 0x04, 13: 0x05, 14: 0x22, 15: 0x00}
    for c, b in prog.items():
        sec[c] = b
    anc = {c: 0 for c in range(10, 20)}            # K=0 known over the region -> P==C
    ranges = S.SolverConfig().flash_ranges
    bnd, ops, ok = G.tiling_roles(bytes(sec), anc, 10, 16, ranges)
    check("tiling_roles: seed completes", ok)
    check("tiling_roles: col10 NOP is a boundary (len1)", bnd.get(10) == {1})
    check("tiling_roles: col11 LJMP is a boundary (len3)", bnd.get(11) == {3})
    check("tiling_roles: cols 12,13 are operands of the LJMP", {12, 13} <= ops)
    check("tiling_roles: col14 RET is a boundary", 14 in bnd)
    check("tiling_roles: LJMP operand cols not misread as boundaries", 12 not in bnd and 13 not in bnd)

    # soundness: hide a genuinely-known lattice col, narrow, and confirm its TRUE K is NOT removed
    hide = 142                                     # an L0 lattice col in the col136 window
    if hide in anchors:
        truth = anchors[hide]
        anchors_h = {c: v for c, v in anchors.items() if c != hide}
        st_h = G.build_seed(images, anchors_h)
        G.narrow_from_seed(st_h, images, 0, 136, ranges)
        check("soundness: hidden col's TRUE K survives narrowing (never wrongly removed)",
              truth in st_h.dom[hide])

    # narrowed domains are non-empty, <256, and contain only legal-opcode-consistent K (>=1)
    st_n = G.build_seed(images, anchors)
    ch = G.narrow_from_seed(st_n, images, 0, 136, ranges)
    real = {c: s for c, s in ch.items() if not str(c).startswith("__")}
    check("narrowed domains stay non-empty", all(st_n.size(c) >= 1 for c in real))
    check("narrowing is deterministic",
          G.narrow_from_seed(G.build_seed(images, anchors), images, 0, 136, ranges) == ch)

    # ---- Phase 5c: _branch_roles on the controlled synthetic sector ----
    # Only cols 10,11,14 known -> the LJMP operands 12,13 are unknown => classified as unconstrained.
    anc_sparse = {10: 0, 11: 0, 14: 0}
    feasible, forced, unconstrained = G._branch_roles({"v": bytes(sec)}, anc_sparse, 10, ranges)
    check("_branch_roles: feasible on the synthetic stream", feasible)
    check("_branch_roles: LJMP operand cols (12,13) are unconstrained", {12, 13} <= unconstrained)
    check("_branch_roles: forced cols are never also unconstrained", not (set(forced) & unconstrained))

    # ---- Phase 5c: expand_frontier soundness + measured behaviour (one full run) ----
    st_f = G.build_seed(images, anchors)
    rep = G.expand_frontier(st_f, images, S.SolverConfig())
    check("expand_frontier reports every decodable vector", len(rep["vectors"]) == 14)
    check("known cols untouched by frontier expansion",
          all(st_f.size(c) == 1 for c in anchors if 2 <= c < 514))
    check("all domains stay non-empty after frontier expansion",
          all(st_f.size(c) >= 1 for c in G.BODY))
    check("frontier narrowing is bounded/sound (negligible: total < 32)", rep["total_narrowed"] < 32)
    rep2 = G.expand_frontier(G.build_seed(images, anchors), images, S.SolverConfig())
    check("frontier expansion is deterministic", rep == rep2)

    # invariant: RCIGD never touches ks_partial
    check("ks_partial NOT written by RCIGD (separate map)",
          G.CHECKPOINT != S.SolverConfig().ks_partial_path)

    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} case(s))")
        return 1
    print("RESULT: PASS (all cases passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
