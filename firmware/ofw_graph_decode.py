#!/usr/bin/env python3
"""RCIGD — Recursive Cross-version Instruction-Graph Decode (PL_OMS Phase 5).

Narrows per-column keystream K-domains by branch-and-bound over instruction-alignment
hypotheses (hard rejections: S1 illegal opcode, S3 out-of-range abs target; S4 cross-version).
Goal is NARROWING, not unique proof — output is a probabilistic per-column domain map + ranked
function-entry hypotheses. See docs/ofw_mask_solver.plan.md Phase 5 for the full algorithm.

Phase 5a (this file, runnable): the RAM-resident DomainState + seed + frontier + checkpoint I/O
+ `kickoff`. The decode_forward primitive (5b), MRV expansion (5c) and measurement (5d) are
staged next — their entry points are defined but raise NotImplementedError so the process start
is honest (no faked narrowing).

Invariants (carried from SP_OMS): NEVER writes ks_partial (RCIGD output is a SEPARATE map);
deterministic (no RNG); read-only on .ofw. Only intermediate snapshots hit disk; work is in RAM.
"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import ofw_mask_solver as S            # noqa: E402
from mcs51 import instr_info           # noqa: E402

SECTOR = 514
BODY = range(2, SECTOR)                # cols 0/1 are CRC/SEQ, out of code scope
PAGE_SIZE = 0x200
FLASH_BASE = 0x0400
CHECKPOINT = "ks_graph_state.json"     # git-ignored, regenerable


def page_of_hi(hi):
    """Logical page L that an absolute app address 0xHHxx falls in (the whole 256-byte hi-block
    sits in one 512-byte page). Returns None for non-app (bootloader / erased) high bytes."""
    base = hi << 8
    if base < FLASH_BASE:
        return None
    L = (base - FLASH_BASE) // PAGE_SIZE
    return L


def addr_to_col(addr):
    """Absolute app flash address -> (L, keystream col) or (None, None) if below app base."""
    if addr < FLASH_BASE:
        return None, None
    off = (addr - FLASH_BASE) % PAGE_SIZE
    L = (addr - FLASH_BASE) // PAGE_SIZE
    return L, off + 2


# ------------------------------------------------------------------- RAM state
class DomainState:
    """Per-column K candidate domains, RAM-resident. Known cols are singletons; unknown start full."""

    def __init__(self, anchors):
        self.anchors = dict(anchors)
        # dom[col] = set of surviving K values (0..255). Known -> {K}. Unknown -> full.
        self.dom = {}
        for col in BODY:
            self.dom[col] = {anchors[col]} if col in anchors else set(range(256))
        self.frontier = []             # list of frontier dicts (unresolved jump targets)
        self.entries = []              # confirmed aligned entry points (page, col, provenance)
        self.stats = {"nodes": 0, "branches_live": 0, "branches_killed": 0}

    def size(self, col):
        return len(self.dom[col])

    def prune(self, col, keep):
        """Intersect dom[col] with `keep` (a set/iterable of K values). Returns #removed."""
        before = len(self.dom[col])
        self.dom[col] &= set(keep)
        return before - len(self.dom[col])

    # ---- checkpoint (intermediate results only) ----
    def to_dict(self, seed_hash):
        # compact: store only non-full domains (known singletons + any pruned col)
        narrowed = {str(c): sorted(self.dom[c]) for c in BODY if len(self.dom[c]) < 256}
        return {
            "note": "RCIGD intermediate snapshot (PL_OMS Phase 5). Regenerable; NOT the proven mask. "
                    "Cols absent from 'domains' are still full (256 candidates).",
            "seed_hash": seed_hash,
            "total_cols": len(BODY),
            "known_cols": sum(1 for c in BODY if c in self.anchors),
            "narrowed_cols": len(narrowed),
            "domains": narrowed,
            "frontier": self.frontier,
            "entries": self.entries,
            "stats": self.stats,
        }

    def save(self, path, seed_hash):
        full = path if os.path.isabs(path) else os.path.join(S.FIRMWARE_DIR, path)
        with open(full, "w") as fh:
            json.dump(self.to_dict(seed_hash), fh, indent=1)
        return full

    @classmethod
    def load_snapshot(cls, path, anchors):
        full = path if os.path.isabs(path) else os.path.join(S.FIRMWARE_DIR, path)
        with open(full) as fh:
            d = json.load(fh)
        st = cls(anchors)
        for c, vals in d.get("domains", {}).items():
            st.dom[int(c)] = set(vals)
        st.frontier = d.get("frontier", [])
        st.entries = d.get("entries", [])
        st.stats = d.get("stats", st.stats)
        return st


# ------------------------------------------------------------------- seeding
def build_seed(images, anchors):
    """Construct the initial DomainState: known-boundary entries on L=0 + the 16 vector-target frontier."""
    st = DomainState(anchors)

    # Entries: known instruction boundaries. The reset LJMP (cols 2..4, 3 bytes) => boundary at col 5;
    # the startup LJMP (cols 133..135) => the first unknown-alignment boundary at col 136.
    for col, prov in [(2, "reset LJMP@0x0400"), (133, "startup LJMP@0x0483")]:
        if col in anchors:
            st.entries.append({"L": 0, "col": col, "kind": "known-boundary", "prov": prov})
    st.entries.append({"L": 0, "col": 136, "kind": "post-startup-boundary",
                       "prov": "first unknown-alignment boundary after the L0 startup LJMP"})

    # Frontier: each L=0 vector LJMP target. target-hi is on the lattice (known); target-lo is unknown
    # -> lo-domain = dom[lo_col]. Map hi -> logical code page. Bootloader/erased his are not decodable.
    for row in S.scan_jump_targets(images, anchors):
        hi = None if row["target_hi"] is None else int(row["target_hi"], 16)
        # lo column = opcode col + 2
        lo_col = row["at_col"] + 2
        L = page_of_hi(hi) if hi is not None else None
        decodable = L is not None and images.ref_bytes(L) is not None
        st.frontier.append({
            "vector": row["from_slot"],
            "opcode_col": row["at_col"],
            "target_hi": row["target_hi"],
            "lo_col": lo_col,
            "page": L,
            "decodable": bool(decodable),
            "lo_domain_size": st.size(lo_col) if lo_col in st.dom else 0,
        })
    return st


def seed_hash(images, anchors):
    """Deterministic seed identity for resume (no RNG/time)."""
    key = ("|".join(images.versions) + "|" + ",".join(f"{c}:{anchors[c]}" for c in sorted(anchors)))
    # simple stable digest without hashlib import noise
    h = 1469598103934665603
    for ch in key.encode():
        h = ((h ^ ch) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


# ------------------------------------------------------ Phase 5b: tiling narrowing
# Opcodes grouped by instruction length, illegal (0xA5) excluded from its length set (S1).
OPS_OF_LEN = {1: set(), 2: set(), 3: set()}
for _op in range(256):
    _info = instr_info(_op)
    if not _info.illegal:
        OPS_OF_LEN[_info.length].add(_op)


def k_set_for_length(cbyte, length):
    """K values that make ciphertext byte `cbyte` decode to a LEGAL opcode of `length`.
    Decode is a bijection K<->opcode (P=(cbyte-K)&0xFF), so this is a fixed-size set per length."""
    return {(cbyte - op) & 0xFF for op in OPS_OF_LEN[length]}


def _forced_length(sec, anchors, ranges, c):
    """At a KNOWN column treated as an opcode boundary: its forced length, or None if the tiling
    dies there (illegal opcode, or a fully-resolved abs target out of flash range = S1/S3)."""
    p = (sec[c] - anchors[c]) & 0xFF
    info = instr_info(p)
    if info.illegal:
        return None
    if info.kind in ("abs_jump", "abs_call") and (c + 1) in anchors and (c + 2) in anchors and c + 2 < SECTOR:
        hi = (sec[c + 1] - anchors[c + 1]) & 0xFF
        lo = (sec[c + 2] - anchors[c + 2]) & 0xFF
        if not any(lo0 <= ((hi << 8) | lo) <= hi0 for lo0, hi0 in ranges):
            return None
    return info.length


def tiling_roles(sec, anchors, seed, window_end, ranges):
    """One version. From a known boundary `seed`, compute over ALL legal instruction tilings up to
    `window_end`: (a) `bnd_len[col]` = lengths col takes as a boundary in some completable tiling,
    (b) `operand_cols` = cols that are an operand in some completable tiling. 8051 decode-from-a-
    boundary is context-free, so this is memoized reachability — O(window), exhaustive, no budget."""
    memo = {}

    def can_complete(c):
        if c > window_end:
            return True
        if c in memo:
            return memo[c]
        memo[c] = False                     # guard (no cycles forward, but safe)
        ok = False
        if c in anchors:
            fl = _forced_length(sec, anchors, ranges, c)
            ok = fl is not None and can_complete(c + fl)
        else:
            for L in (1, 2, 3):
                if OPS_OF_LEN[L] and can_complete(c + L):
                    ok = True
                    break
        memo[c] = ok
        return ok

    bnd_len = {}
    operand_cols = set()
    if not can_complete(seed):
        return bnd_len, operand_cols, False          # seed alignment impossible in this version
    seen = {seed}
    stack = [seed]
    while stack:
        c = stack.pop()
        if c > window_end:
            continue
        if c in anchors:
            lengths = [_forced_length(sec, anchors, ranges, c)]
            lengths = [x for x in lengths if x is not None and can_complete(c + x)]
        else:
            lengths = [L for L in (1, 2, 3) if OPS_OF_LEN[L] and can_complete(c + L)]
        for L in lengths:
            bnd_len.setdefault(c, set()).add(L)
            for o in range(c + 1, min(c + L, SECTOR)):
                operand_cols.add(o)
            nxt = c + L
            if nxt <= window_end and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return bnd_len, operand_cols, True


def narrow_from_seed(state, images, L, seed, ranges, window_end=513):
    """Phase 5b core: narrow K-domains on page L from a known boundary `seed`, per-version tilings
    intersected. A column is narrowed ONLY if it is a boundary in EVERY valid tiling of EVERY version
    (operand-escape => full domain). Returns {col: narrowed_size} for columns that actually shrank."""
    pv = images.page_versions(L)
    if not pv:
        return {}
    per_ver = []
    for sec in pv.values():
        bnd_len, operand_cols, ok = tiling_roles(sec, state.anchors, seed, window_end, ranges)
        if not ok:
            return {"__dead__": 0}          # seed impossible in a version -> whole seed rejected
        surv = {}
        for c in range(seed, window_end + 1):
            if c in state.anchors:
                continue
            if c in operand_cols:
                continue                    # operand in some tiling -> K unconstrained (full)
            if c in bnd_len:                # forced boundary (never operand) -> length-constrained
                ks = set()
                for Ln in bnd_len[c]:
                    ks |= k_set_for_length(sec[c], Ln)
                surv[c] = ks
        per_ver.append(surv)

    changed = {}
    cols = set().union(*[s.keys() for s in per_ver]) if per_ver else set()
    for c in cols:
        keep = None
        for surv in per_ver:
            ks = surv.get(c)               # absent => full (256) in that version
            if ks is None:
                continue
            keep = ks if keep is None else (keep & ks)
        if keep is not None:
            removed = state.prune(c, keep)
            if removed:
                changed[c] = state.size(c)
    return changed


def _branch_roles(pv, anchors, entry_col, ranges):
    """For one candidate ISR-entry (all versions of page pv), classify each body col in
    [entry_col, 513]: is it a forced boundary in EVERY version (never an operand), and if so its
    length-constrained K set (intersected across versions)? Returns (feasible, forced{col:kset},
    unconstrained_cols). `feasible` is False iff a version cannot tile from entry_col at all."""
    per_bnd, per_ops, secs = [], [], []
    for sec in pv.values():
        bnd, ops, ok = tiling_roles(sec, anchors, entry_col, 513, ranges)
        if not ok:
            return False, {}, set()
        per_bnd.append(bnd)
        per_ops.append(ops)
        secs.append(sec)
    forced, unconstrained = {}, set()
    for c in range(entry_col, SECTOR):
        if c in anchors:
            continue
        operand_any = any(c in ops for ops in per_ops)
        boundary_all = all(c in bnd for bnd in per_bnd)
        if boundary_all and not operand_any:
            ks = set(range(256))
            for i, bnd in enumerate(per_bnd):
                kv = set()
                for Ln in bnd[c]:
                    kv |= k_set_for_length(secs[i][c], Ln)
                ks &= kv
            forced[c] = ks
        else:
            unconstrained.add(c)
    return True, forced, unconstrained


def expand_frontier(state, images, config):
    """PHASE 5c — MRV frontier expansion. For each decodable vector target (hi known, lo unknown),
    sweep lo -> ISR-entry col, run the 5b tiling from that entry, and accumulate SOUND narrowing:
    a column narrows only if it is a forced boundary in EVERY alive lo-branch that reaches it AND
    unconstrained in none (the true lo is among the alive branches, so the domain is the UNION over
    them — operand-escape in any branch => full domain). Read-only; never writes ks_partial. Returns
    a measurement report."""
    ranges = config.flash_ranges
    report = {"vectors": [], "total_narrowed": 0}
    for node in state.frontier:
        if not node["decodable"]:
            continue
        L, hi = node["page"], int(node["target_hi"], 16)
        pv = images.page_versions(L)
        if not pv:
            continue
        alive = 0
        # per-col: union of forced K-sets over alive branches; and a flag if EVER unconstrained/unreached.
        union_forced, ever_loose = {}, set()
        for lo in range(256):
            Lx, entry_col = addr_to_col((hi << 8) | lo)
            if Lx != L or entry_col is None or not (2 <= entry_col <= 513):
                continue
            feasible, forced, unconstrained = _branch_roles(pv, state.anchors, entry_col, ranges)
            if not feasible:
                continue                          # this lo hard-refuted (S1/S3 at a known col)
            alive += 1
            for c in range(2, entry_col):         # cols before the entry are unreached by this branch
                ever_loose.add(c)
            for c in unconstrained:
                ever_loose.add(c)
            for c, ks in forced.items():
                union_forced[c] = union_forced.get(c, set()) | ks
        # SOUND narrowing: col c narrowable iff forced in EVERY alive branch (never loose) -> use union set
        changed = {}
        for c, ks in union_forced.items():
            if c in ever_loose:
                continue                          # loose in some alive branch => domain stays full
            if len(ks) < 256:
                removed = state.prune(c, ks)
                if removed:
                    changed[c] = state.size(c)
        report["vectors"].append({"vector": node["vector"], "page": L,
                                  "alive_lo": alive, "cols_narrowed": len(changed)})
        report["total_narrowed"] += len(changed)
    return report


# ------------------------------------------------------------------- CLI
def _kickoff(argv):
    cfg = S.SolverConfig()
    images, anchors = S.load(cfg)
    st = build_seed(images, anchors)
    sh = seed_hash(images, anchors)
    path = st.save(CHECKPOINT, sh)

    known = sum(1 for c in BODY if c in anchors)
    sizes = [st.size(c) for c in BODY]
    full = sum(1 for s in sizes if s == 256)
    dec = [f for f in st.frontier if f["decodable"]]
    print("RCIGD kickoff (PL_OMS Phase 5a) — RAM state seeded, snapshot written")
    print(f"  columns 2..513         : {len(list(BODY))}")
    print(f"  known (singleton dom)  : {known}")
    print(f"  full-domain (256) cols : {full}")
    print(f"  seed hash              : {sh}")
    print(f"  snapshot               : {path}")
    print(f"  entries (aligned seeds): {len(st.entries)}")
    for e in st.entries:
        print(f"      L{e['L']} col {e['col']:>3}  {e['kind']}  ({e['prov']})")
    print(f"  frontier (vector targets): {len(st.frontier)}  decodable-into-code-page: {len(dec)}")
    print(f"      {'vector':<12} {'hi':>5} {'page':>4} {'lo_col':>6} {'lo_dom':>6} decodable")
    for f in st.frontier:
        pg = "-" if f["page"] is None else f"L{f['page']}"
        print(f"      {f['vector']:<12} {str(f['target_hi']):>5} {pg:>4} "
              f"{f['lo_col']:>6} {f['lo_domain_size']:>6} {f['decodable']}")
    print("  NEXT: Phase 5b decode_forward (per-version, known-col checkpointed) -> first real narrowing.")
    return 0


def _decode(argv):
    """Phase 5b: narrow K-domains by tiling from the L=0 known boundaries. Read-only; snapshot only."""
    cfg = S.SolverConfig()
    images, anchors = S.load(cfg)
    st = build_seed(images, anchors)
    ranges = cfg.flash_ranges

    print("RCIGD decode (PL_OMS Phase 5b) — tiling-narrow from L=0 known boundaries")
    total_changed = {}
    for seed in (136,):                      # the first unknown-alignment boundary after the startup LJMP
        changed = narrow_from_seed(st, images, 0, seed, ranges)
        if changed.get("__dead__") is not None and "__dead__" in changed:
            print(f"  seed col {seed}: DEAD (a version cannot tile from here) — seed rejected")
            continue
        total_changed.update(changed)
        print(f"  seed col {seed}: narrowed {len(changed)} column(s)")

    if total_changed:
        sizes = sorted(total_changed.items())
        print(f"  columns narrowed below 256: {len(sizes)}")
        hist = {}
        for _c, s in sizes:
            bucket = "1" if s == 1 else ("2-16" if s <= 16 else ("17-64" if s <= 64 else "65-255"))
            hist[bucket] = hist.get(bucket, 0) + 1
        print(f"  domain-size histogram (narrowed cols): {hist}")
        tight = [(c, s) for c, s in sizes if s <= 32]
        if tight:
            print(f"  tightest domains (<=32): " + ", ".join(f"col{c}={s}" for c, s in tight[:20]))
        uniq = [c for c, s in sizes if s == 1]
        if uniq:
            print(f"  UNIQUE (size 1) cols: {uniq}  <- candidates for gated propose (NOT auto-written)")
    else:
        print("  no columns narrowed (operand-escape dominates from this seed) — expected without a")
        print("  denser known-column neighbourhood; deeper reach needs Phase 5c frontier expansion.")

    sh = seed_hash(images, anchors)
    path = st.save(CHECKPOINT, sh)
    print(f"  snapshot: {path}")
    return 0


def _frontier(argv):
    """Phase 5c: MRV frontier expansion over the vector-target ISR entries. Read-only; snapshot only."""
    cfg = S.SolverConfig()
    images, anchors = S.load(cfg)
    st = build_seed(images, anchors)
    narrow_from_seed(st, images, 0, 136, cfg.flash_ranges)     # fold in the 5b L0 narrowing first
    report = expand_frontier(st, images, cfg)

    print("RCIGD frontier (PL_OMS Phase 5c) — MRV expansion over vector-target ISR entries")
    print(f"  {'vector':<12} {'page':>4} {'alive_lo':>8} {'cols_narrowed':>13}")
    for v in report["vectors"]:
        print(f"  {v['vector']:<12} L{v['page']:<3} {v['alive_lo']:>8} {v['cols_narrowed']:>13}")
    print(f"  TOTAL columns hard-narrowed across all frontier vectors: {report['total_narrowed']}")
    below = [(c, st.size(c)) for c in BODY if c not in anchors and st.size(c) < 256]
    print(f"  columns below 256 (incl. 5b): {len(below)}"
          + (f"; tightest: " + ", ".join(f"col{c}={s}" for c, s in sorted(below, key=lambda x: x[1])[:10])
             if below else ""))
    if report["total_narrowed"] == 0:
        print("  => cross-page propagation adds NO sound narrowing: each vector target lands on another")
        print("     unknown-K region; operand-escape makes every col loose in some alive lo-branch.")
    sh = seed_hash(images, anchors)
    print(f"  snapshot: {st.save(CHECKPOINT, sh)}")
    return 0


def main(argv):
    import argparse
    p = argparse.ArgumentParser(description="RCIGD — recursive cross-version instruction-graph decode")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("kickoff", help="build + seed the RAM state, write the initial snapshot (Phase 5a)")
    sub.add_parser("decode", help="tiling-narrow K-domains from L=0 known boundaries (Phase 5b)")
    sub.add_parser("frontier", help="MRV frontier expansion over vector-target entries (Phase 5c)")
    a = p.parse_args(argv)
    if a.cmd == "kickoff":
        return _kickoff(argv)
    if a.cmd == "decode":
        return _decode(argv)
    if a.cmd == "frontier":
        return _frontier(argv)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
