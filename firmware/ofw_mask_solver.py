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

# C8051F340 interrupt names by vector index (0..15); slot 16 = the post-table startup LJMP.
IRQ_NAMES = ("INT0", "Tmr0", "INT1", "Tmr1", "UART0", "Tmr2", "SPI0", "SMB0",
             "v8", "ADC(v9)", "v10", "v11", "v12", "v13", "v14", "v15")


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


def _slot_is_written(opcode_col: int, pv: dict, span: int = 8) -> bool:
    """S4-family — a vector slot is 'written' (not erased) if ANY byte in its 8-byte span
    differs across versions. Erased flash is a constant 0xFF fill, so any cross-version
    variation proves the slot holds real content ⇒ the erased hypothesis is excluded ⇒ the
    opcode must be the written LJMP. (Doesn't fire when every slot byte is version-constant.)"""
    if len(pv) < 2:
        return False
    secs = list(pv.values())
    for c in range(opcode_col, min(opcode_col + span, SECTOR)):
        if len({sec[c] for sec in secs}) > 1:
            return True
    return False


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


def _target_class(hi):
    """Classify an LJMP target by its (known) high byte — the vendor's layout pattern."""
    if hi is None:
        return "unknown-hi"
    if 0x04 <= hi <= 0x7B:
        return "app-code"          # in the application flash region -> a used handler
    if hi == 0xFF:
        return "ff-ambiguous"      # LJMP 0xFFxx vs erased slot — hi=0xFF can't distinguish
    if 0xF0 <= hi <= 0xFE:
        return "boot-redirect"     # written non-FF high-flash target -> redirect to bootloader
    return "other"


def vector_table_analysis(images: LoadedImages, anchors: dict) -> list:
    """Automated L=0 vector-table walk (the systematized §3f procedure).

    For every slot (reset + 16 IRQ vectors + post-table LJMP) decode what is known —
    opcode plaintext (from anchors) and target-hi plaintext (the lattice anchor) — and
    classify the slot by its target region (app-code / boot-redirect / ff-ambiguous).
    Read-only; returns one dict per slot. This is the repeatable form of the manual
    vector sudoku: run it on any future image set to re-derive the disposition table.
    """
    ref = images.ref_bytes(0)
    if ref is None:
        return []
    pv = images.page_versions(0)

    def pval(col):
        return (ref[col] - anchors[col]) & 0xFF if col in anchors else None

    def lo_xver(col):
        """target-lo constancy across versions: CONST => layout-fixed target (may be pinnable),
        VARY => build-placed target (moved between firmware versions -> not file-determinable)."""
        vals = {sec[col] for sec in pv.values()}
        return "const" if len(vals) <= 1 else "vary"

    slots = [("reset", RESET_COL, RESET_COL + 1)]
    for n, name in enumerate(IRQ_NAMES):
        slots.append((name, 5 + 8 * n, 6 + 8 * n))
    slots.append(("post/startup", POST_TABLE_COL, POST_TABLE_COL + 1))

    out = []
    for name, opcol, hicol in slots:
        p_op = pval(opcol)
        # reset target-hi (col 3) is not on the lattice; every IRQ/post hi IS a lattice anchor.
        p_hi = pval(hicol)
        klass = _target_class(p_hi)
        is_ljmp = (p_op == LJMP_OPCODE)
        lo_col = opcol + 2
        out.append({
            "slot": name,
            "opcode_col": opcol,
            "opcode_P": _hex(p_op) if p_op is not None else None,
            "opcode": "LJMP" if is_ljmp else ("?" if p_op is None else _hex(p_op)),
            "hi_col": hicol,
            "target_hi": _hex(p_hi) if p_hi is not None else None,
            "target": f"0x{p_hi:02x}xx" if p_hi is not None else None,
            "class": klass,
            "opcode_known": opcol in anchors,
            "lo_col": lo_col,
            "lo_xver": lo_xver(lo_col),          # const => layout-fixed target; vary => build-placed
            "lo_known": lo_col in anchors,
        })
    return out


# 1-byte control-flow terminators — the ONLY terminators that fix a specific predecessor byte
# value (RET/RETI). Multi-byte terminators (LJMP/SJMP/AJMP/ACALL) end in an operand → any value.
TERMINATOR_OPCODES = {0x22: "RET", 0x32: "RETI"}
PADDING_FILLS = {0x00: "pad-00", 0xFF: "pad-FF"}
L0_LO, L0_HI = 0x0400, 0x05FF     # logical page 0 flash span


def _l0_addr_to_col(addr: int):
    """Map an absolute flash address in the L=0 page to its keystream column (or None)."""
    if L0_LO <= addr <= L0_HI:
        return (addr - L0_LO) + 2
    return None


def scan_jump_targets(images: LoadedImages, anchors: dict) -> list:
    """Scan the decoded L=0 code for LJMP/LCALL whose full target (hi AND lo) is known —
    i.e. the *addresses of other functions* reachable from what we've already opened. A fully
    resolved target is a known function-start address that the epilogue signal can then anchor
    on. Partially-resolved jumps (target-hi known, lo unknown) are reported as page-only."""
    rows = []
    ref = images.ref_bytes(0)
    if ref is None:
        return rows
    for slot in vector_table_analysis(images, anchors):
        if slot["opcode"] != "LJMP":
            continue
        hi = None if slot["target_hi"] is None else int(slot["target_hi"], 16)
        lo_col = slot["lo_col"]
        lo = (ref[lo_col] - anchors[lo_col]) & 0xFF if lo_col in anchors else None
        resolved = hi is not None and lo is not None
        rows.append({
            "from_slot": slot["slot"],
            "at_col": slot["opcode_col"],
            "target_hi": slot["target_hi"],
            "target": (f"0x{hi:02x}{lo:02x}" if resolved else
                       (f"0x{hi:02x}xx" if hi is not None else "?")),
            "resolved": resolved,
            "target_addr": ((hi << 8) | lo) if (hi is not None and lo is not None) else None,
        })
    return rows


def epilogue_candidates(images: LoadedImages, anchors: dict, target_addr: int) -> dict:
    """S-epilogue — given a KNOWN function-start address, the preceding byte is a control-flow
    terminator of the previous function (8051 packs functions back-to-back, no alignment pad).
    Returns {pred_col, candidates:[{K,P,basis}]} — a NARROW variants set {RET, RETI (+pad)}, NEVER
    a unique byte: picking one terminator would be a statistical guess (C_OMS_DEC_02, the §4 trap)."""
    target_col = _l0_addr_to_col(target_addr)
    if target_col is None or target_col <= 2:
        return {}
    pred_col = target_col - 1
    if pred_col in anchors:
        return {}                              # predecessor already known
    ref = images.ref_bytes(0)
    if ref is None:
        return {}
    c = ref[pred_col]
    cands = [{"K": _hex((c - p) & 0xFF), "P": _hex(p), "basis": f"prev-fn terminator {name}"}
             for p, name in {**TERMINATOR_OPCODES, **PADDING_FILLS}.items()]
    return {"pred_col": pred_col, "target_addr": target_addr, "candidates": cands}


# S-prologue PRIORS — the first *two* bytes of a function, keyed by SDCC --model-small conventions
# (verified against firmware/reference/ref0400.rst; see spike §3g). UNLIKE the vector-table LJMP
# (a hard S2/S3 anchor) these are STATISTICAL PRIORS, never hard-known plaintext: SDCC uses static
# overlay allocation (no stack frame), so regular functions start with a 2-byte param-load
# (MOV R7,DPL = AF 82 — 4/4 reference fns with a scalar 1st arg), and only NON-trivial ISRs push ACC
# (C0 E0) — the optimizer drops the push for leaf ISRs (held in only 3/7 reference ISRs). Emitting one
# as a `unique` K would be the §4 statistical trap (C_OMS_DEC_02). Each is a 2-byte pattern → predicts
# TWO keystream bytes; when the 2nd byte lands on a KNOWN column it becomes a hard validated/refuted
# cross-check (a real filter), but a "validated" prior is still NOT proof the fn uses that prologue.
# ((p0, p1), basis, confidence):
PROLOGUE_PRIORS_2B = (
    ((0xAF, 0x82), "MOV R7,DPL (regular fn, 1-byte 1st arg — SDCC default; 4/4 in ref)", "primary"),
    ((0xC0, 0xE0), "PUSH ACC (non-trivial ISR entry; 3/7 ISRs in ref)", "primary"),
    ((0xAE, 0x83), "MOV R6,DPH (regular fn, 2-byte int/ptr 1st arg, high half)", "secondary"),
    ((0xAE, 0x82), "MOV R6,DPL (1-byte 1st arg, alt R6 allocation)", "variant"),
    ((0xAD, 0x82), "MOV R5,DPL (1-byte 1st arg, alt R5 allocation)", "variant"),
)


def prologue_candidates(images: LoadedImages, anchors: dict, target_addr: int) -> dict:
    """S-prologue — given a KNOWN function-start address, the entry byte(s) follow an SDCC prologue
    convention. Returns {entry_col, priors:[{cols,K,P,basis,confidence,check?}]} — SOFT PRIORS for
    cross-checking only, NEVER promoted to ks_partial (symmetric to epilogue_candidates but even
    weaker: a prior, not a narrow variant set). Each prior is a 2-byte pattern → two (col,K) pairs;
    if the 2nd column is a known anchor the prior carries `check`=`validated`/`refuted` (the derived
    K matches / contradicts the known byte). Fires only for an L=0-local, not-yet-known entry column;
    the 2nd byte is emitted only while it stays inside the L=0 page. See spike §3g."""
    entry_col = _l0_addr_to_col(target_addr)
    if entry_col is None or entry_col <= 2:
        return {}
    if entry_col in anchors:
        return {}                              # entry byte already known (e.g. a trampoline LJMP)
    ref = images.ref_bytes(0)
    if ref is None:
        return {}
    c0 = ref[entry_col]
    col1 = entry_col + 1
    have_c1 = col1 < len(ref)                  # keep the 2nd byte inside the page
    priors = []
    for (p0, p1), basis, conf in PROLOGUE_PRIORS_2B:
        k0 = (c0 - p0) & 0xFF
        entry = {"cols": [entry_col], "K": [_hex(k0)], "P": [_hex(p0)],
                 "basis": basis, "confidence": conf}
        if have_c1:
            k1 = (ref[col1] - p1) & 0xFF
            entry["cols"].append(col1)
            entry["K"].append(_hex(k1))
            entry["P"].append(_hex(p1))
            if col1 in anchors:                # hard cross-check against a known neighbour
                entry["check"] = "validated" if anchors[col1] == k1 else "refuted"
        priors.append(entry)
    return {"entry_col": entry_col, "target_addr": target_addr, "priors": priors}


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
    slot_written = _slot_is_written(opcol, pv)      # any cross-version-varying slot byte ⇒ not erased

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
                # S4 — a cross-version-varying slot byte proves the slot is written, not erased.
                if slot_written:
                    rejected[k] = "S4"
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

    pv = sub.add_parser("vectors", help="L=0 vector-table disposition analysis (read-only)")
    pv.add_argument("--images", nargs="+")
    pv.add_argument("--ks")

    pj = sub.add_parser("jumps", help="scan opened code for jump targets + epilogue/prologue candidates (read-only)")
    pj.add_argument("--images", nargs="+")
    pj.add_argument("--ks")

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
        elif a.cmd == "vectors":
            cfg = _cfg_from_args(a)
            images, anchors = load(cfg)
            rows = vector_table_analysis(images, anchors)
            print("L=0 vector-table disposition (opcode + target-hi decoded from anchors):")
            print(f"  {'slot':<12} {'opCol':>5} {'opcode':>6} {'hiCol':>5} {'target':>8}  {'lo':>5}  class")
            counts = collections.Counter()
            lo_counts = collections.Counter()
            for r in rows:
                counts[r["class"]] += 1
                lo_counts[r["lo_xver"]] += 1
                print(f"  {r['slot']:<12} {r['opcode_col']:>5} {r['opcode']:>6} "
                      f"{r['hi_col']:>5} {str(r['target']):>8}  {r['lo_xver']:>5}  {r['class']}"
                      + ("" if r["opcode_known"] else "   (opcode unresolved)"))
            print("  target class: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
            print("  target-lo   : " + ", ".join(f"{k}={v}" for k, v in sorted(lo_counts.items()))
                  + "   (const => layout-fixed target, may be pinnable; vary => build-placed, not file-determinable)")
        elif a.cmd == "jumps":
            cfg = _cfg_from_args(a)
            images, anchors = load(cfg)
            rows = scan_jump_targets(images, anchors)
            resolved = [r for r in rows if r["resolved"]]
            print(f"jump/call targets found in opened L=0 code ({len(rows)} LJMP; {len(resolved)} fully resolved):")
            for r in rows:
                tag = "RESOLVED" if r["resolved"] else "page-only (lo unknown)"
                print(f"  {r['from_slot']:<12} @col {r['at_col']:>3} -> {r['target']:>8}  {tag}")
            print("\nS-epilogue (byte before a resolved function-start = prev-fn terminator):")
            any_ep = False
            for r in resolved:
                ep = epilogue_candidates(images, anchors, r["target_addr"])
                if not ep:
                    continue
                any_ep = True
                ks = ", ".join(f"{c['K']}({c['P']}={c['basis'].split()[-1]})" for c in ep["candidates"])
                print(f"  target {r['target']} (fn-start) -> col {ep['pred_col']} candidates: {ks}")
                print(f"    NOTE: variants only — choosing one terminator is a statistical guess (NOT promoted).")
            if not any_ep:
                print("  (no resolved target has an unknown, L=0-local predecessor)")
            print("\nS-prologue (2-byte SDCC prologue priors at a resolved function-start — spike §3g):")
            any_pr = False
            for r in resolved:
                pr = prologue_candidates(images, anchors, r["target_addr"])
                if not pr:
                    continue
                any_pr = True
                print(f"  target {r['target']} (fn-start) -> cols {pr['entry_col']}[,{pr['entry_col']+1}]:")
                for c in pr["priors"]:
                    pat = " ".join(f"{p[2:]}" for p in c["P"])            # e.g. "af 82"
                    kd = "->".join(f"K[{col}]={k}" for col, k in zip(c["cols"], c["K"]))
                    chk = f"  [{c['check'].upper()}]" if "check" in c else ""
                    print(f"      P={pat:<6} {kd:<26} {c['confidence']:<9} {c['basis']}{chk}")
                print(f"    NOTE: SOFT PRIORS only (SDCC has no reliable stack prologue) — cross-check, NEVER promoted."
                      f" A [REFUTED] prior is eliminated; [VALIDATED] is consistent, not proof.")
            if not any_pr:
                print("  (no resolved target has an unknown, L=0-local entry column)")
    except SolverError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
