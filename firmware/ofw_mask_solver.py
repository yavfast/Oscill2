#!/usr/bin/env python3
"""Offline `.ofw` keystream-mask solver — per-column determinability catalog.

Implements the two-pass search of C_OMS / SP_OMS:

  Pass 1  cross-version triage + logical-page classification (cheap, all columns).
  Pass 2  anchor-seeded 8051 constraint search on code pages (the yield). v1 attacks
          only L=0, the vector table, where the seeds are guaranteed (PL_OMS_DEC_01).

Every keystream column 2..513 gets a verdict — `known` / `unique` / `variants` /
`undeterminable` — using HARD structural signals only (S1 illegal opcode, S2 vector-slot
tiling, S3 operand range, S4 cross-version coherence, S6 anchor consistency). No
statistical acceptance (C_OMS_DEC_02 — the falsified §4 trap). The tool is read-only on
`.ofw` and `ks_partial.json`; it writes only the catalog. `propose_promotions` proposes
`unique` finds for `ks_partial` but never writes them (C_OMS_DEC_03 gated bridge).

CLI:  ofw_mask_solver.py solve   [--images ...] [--ks ...] [--out ...]
      ofw_mask_solver.py report  [--catalog ...]
      ofw_mask_solver.py propose [--catalog ...]

See docs/ofw_mask_solver.{concept,sp,plan}.md. Reuses firmware/ofw_crypto.py (parse) and
firmware/mask_lib.py (logical_L). All arithmetic is mod 256.
"""
# [C_OMS] OFW Mask Solver · [SP_OMS] contracts · [PL_OMS] plan
import argparse
import collections
import json
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mcs51                      # noqa: E402  (local module)
import ofw_crypto                 # noqa: E402
import mask_lib                   # noqa: E402

SECTOR = 514
TOTAL = SECTOR                    # mask length (514); catalog covers cols 2..513
FIRMWARE_DIR = os.path.dirname(os.path.abspath(__file__))

# L=0 vector-table geometry (app @ 0x0400; spike §3f). Reset LJMP at cols 2..4; IRQ vector
# n occupies an 8-byte slot with opcode col = 5+8n, target-hi col = 6+8n (a lattice anchor),
# target-lo col = 7+8n. C8051F340 = 16 IRQ vectors. col 133 = the post-table startup LJMP.
RESET_COL = 2
VECTOR_OPCODE_COLS = tuple(5 + 8 * n for n in range(16))
POST_TABLE_COL = 133
LJMP_OPCODE = 0x02
ERASED_FILL = 0xFF


def _is_lattice(col: int) -> bool:
    """True for the stride-8 offset-4 erased-flash lattice columns (0xFF background)."""
    return (col - 2) % 8 == 4


# ---------------------------------------------------------------------------- errors

class SolverError(Exception):
    """Typed abort (SP_OMS_02_01 / SP_OMS_03_01). `.code` is the spec error code."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


# ---------------------------------------------------------------------------- config

@dataclass
class SolverConfig:
    """Run parameters (SP_OMS_01_01). All defaulted → the tool runs with zero arguments."""
    images: list = field(default_factory=lambda: ["Uosc123.ofw", "Uosc125.ofw", "Uosc126.ofw"])
    ks_partial_path: str = "ks_partial.json"
    catalog_out: str = "ks_solver_catalog.json"
    flash_ranges: list = field(default_factory=lambda: [[0x0400, 0x7BFF], [0xF000, 0xFFFF]])
    search_bound: int = 200000
    max_window: int = 64

    def _validate(self):
        if not self.images:
            raise SolverError("E_NO_IMAGE", "no images configured")
        if self.search_bound < 1:
            raise SolverError("E_CONFIG", "search_bound must be >= 1")
        if self.max_window < 8:
            raise SolverError("E_CONFIG", "max_window must be >= 8")
        if not self.flash_ranges:
            raise SolverError("E_CONFIG", "flash_ranges must be non-empty")
        for r in self.flash_ranges:
            if len(r) != 2 or not (0 <= r[0] <= r[1] <= 0xFFFF):
                raise SolverError("E_CONFIG", f"malformed flash range {r}")


# --------------------------------------------------------------------- loaded images

@dataclass
class LoadedImages:
    """Parsed `.ofw` set organised by logical page (SP_OMS-internal)."""
    versions: list                       # image basenames, in config order
    pages: dict                          # {L -> {version -> sector bytes (514)}}

    def page_versions(self, L):
        return self.pages.get(L, {})

    def ref_bytes(self, L):
        """First version (config order) carrying page L, or None."""
        pv = self.pages.get(L, {})
        for v in self.versions:
            if v in pv:
                return pv[v]
        return None


# ---------------------------------------------------------------------- 01_03 PageInfo

@dataclass
class PageInfo:
    L: object                            # int 0..58 or "E"
    versions: list
    page_class: str                      # code | data-table | string | erased-lattice | mixed
    entry_points: list                   # known instruction-boundary seeds (opcode cols)


# ------------------------------------------------------------------------------ load

def _resolve(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(FIRMWARE_DIR, path)


def _load_images(config: SolverConfig) -> LoadedImages:
    pages = {}
    versions = []
    for name in config.images:
        path = _resolve(name)
        if not os.path.isfile(path):
            raise SolverError("E_NO_IMAGE", f"image not found: {path}")
        try:
            with open(path, "rb") as fh:
                parsed = ofw_crypto.parse(fh.read())
        except ValueError as e:
            raise SolverError("E_NO_IMAGE", f"{name}: {e}")
        payload = parsed["payload"]
        if not payload or len(payload) % SECTOR != 0:
            raise SolverError("E_NO_IMAGE", f"{name}: payload length {len(payload)} not a multiple of {SECTOR}")
        base = os.path.basename(name)
        versions.append(base)
        n = len(payload) // SECTOR
        for i in range(n):
            sec = payload[i * SECTOR:(i + 1) * SECTOR]
            L = mask_lib.logical_L(sec)
            pages.setdefault(L, {})[base] = sec
    return LoadedImages(versions=versions, pages=pages)


def _load_anchors(config: SolverConfig) -> dict:
    path = _resolve(config.ks_partial_path)
    if not os.path.isfile(path):
        raise SolverError("E_KS_INVALID", f"ks_partial not found: {path}")
    try:
        with open(path) as fh:
            raw = json.load(fh)
    except (ValueError, OSError) as e:
        raise SolverError("E_KS_INVALID", f"ks_partial unreadable: {e}")
    known = raw.get("known", raw) if isinstance(raw, dict) else None
    if not isinstance(known, dict):
        raise SolverError("E_KS_INVALID", "ks_partial is not a {col: K} map")
    anchors = {}
    for k, v in known.items():
        try:
            col = int(k)
            val = int(v, 16) if isinstance(v, str) else int(v)
        except (ValueError, TypeError):
            raise SolverError("E_KS_INVALID", f"bad ks_partial entry {k!r}: {v!r}")
        if not (0 <= col <= 513) or not (0 <= val <= 255):
            raise SolverError("E_KS_INVALID", f"out-of-range ks_partial entry {col}={val}")
        anchors[col] = val
    return anchors


def load(config: SolverConfig):
    """Validate config, parse images, load anchors. -> (LoadedImages, anchors dict)."""
    config._validate()
    images = _load_images(config)
    anchors = _load_anchors(config)
    return images, anchors


# -------------------------------------------------------------- 02_02 classify_columns

def classify_columns(images: LoadedImages) -> dict:
    """Pass-1 cross-version class per column (SP_OMS_02_02).

    `constant` iff the ciphertext is equal across the versions carrying the page on EVERY
    shared page; `varying` iff it differs on any; `n/a` iff no page carries >=2 versions.
    (For the 3 shipped images every column varies on at least one page — see PL_OMS note.)
    """
    shared = [L for L, pv in images.pages.items() if len(pv) >= 2]
    out = {}
    for col in range(2, SECTOR):
        comparable = False
        varying = False
        for L in shared:
            pv = images.pages[L]
            comparable = True
            vals = {sec[col] for sec in pv.values()}
            if len(vals) > 1:
                varying = True
                break
        if not comparable:
            out[col] = "n/a"
        else:
            out[col] = "varying" if varying else "constant"
    return out


def page_is_version_constant(images: LoadedImages, L) -> bool:
    """True iff page L is byte-identical across all versions carrying it (>=2)."""
    pv = images.pages.get(L, {})
    if len(pv) < 2:
        return False
    first = next(iter(pv.values()))
    return all(sec == first for sec in pv.values())


# --------------------------------------------------------------- 02_03 classify_pages

def _printable_run(ref: bytes, anchors: dict) -> int:
    """Longest run of consecutive anchored columns that decrypt to printable ASCII."""
    best = run = 0
    for col in range(2, SECTOR):
        if col in anchors:
            p = (ref[col] - anchors[col]) & 0xFF
            if 0x20 <= p < 0x7F:
                run += 1
                best = max(best, run)
                continue
        run = 0
    return best


def _lattice_all_ff(ref: bytes, anchors: dict) -> bool:
    """True iff every anchored lattice column on this page decrypts to 0xFF (erased)."""
    latt = [c for c in range(2, SECTOR) if _is_lattice(c) and c in anchors]
    if not latt:
        return False
    return all(((ref[c] - anchors[c]) & 0xFF) == 0xFF for c in latt)


def _is_vector_code_page(L, pv: dict, anchors: dict) -> bool:
    """Hard test for the L=0 vector table: reset col decodes to LJMP in every version."""
    if L != 0 or RESET_COL not in anchors:
        return False
    return all(((sec[RESET_COL] - anchors[RESET_COL]) & 0xFF) == LJMP_OPCODE
               for sec in pv.values())


def classify_pages(images: LoadedImages, anchors: dict) -> dict:
    """Assign each logical page a page_class + entry-point seeds (SP_OMS_02_03)."""
    result = {}
    for L, pv in images.pages.items():
        ref = images.ref_bytes(L)
        versions = [v for v in images.versions if v in pv]
        if ref is None:
            result[L] = PageInfo(L=L, versions=versions, page_class="mixed", entry_points=[])
            continue
        if _is_vector_code_page(L, pv, anchors):
            entries = [RESET_COL] + list(VECTOR_OPCODE_COLS) + [POST_TABLE_COL]
            cls = "code"
        elif _lattice_all_ff(ref, anchors):
            cls, entries = "erased-lattice", []
        elif _printable_run(ref, anchors) >= 8:
            cls, entries = "data-table", []
        else:
            cls, entries = "mixed", []
        result[L] = PageInfo(L=L, versions=versions, page_class=cls, entry_points=entries)
    return result


# ----------------------------------------------------------------- signals (S1..S6)

def _log_bounded(L, col, reason: str):
    """SP_OMS_03_02 — no silent truncation: a bounded window logs its cap to stderr."""
    print(f"[W_BOUNDED] L{L} col {col}: {reason} -> undeterminable(search-bounded)", file=sys.stderr)


def _hi_in_ranges(p_hi: int, flash_ranges) -> bool:
    """S3 helper — is target-hi byte within any flash range (some low byte makes it valid)?"""
    return any((lo >> 8) <= p_hi <= (hi >> 8) for lo, hi in flash_ranges)


def _s4_all_versions(col: int, k: int, expected_p: int, pv: dict) -> bool:
    """S4 — the shared key k must yield `expected_p` in EVERY version carrying the page."""
    return all(((sec[col] - k) & 0xFF) == expected_p for sec in pv.values())


# ----------------------------------------------------------- 02_04 window CSP core

def windows_of(page: PageInfo, anchors: dict) -> list:
    """Anchor-bounded windows on a code page — one per vector slot whose target-hi is a
    known lattice anchor (the bound). v1: only L=0 vector slots (PL_OMS_DEC_01)."""
    if page.page_class != "code":
        return []
    windows = []
    for opcol in page.entry_points:
        hicol = opcol + 1
        if hicol not in anchors:          # need the target-hi anchor to bound/decode the slot
            continue
        windows.append({
            "page": page.L,
            "opcode_col": opcol,
            "hi_col": hicol,
            "cols_unknown": [opcol] if opcol not in anchors else [],
            "anchors_in_span": {hicol: anchors[hicol]},
        })
    return windows


def solve_window(window: dict, page: PageInfo, images: LoadedImages, anchors: dict,
                 config: SolverConfig, node_counter: list) -> dict:
    """Pass-2 core (SP_OMS_02_04) — recover/bound one code window's unknown opcode column.

    v1 realization (PL_OMS_DEC_01, L=0 vector table): the general anchor-seeded DFS over
    instruction boundaries collapses to a depth-1 search per 8-byte vector slot, because
    the target-hi lattice anchor at `col+1` bounds the slot immediately. Each candidate `k`
    is tested exhaustively (0..255): the decrypted opcode is decoded via `mcs51.instr_info`
    and must be a *written vector LJMP* (`kind == abs_jump`, whose S3 target lands in flash)
    or an *erased slot* (0xFF fill, whose S2 tiling requires the known target-hi to be 0xFF).
    Anything else fails S2. S4 enforces the shared key across all versions; S6 forbids
    contradicting a known anchor.

    Returns {col -> {"survivors": {k: {"P", "basis"}}, "rejected": {k: reason}, "bounded"}}.
    Raises SolverError('W_ANCHOR_ANOMALY', ...) if zero fills survive at a hidden column.
    """
    out = {}
    pv = images.page_versions(page.L)
    ref = images.ref_bytes(page.L)
    if ref is None:
        return out
    opcol = window["opcode_col"]
    hicol = window["hi_col"]
    p_hi = (ref[hicol] - anchors[hicol]) & 0xFF     # target-hi plaintext (known lattice anchor)
    slot = f"slot{(opcol - 5) // 8}" if opcol in VECTOR_OPCODE_COLS else "post-table"

    # max_window: a window spanning more unknown columns than the cap is declared bounded
    # without search (SP_OMS_01_01 / 03_01). For a single anchor-bounded slot the span is 1.
    span = (max(window["cols_unknown"]) - min(window["cols_unknown"]) + 1) if window["cols_unknown"] else 0
    if span > config.max_window:
        for col in window["cols_unknown"]:
            _log_bounded(page.L, col, f"span {span} > max_window {config.max_window}")
            out[col] = {"survivors": {}, "rejected": {}, "bounded": True}
        return out

    for col in window["cols_unknown"]:
        survivors, rejected = {}, {}
        bounded = False
        for k in range(256):
            node_counter[0] += 1
            if node_counter[0] > config.search_bound:
                bounded = True
                _log_bounded(page.L, col, f"node budget {config.search_bound} exceeded")
                break
            p_op = (ref[col] - k) & 0xFF
            info = mcs51.instr_info(p_op)
            # S1 — illegal opcode (0xA5)
            if info.illegal:
                rejected[k] = "S1"
                continue
            if info.kind == "abs_jump":
                # written vector LJMP: 3-byte instruction tiling the 8-byte slot; its target-hi
                # operand lands on the known lattice anchor (col+1) and reproduces it (S2 tiling).
                # S3 — LJMP target (hi known) must fall inside a flash range.
                if not _hi_in_ranges(p_hi, config.flash_ranges):
                    rejected[k] = "S3"
                    continue
                # S4 — shared k must decode to the SAME opcode in every version.
                if not _s4_all_versions(col, k, p_op, pv):
                    rejected[k] = "S4"
                    continue
                # S6 — must not contradict a known anchor.
                if col in anchors and k != anchors[col]:
                    rejected[k] = "S6"
                    continue
                survivors[k] = {"P": p_op,
                                "basis": f"LJMP(abs_jump) @L{page.L} {slot}; target-hi {p_hi:#04x} "
                                         f"in flash range; xver ok [assumes vector slot = LJMP|erased]"}
            elif p_op == ERASED_FILL:
                # erased slot: whole slot is 0xFF ⇒ S2 tiling requires the known target-hi = 0xFF.
                if p_hi != ERASED_FILL:
                    rejected[k] = "S2"
                    continue
                if not _s4_all_versions(col, k, ERASED_FILL, pv):
                    rejected[k] = "S4"
                    continue
                if col in anchors and k != anchors[col]:
                    rejected[k] = "S6"
                    continue
                survivors[k] = {"P": ERASED_FILL,
                                "basis": f"erased-fill @L{page.L} {slot} (target-hi 0xFF); xver ok "
                                         f"[assumes vector slot = LJMP|erased]"}
            else:
                # S2 — a vector slot's opcode must be a written LJMP (abs_jump) or an erased 0xFF fill.
                rejected[k] = "S2"
        if not bounded and not survivors and col not in anchors:
            # zero fills survived a hidden column → page mis-class or suspect anchor. Flag; never edit ks_partial.
            raise SolverError("W_ANCHOR_ANOMALY",
                              f"col {col} on L{page.L}: no fill survives S1-S6 (page mis-class or suspect anchor)")
        out[col] = {"survivors": survivors, "rejected": rejected, "bounded": bounded}
    return out


# ----------------------------------------------------------- verdict aggregation

def _hex(v: int) -> str:
    return f"0x{v & 0xFF:02x}"


def _seed_record(col: int, anchors: dict, colclass: dict) -> dict:
    """Initial per-column record before Pass-2 (SP_OMS_04_01 [unknown]/[known])."""
    if col in anchors:
        return {"col": col, "verdict": "known", "value": _hex(anchors[col]),
                "cross_version": colclass.get(col, "n/a"), "page_class": "mixed",
                "attacked_on": [], "candidates": None, "rejected": [], "notes": ""}
    return {"col": col, "verdict": "undeterminable", "value": None,
            "cross_version": colclass.get(col, "n/a"), "page_class": "mixed",
            "attacked_on": [], "candidates": "unconstrained", "rejected": [],
            "notes": "no-signal"}


def _merge_window(result: dict, page: PageInfo, records: dict):
    """Fold a solve_window result into the per-column records (union of survivors)."""
    for col, r in result.items():
        rec = records[col]
        if col not in rec["attacked_on"]:
            rec["attacked_on"].append(page.L)
        rec["page_class"] = page.page_class
        if r["bounded"]:
            rec["verdict"] = "undeterminable"
            rec["value"] = None
            rec["candidates"] = "unconstrained"
            rec["notes"] = "search-bounded"
            continue
        survivors, rejected = r["survivors"], r["rejected"]
        cands = [{"K": _hex(k), "P": _hex(v["P"]), "basis": v["basis"]}
                 for k, v in sorted(survivors.items())]
        rec["candidates"] = cands
        rec["rejected"] = [{"K": _hex(k), "reason": reason} for k, reason in sorted(rejected.items())]
        rec["notes"] = ""
        if len(survivors) == 1:
            rec["verdict"] = "unique"
            rec["value"] = cands[0]["K"]
        elif len(survivors) >= 2:
            rec["verdict"] = "variants"
            rec["value"] = None
        else:
            rec["verdict"] = "undeterminable"
            rec["value"] = None
            rec["notes"] = "no-signal"


def finalize_verdicts(records: dict, anchors: dict):
    """Enforce the SP_OMS_01_04 invariants (known never overwritten; value/candidate shape)."""
    for col, rec in records.items():
        if col in anchors:
            rec["verdict"] = "known"
            rec["value"] = _hex(anchors[col])
            rec["candidates"] = None
            # keep any rejected/basis as corroboration context, but a known byte is authoritative


# ------------------------------------------------------------------ 02_01 solve

def solve(config: SolverConfig) -> dict:
    """Run both passes and write the catalog (SP_OMS_02_01). Returns the catalog dict."""
    images, anchors = load(config)
    colclass = classify_columns(images)
    pages = classify_pages(images, anchors)

    records = {col: _seed_record(col, anchors, colclass) for col in range(2, SECTOR)}
    node_counter = [0]
    anomalies = []
    for page in sorted(pages.values(), key=lambda p: (p.L == "E", p.L)):
        if page.page_class != "code":
            continue
        for window in windows_of(page, anchors):
            try:
                result = solve_window(window, page, images, anchors, config, node_counter)
            except SolverError as e:
                if e.code == "W_ANCHOR_ANOMALY":
                    anomalies.append(str(e))
                    continue
                raise
            _merge_window(result, page, records)

    finalize_verdicts(records, anchors)
    catalog = build_catalog(records, config, images, anchors, anomalies)
    write_json(_resolve(config.catalog_out), catalog)
    return catalog


# ------------------------------------------------------------- 01_06 build_catalog

def build_catalog(records: dict, config: SolverConfig, images: LoadedImages,
                  anchors: dict, anomalies=None) -> dict:
    summary = collections.Counter(rec["verdict"] for rec in records.values())
    ks_n = sum(1 for c in anchors if 2 <= c <= 513)
    meta = {
        "tool": "ofw_mask_solver",
        "generated_from": list(images.versions),
        "ks_partial_n": ks_n,
        "total": TOTAL,
        "search_bound": config.search_bound,
        "flash_ranges": [[r[0], r[1]] for r in config.flash_ranges],
        "summary": {
            "known": summary.get("known", 0),
            "unique": summary.get("unique", 0),
            "variants": summary.get("variants", 0),
            "undeterminable": summary.get("undeterminable", 0),
        },
    }
    n_bounded = sum(1 for rec in records.values() if rec.get("notes") == "search-bounded")
    if n_bounded:
        meta["search_bounded"] = n_bounded
    if anomalies:
        meta["anomalies"] = list(anomalies)
    return {"meta": meta, "columns": {str(c): records[c] for c in sorted(records)}}


def write_json(path: str, catalog: dict):
    """Deterministic serialization — no timestamps (SP_OMS_05_02)."""
    with open(path, "w") as f:
        json.dump(catalog, f, indent=1, sort_keys=True)
        f.write("\n")


# --------------------------------------------------- 02_06 propose_promotions

def propose_promotions(catalog: dict, anchors: dict) -> list:
    """Gated bridge (SP_OMS_02_06) — list `unique` cols not already in ks_partial. No write."""
    proposals = []
    for col_s, rec in catalog["columns"].items():
        if rec["verdict"] != "unique":
            continue
        col = int(col_s)
        value = int(rec["value"], 16)
        if col in anchors:
            # a unique that disagrees with a known anchor is an anomaly (impossible if S6 held).
            if anchors[col] != value:
                raise SolverError("P_CONTRADICTS_KNOWN", f"col {col} unique {rec['value']} contradicts anchor")
            continue    # already a known byte — not a fresh promotion
        basis = rec["candidates"][0]["basis"] if isinstance(rec["candidates"], list) and rec["candidates"] else ""
        proposals.append({"col": col, "value": rec["value"], "basis": basis})
    return proposals


# --------------------------------------------------------------- 02_07 report

def report(catalog: dict) -> str:
    """Render the catalog as a human-readable summary (SP_OMS_02_07). Read-only."""
    m = catalog["meta"]
    s = m["summary"]
    lines = [
        f"OFW mask solver catalog — {m['tool']}",
        f"  images        : {', '.join(m['generated_from'])}",
        f"  columns 2..513: {sum(s.values())}   (ks_partial anchors: {m['ks_partial_n']})",
        f"  known={s['known']}  unique={s['unique']}  variants={s['variants']}  undeterminable={s['undeterminable']}",
    ]
    if m.get("anomalies"):
        lines.append(f"  ANOMALIES     : {len(m['anomalies'])}")
        for a in m["anomalies"]:
            lines.append(f"    ! {a}")
    uniq = [(int(c), r) for c, r in catalog["columns"].items() if r["verdict"] == "unique"]
    if uniq:
        lines.append(f"  unique finds ({len(uniq)}):")
        for col, r in sorted(uniq):
            basis = r["candidates"][0]["basis"] if isinstance(r["candidates"], list) and r["candidates"] else ""
            lines.append(f"    col {col:>3} = {r['value']}   {basis}")
    var = [(int(c), r) for c, r in catalog["columns"].items() if r["verdict"] == "variants"]
    if var:
        lines.append(f"  variants ({len(var)}):")
        for col, r in sorted(var):
            ks = ",".join(cd["K"] for cd in r["candidates"]) if isinstance(r["candidates"], list) else "?"
            lines.append(f"    col {col:>3} : {{{ks}}}")
    und = collections.Counter(r["notes"] or "?" for r in catalog["columns"].values()
                              if r["verdict"] == "undeterminable")
    if und:
        lines.append("  undeterminable by reason: " + ", ".join(f"{k}={v}" for k, v in sorted(und.items())))
    return "\n".join(lines)


# ------------------------------------------------------------------------ CLI

def _cfg_from_args(a) -> SolverConfig:
    cfg = SolverConfig()
    if a.images:
        cfg.images = a.images
    if a.ks:
        cfg.ks_partial_path = a.ks
    if getattr(a, "out", None):
        cfg.catalog_out = a.out
    if getattr(a, "search_bound", None):
        cfg.search_bound = a.search_bound
    return cfg


def main(argv):
    p = argparse.ArgumentParser(description="Offline .ofw keystream-mask solver")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("solve", help="run both passes, write the catalog")
    ps.add_argument("--images", nargs="+")
    ps.add_argument("--ks")
    ps.add_argument("--out")
    ps.add_argument("--search-bound", type=int, dest="search_bound")

    pr = sub.add_parser("report", help="render an existing catalog")
    pr.add_argument("--catalog", default="ks_solver_catalog.json")

    pp = sub.add_parser("propose", help="propose unique finds for ks_partial (no write)")
    pp.add_argument("--catalog", default="ks_solver_catalog.json")
    pp.add_argument("--ks")

    a = p.parse_args(argv)
    try:
        if a.cmd == "solve":
            cfg = _cfg_from_args(a)
            catalog = solve(cfg)
            print(report(catalog))
            print(f"\nwrote catalog -> {_resolve(cfg.catalog_out)}")
        elif a.cmd == "report":
            with open(_resolve(a.catalog)) as fh:
                catalog = json.load(fh)
            print(report(catalog))
        elif a.cmd == "propose":
            with open(_resolve(a.catalog)) as fh:
                catalog = json.load(fh)
            cfg = SolverConfig()
            if a.ks:
                cfg.ks_partial_path = a.ks
            anchors = _load_anchors(cfg)
            proposals = propose_promotions(catalog, anchors)
            print(f"{len(proposals)} promotion proposal(s) (ks_partial NOT modified):")
            for pr_ in proposals:
                print(f"  col {pr_['col']:>3} = {pr_['value']}   {pr_['basis']}")
    except SolverError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
