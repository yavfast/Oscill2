# Implementation Plan: OFW Mask Solver  {#PL_OMS}

> **Code:** PL_OMS
> **Status:** completed
> **Created:** 2026-07-15
> **Updated:** 2026-07-15
>
> **Concept:** [C_OMS](./ofw_mask_solver.concept.md)
> **Specification:** [SP_OMS](./ofw_mask_solver.sp.md)
> **Depends on:** none (reuses `firmware/ofw_crypto.py`, `firmware/mask_lib.py`)
> **Used by:** —
>
> Build the offline `.ofw` mask solver in Python under `firmware/`: an MCS-51 decoder, a two-pass
> search (cross-version + page triage over all columns → anchor-seeded 8051 CSP on code pages), and a
> per-column determinability catalog with a gated promotion bridge. Bottom-up, each phase independently
> verifiable via a standalone test script.

## Goal

A runnable `firmware/ofw_mask_solver.py solve` that reads the 3 `.ofw` images + `ks_partial.json` and
writes `firmware/ks_solver_catalog.json` — a per-column verdict (`unique` / `variants` /
`undeterminable` / `rejected`) for all 512 keystream columns (req 3), using hard signals only. Success
is objectively pinned: the solver, with col 133 hidden from `ks_partial`, must re-derive `K[133]=0x29`
as `unique` (the byte already committed in §3f), and must return the trap slots (21/125/13/45) as
`variants` containing their `0x02`-derived keys — without ever writing the proven mask.

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3, stdlib only (`json`, `collections`, `sys`, `argparse`) | Matches the existing `firmware/` tooling (`ofw_crypto.py`, `mask_lib.py`); offline & deterministic; no new deps. |
| Module layout | `firmware/mcs51.py` (decoder) + `firmware/ofw_mask_solver.py` (solver + CLI) | Decoder is reusable and independently testable; keeps the solver focused. Function-oriented modules (PythonOneClassPerFile is `prefer`, satisfied). |
| Reuse | Import `mask_lib.load/L_map/logical_L/known_K`, `ofw_crypto.parse` | Cipher model + loading already proven; do not re-implement (Code Reuse). |
| Decoder table | Static hand-encoded MCS-51 256-entry table (SP_OMS_DEC_02) | Deterministic, auditable, zero dependency; `0xA5` = the one illegal opcode. |
| Search | Anchor-seeded bounded DFS (SP_OMS_DEC_03) | Tractable vs `256^n`; reproduces how §3f actually worked. |
| Tests | **Standalone scripts in `scripts/`** (import module, print PASS/FAIL, exit code), NOT pytest | Project rule `PythonTestsAreStandaloneScripts`; no pytest configured. |
| Catalog serialization | `json.dump(..., indent=1, sort_keys=True)`, no timestamps | Byte-identical reruns → determinism invariant (SP_OMS_05_02). |

## Required Knowledge

| Kind | Ref | Applies to | Note |
|------|-----|-----------|------|
| rule | PythonSnakeCaseForModulesAndFunctions (`must`) | all phases | modules/functions snake_case; constants UPPER_SNAKE |
| rule | PythonPrivateMethodUnderscore (`should`) | all phases | internal helpers `_prefixed` |
| rule | PythonTestsAreStandaloneScripts (`prefer`) | test scripts | standalone in `scripts/`, import + print; not pytest |
| rule | PythonOneClassPerFile (`prefer`) | Phase 1,4 | keep decoder/solver modules focused |
| skill (apply) | firmware_ofw_format (current) | all phases | cipher model, lattice, §3f LJMP grid, the §4 statistical trap — outranks generic crypto priors; hard-signals-only is binding |

## Progress

- [x] Phase 1 — MCS-51 decoder (`firmware/mcs51.py`; `scripts/test_mcs51.py` PASS)
- [x] Phase 2 — Loaders, config, Pass-1 triage (`scripts/test_ofw_solver_pass1.py` PASS)
- [x] Phase 3 — solve_window CSP + signals S1–S6 (`scripts/test_ofw_solver_window.py` PASS — §3f reproduced)
- [x] Phase 4 — Catalog, report, propose, full solve run (`scripts/test_ofw_solver_catalog.py` PASS; `firmware/ks_solver_catalog.json` produced)

## Phases

### Phase 1 — MCS-51 decoder (`firmware/mcs51.py`) [TODO]

**Depends on:** none
**Implements:** [SP_OMS_01_02](./ofw_mask_solver.sp.md#SP_OMS_01_02), [SP_OMS_02_05](./ofw_mask_solver.sp.md#SP_OMS_02_05)
**Verify:** [SP_OMS_05_01](./ofw_mask_solver.sp.md#SP_OMS_05_01) `instr_len` totality row (all 256 → {1,2,3}; `0x02`/`0x12`→3, `0x80`→2, `0x00`→1, `0xA5`.illegal). Phase-local: `scripts/test_mcs51.py` prints PASS/FAIL for the whole 256-map + a hand-checked decode of a known LJMP `02 hi lo`.

What to create:
| Entity | Module | Purpose |
|--------|--------|---------|
| `LEN_TABLE` (256 ints), `KIND_TABLE` | mcs51.py | canonical MCS-51 length/kind map |
| `instr_len(op)`, `instr_info(op)->Instr8051`, `decode_stream(plain,start)` | mcs51.py | totals over 0..255; greedy linear decode |

Notes:
- `Instr8051` = a small dataclass/namedtuple `(opcode, length, kind, illegal)`.
- `kind ∈ {abs_jump, abs_call, page_jump, page_call, rel_branch, other}` — only the branch/call kinds gate S3; everything else is `other`.

### Phase 2 — Loaders, config, Pass-1 triage (`firmware/ofw_mask_solver.py`) [TODO]

**Depends on:** Phase 1
**Implements:** [SP_OMS_01_01](./ofw_mask_solver.sp.md#SP_OMS_01_01), [SP_OMS_01_03](./ofw_mask_solver.sp.md#SP_OMS_01_03), [SP_OMS_02_02](./ofw_mask_solver.sp.md#SP_OMS_02_02), [SP_OMS_02_03](./ofw_mask_solver.sp.md#SP_OMS_02_03), [SP_OMS_03_01](./ofw_mask_solver.sp.md#SP_OMS_03_01)
**Verify:** [SP_OMS_05_03](./ofw_mask_solver.sp.md#SP_OMS_05_03) (anchors from ks_partial → `known` count == 107 on cols 2..513); [SP_OMS_03_01](./ofw_mask_solver.sp.md#SP_OMS_03_01) input-validation errors (E_NO_IMAGE / E_KS_INVALID). Phase-local: `scripts/test_ofw_solver_pass1.py` asserts classify: L=0→`code`, L=14..24→`erased-lattice`, L=10/11→`data-table`/`string`; cross-version: col 300→`varying`, an L=11 body col→`constant`.

What to implement:
- `SolverConfig` (defaults per 01_01), `_load(config)` → `(images, anchors)` reusing `mask_lib`; validation → typed errors.
- `classify_columns(images)` → cross-version class per col (02_02).
- `classify_pages(images, anchors)` → `{L: PageInfo}` with `page_class` + `entry_points` (02_03); L=0 entry_points = the vector-LJMP opcode cols (5+8n) + reset (col 2).

Pseudocode sketch:
    def classify_pages(images, anchors):
        for L, versions in logical_pages(images):
            if lattice_all_ff(L): cls = "erased-lattice"
            elif L == 0 or has_ljmp_grid(L): cls = "code"; seeds = ljmp_opcode_cols(L)
            elif printable_or_record_signature(L): cls = "string"|"data-table"
            else: cls = "mixed"

### Phase 3 — solve_window CSP + signals S1–S6 (`firmware/ofw_mask_solver.py`) [TODO]

**Depends on:** Phase 1, Phase 2
**Implements:** [SP_OMS_02_04](./ofw_mask_solver.sp.md#SP_OMS_02_04), [SP_OMS_03_02](./ofw_mask_solver.sp.md#SP_OMS_03_02)
**Verify:** [SP_OMS_05_01](./ofw_mask_solver.sp.md#SP_OMS_05_01) **§3f reproduction (the acceptance test)** — hide col 133 → `unique`=`0x29`; hide {21,125} → candidate set contains `0xc1`/`0xdf`; hide {13,45} → `variants` with both LJMP(`0x02`) and erased(`0xFF`) keys. [SP_OMS_05_02](./ofw_mask_solver.sp.md#SP_OMS_05_02) bound-independence of `unique`, exhaustiveness (`survivors+rejected==256`), signal monotonicity. Phase-local: `scripts/test_ofw_solver_window.py` runs the hide-and-recover harness on L=0.

What to implement:
- `solve_window(window, page, images, anchors, config)` — anchor-seeded DFS (02_04 pseudocode).
- Signals `_s1_illegal`, `_s2_tiles`, `_s3_operand_in_range` (uses `config.flash_ranges`), `_s4_valid_all_versions`, `_s6_anchor_consistent`.
- Node-budget guard → `W_BOUNDED`; zero-survivor+all-S6-fail → `W_ANCHOR_ANOMALY` (flag, never edit ks_partial).

Notes:
- The hide-and-recover harness is the core regression: remove a known col from `anchors`, run the window that contains it, assert the verdict/candidates match the committed §3f ground truth. This makes the spec's positive control executable.

### Phase 4 — Catalog, report, propose, full solve run (`firmware/ofw_mask_solver.py`) [TODO]

**Depends on:** Phase 1, Phase 2, Phase 3
**Implements:** [SP_OMS_01_04](./ofw_mask_solver.sp.md#SP_OMS_01_04), [SP_OMS_01_05](./ofw_mask_solver.sp.md#SP_OMS_01_05), [SP_OMS_01_06](./ofw_mask_solver.sp.md#SP_OMS_01_06), [SP_OMS_02_01](./ofw_mask_solver.sp.md#SP_OMS_02_01), [SP_OMS_02_06](./ofw_mask_solver.sp.md#SP_OMS_02_06), [SP_OMS_02_07](./ofw_mask_solver.sp.md#SP_OMS_02_07), [SP_OMS_04_01](./ofw_mask_solver.sp.md#SP_OMS_04_01) (verdict lifecycle realized in `finalize_verdicts`)
**Verify:** [SP_OMS_05_02](./ofw_mask_solver.sp.md#SP_OMS_05_02) determinism (two runs byte-identical) + `sha256(ks_partial.json)` unchanged; [SP_OMS_05_01](./ofw_mask_solver.sp.md#SP_OMS_05_01) happy path (512 records; summary sums to 512) + `propose_promotions` gated (no write); [SP_OMS_05_04](./ofw_mask_solver.sp.md#SP_OMS_05_04) edge cases (erased-lattice→`data-page`, <3-version page, window explosion→`search-bounded`). Phase-local: `scripts/test_ofw_solver_catalog.py`; then a real `solve` producing `firmware/ks_solver_catalog.json`.

What to implement:
- `finalize_verdicts`, `build_catalog` (01_04/01_06 invariants), deterministic `write_json`.
- `solve(config)` orchestration (02_01) wiring Pass-1 + Pass-2.
- `report(catalog)` (02_07) — verdict counts + `unique` list; `propose_promotions(catalog)` (02_06) — proposal list only, no `ks_partial` write.
- `argparse` CLI: `solve` / `report` / `propose`.

Notes:
- The real run is the deliverable artifact the user asked for. Cross-check its output against `ks_partial` (all 107 → `known`) and against §3f (col 133 shows `known` when present; the trap slots show `variants`).
- [SP_OMS_06_01](./ofw_mask_solver.sp.md#SP_OMS_06_01) **Reversibility** is satisfied by design across all phases (no implementation step): the tool is read-only on `.ofw`/`ks_partial`; the only writes are the deletable `ks_solver_catalog.json` + new modules; `propose_promotions` never writes the proven mask. No rollback code needed.

### Phase 5 — Recursive cross-version instruction-graph decode (RCIGD) [IN-PROGRESS 2026-07-16]

**Purpose.** Not to *prove* bytes but to **narrow per-column K-domains** (256 → few) by branch-and-bound
over instruction-alignment hypotheses, using the two hard rejections the user named — **illegal opcode**
(S1) and **out-of-range address** (S3) — plus cross-version coupling (S4). Output = a per-column candidate
map + ranked function-entry hypotheses, to seed later work. Accepts non-uniqueness (goal is fewer branches).

**Why this can prune where per-column cannot.** In isolation a column has *operand-escape* (any byte is a
legal operand) → no rejection. Rejection compounds only along an **assumed alignment chain**: from a known
instruction boundary, each opcode's length forces the next boundary; a branch dies when the chain (a) hits
an illegal opcode, (b) resolves an abs target out of `flash_ranges`, or (c) is forced to split a known-K
column's instruction inconsistently. The chain is seeded where alignment is known (L=0) and **propagates
across pages through resolved jump targets** (a jump's target is a new aligned entry).

**Cross-version coupling (the crux).** K is shared but `P[v][col]=C[v][col]−K[col]` differs per version, so
instruction boundaries **diverge per version** from a shared start. The single coupling is shared K: a
candidate value `k` at `col` is kept only if it yields a legal, boundary-consistent tiling in **every**
version carrying that page. Divergent versions therefore prune *more*, not less (this is what took §3f-region
decode-forward to floor-29 — the measured baseline this phase generalizes to all 10 code pages).

**State (RAM-resident; `DomainState`).**
- `dom[col]` for col 2..513: a set of surviving K values. Known cols → singleton; unknown → `{0..255}`.
- `boundaries[L][v]`: discovered instruction-boundary offsets per (page, version) (a hypothesis under a branch).
- `frontier`: unresolved jump targets `{page-hi known, lo-domain}` — the branch points (the 16 L0 vectors seed it).
- `entries`: confirmed aligned entry points (seed = L0 known boundaries; grows as targets resolve).
- Only **snapshots** are persisted (§ checkpoint); the live search tree stays in RAM.

**Algorithm (branch-and-bound + MRV).**
1. **Seed.** entries ← L0 known boundaries (reset chain col2→5, startup col133→136). frontier ← the 16 vector
   LJMP targets (`target-hi` from the lattice; `target-lo` domain = `dom[lo_col]`).
2. **Propagate (deterministic, no branch).** From each entry, run `decode_forward` per version: at each opcode
   boundary landing on a **known** col, its length is forced → advance; where the tiling crosses a known col
   as an operand, record no constraint; if a known col is required both as a mid-operand and as a boundary by
   different steps → contradiction → kill this branch. Intersect surviving `k` at each visited unknown opcode
   col across versions → prune `dom[col]`. Range-check every resolved abs target (S3); illegal-opcode check
   every boundary (S1).
3. **Branch (MRV).** Pick the frontier node with the **smallest `target-lo` domain**. For each candidate `lo`:
   set `K[lo_col]=lo` tentatively → target address concrete → new entry at `(page,off)`. Recurse from step 2
   in a bounded window (N instns or until RET/RETI). Keep `lo` iff the window stays legal+in-range in all
   versions; else drop it (prunes `dom[lo_col]`).
4. **Accumulate.** Union the K-assignments over all **surviving** branches → the narrowed `dom[col]` (a
   probabilistic prior, never a forced byte). Rank frontier `lo` candidates by surviving-branch count.
5. **Backtrack** on any emptied domain / range violation. **Terminate** on empty frontier, node-budget, or
   domain fixpoint.

**Hard invariants (carried from SP_OMS).** Never writes `ks_partial` (RCIGD output is a *separate* domain map);
a `unique`-width domain is *reported*, not auto-promoted; determinism (no RNG); read-only on `.ofw`.

**Checkpoint (intermediate results only).** `firmware/ks_graph_state.json` (git-ignored, regenerable): per-col
domain sizes + sets, frontier with lo-domains, live-branch stats, a seed/config hash for resume. Written every
K nodes and at exit; `kickoff` writes the seed snapshot. RAM is the working store; the file is a resumable snapshot.

**Staging.** 5a *(this turn)* — `DomainState` + seed + frontier + checkpoint I/O + `kickoff` (seed snapshot,
sound, runnable). 5b — the `decode_forward` per-version primitive with known-col checkpointing. 5c — MRV
frontier expansion + backtrack + accumulation. 5d — measure narrowed domains vs the floor-29 baseline; if a
domain reaches width 1 under strict S1/S3/S4 (not a statistical guess) it is proposed via the existing gated
`propose` path, never auto-written. Each of 5b–5d gets its own clean-context review before commit.

## Backlog

- ~~**Broader code-page seed discovery** (beyond L=0)~~ — **ACTIVATED as Phase 5 (RCIGD)** 2026-07-16.
- **Richer S5 data-page cribs** (register-name tables, additional LUTs beyond the two hex LUTs) — *Return when:* a specific data-page column becomes a target.
- **Re-run on new inputs** — a 4th firmware version (breaks OTP on varying cols) or a C2 known-page (adds anchors) — *Return when:* either becomes available.

## Design Decisions  {#PL_OMS_DEC}

### DEC_01 — v1 Pass-2 scope: which code pages get the deep search?  {#PL_OMS_DEC_01}

> **Status:** resolved · **Date:** 2026-07-15

**Question:** Pass-2 needs decode seeds (known instruction boundaries). Which code pages does v1 attack?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — L=0 only (guaranteed vector-LJMP seeds) | Tractable, well-defined, delivers the §3f reproduction + any L=0 gains; other code pages → `undeterminable(no-seed)`. |
| B — all code pages via phase-alignment brute force | Much larger search; most pages have no anchor to validate against → low yield, high cost. |
| C — follow L=0 LJMP targets into reachable pages | Needs target-lo (unknown K) to locate the entry precisely → not reliably resolvable in v1. |

**Decision:** A for v1; B/C deferred to backlog.
**Rationale:** Pass-1 already gives **every** column a verdict; Pass-2's real, validated yield is at L=0 (guaranteed seeds, where §3f succeeded). Minimality: ship the tractable, testable core; expand seed discovery only if L=0 is exhausted.
**Rejected because:** B explodes the search for little validated gain; C depends on unknown target-lo bytes.

## Implementation Notes (upstream corrections found during implement)

Two spec figures were adjusted to match verified reality (non-breaking; code was **not** bent to a wrong spec):

- **In-scope anchor count is 106, not 107.** `ks_partial.json` has 107 anchors *total*, but col 1 (SEQ)
  is explicitly out of catalog scope (SP_OMS §01: cols 0/1 excluded). So `meta.summary.known` and the
  cols-2..513 anchor count are **106** (107 = 106 + col 1). SP_OMS_05_03 / SP_OMS_01_06 wording corrected.
- **`data-page` per-column note is deferred (not emitted in v1).** The cipher is positional — a column
  spans all 59 logical pages — so a column has no single owning page. v1 attacks only L=0 (PL_OMS_DEC_01),
  so an un-attacked unknown column resolves to `undeterminable(no-signal)`; `search-bounded` is used when a
  window hits the node budget. The SP_OMS_05_04 erased-lattice edge case is honored at the **page** level:
  such pages classify as `erased-lattice` with empty `entry_points` (no attack, no false 0xFF harvest) — the
  test asserts this. `data-page` as a per-column reason returns when a future version attacks data pages.

**Real-run yield (deliverable `firmware/ks_solver_catalog.json`):** known=106, **unique=2** (col 21=`0xc1`
INT1, col 125=`0xdf` v15 — independently re-derived, matching the deferred §3f candidates), **variants=2**
(col 13 `{0xab LJMP, 0xae erased}`, col 45 `{0x06 LJMP, 0x09 erased}` — the ambiguous Tmr0/Tmr2),
undeterminable=402. Hiding col 133 re-derives it as `unique`=`0x29` (the acceptance test).

## Changelog

| Date | Change |
|------|--------|
| 2026-07-15 | Initial version. 4 bottom-up phases (decoder → triage → window CSP → catalog); tests as standalone scripts (project rule); §3f reproduction is the executable acceptance test; PL_OMS_DEC_01 scopes v1 Pass-2 to L=0 seeds. |
| 2026-07-15 | Implemented all 4 phases (`firmware/mcs51.py`, `firmware/ofw_mask_solver.py`; 4 standalone test scripts, all PASS). §3f reproduced (col 133→`unique` 0x29 when hidden; 21/125→`unique`, 13/45→`variants`). Catalog byte-deterministic; `ks_partial` sha256 unchanged. Two upstream corrections (106 in-scope anchors; `data-page` note deferred) — see Implementation Notes. Status → completed. |
| 2026-07-16 | Added **S-prologue** read-only diagnostic to the `jumps` command (symmetric to the existing S-epilogue), keyed by SDCC `--model-small` prologue conventions verified against `firmware/reference/ref0400.rst` (spike §3g). It emits **soft priors** (`0xC0` PUSH-ACC ISR ~60%, `0xAF` MOV-R7-DPL regular-fn) — **never** hard anchors, never promoted to `ks_partial` (SDCC has no reliable stack prologue: static overlay, not stack frames; optimizer drops leaf-ISR pushes). Outside the formal S1–S6 contracts, like `vectors`/`jumps`/S-epilogue (post-spec read-only diagnostics). Fires only on a column-mapped fn-start with an unknown entry column → **0 targets today** (only 0x0483 is mapped, a trampoline whose opcode is already known); loaded for the external levers. Test added to `test_ofw_solver_window.py`; all solver tests PASS. |
| 2026-07-16 | **Phase 5b implemented** (`firmware/ofw_graph_decode.py`: `tiling_roles` + `narrow_from_seed`, `decode` CLI). Sound linear tiling-narrowing — branch on instruction **length** (1/2/3), context-free reachability + memoized `can_complete`, no node budget. Cross-version intersection; a col narrows only if it is a boundary in **every** valid tiling of every version. **MEASURED from the only L=0 seed (col136): 5 cols narrowed, each by just 1 value (the illegal 0xA5) → 255/256. Negligible** — operand-escape dominates + the free-completing window leaves all lengths viable, so only S1 bites. (The prior "floor-29" needed a cross-version *shared-boundary* assumption — NOT sound in general; the sound version is weaker and confirms the wall harder.) Soundness test added (hidden known col's true K never removed) + controlled tiling-roles decode; all graph+solver tests PASS. Real narrowing now depends on Phase 5c (the 14 vector-target entries as extra boundary anchors + epilogue/prologue priors). |
| 2026-07-16 | **Phase 5c implemented + measured — RCIGD graph approach SOUNDLY REFUTED for file-only** (`expand_frontier`, `_branch_roles`, `frontier` CLI). MRV frontier expansion over the 14 decodable vector-target ISR entries: sweep each `target-lo` (256), run the 5b tiling from each candidate entry, accumulate narrowing with correct operand-escape union semantics (a col narrows only if a forced boundary in EVERY alive lo-branch reaching it). **Result: 3 cols hard-narrowed across all 14 vectors (each −1..−3 values); with 5b, 6 cols total, all still 253–255 candidates. alive_lo ≈ 254–256 (almost no target-lo refutable).** Cross-page jump-target propagation adds ~nothing: each target lands on another unknown-K region; operand-escape makes every col loose in some branch. Clean-context **soundness review: SOUND** (never removes a true K — all 5 claims verified). Test extended (`_branch_roles` + full `expand_frontier` run, determinism, known-cols-untouched); all 4 test files PASS. **Conclusion: the file-only graph does not collapse — 111/514 stands; only external levers remain (more versions / known page).** |
| 2026-07-16 | Extended S-prologue to **2-byte** patterns (spike §3g.4): each prior now predicts `P[entry],P[entry+1]` → two keystream bytes, tiered primary/secondary/variant (`AF 82`, `C0 E0`, `AE 83`, `AE 82`/`AD 82`). Added a **neighbour cross-check** — when `entry+1` is a known column the derived `K[entry+1]` is compared to the known byte → `validated`/`refuted` (a real filter: a wrong fn-start hypothesis at col13 is refuted by the lattice `K[14]`). Still soft/never-promoted, still 0 live targets. Test updated (2-byte structure + cross-check + arithmetic); all solver tests PASS. |
