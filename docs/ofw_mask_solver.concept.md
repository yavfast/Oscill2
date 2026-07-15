# OFW Mask Solver — automated per-column keystream candidate search  {#C_OMS}

> **Code:** C_OMS
> **Status:** draft
> **Created:** 2026-07-15
> **Updated:** 2026-07-15
> **Author:** claude-opus-4-8
> **Owner:** firmware-RE tooling (offline analysis; not part of the shipped app)
> **Complexity:** medium — needs an 8051 instruction-length decoder + a bounded constraint search, but no runtime/hardware coupling
>
> **Depends on:** `firmware/ofw_crypto.py` (cipher model), `firmware/mask_lib.py` (load / L-map / known-K)
> **Used by:** —
> **Spike:** [ofw_mask_cryptanalysis.spike.md](./ofw_mask_cryptanalysis.spike.md)
> **Specification:** [SP_OMS](./ofw_mask_solver.sp.md)
> **Plan:** [ofw_mask_solver.plan.md](./ofw_mask_solver.plan.md)
>
> An offline tool that, for every keystream column whose byte is not yet known, exhaustively
> enumerates candidate values, prunes them through **hard structural signals only** (8051 opcode-stream
> tiling, operand ranges, cross-version coherence, known cribs), and writes a per-column **determinability
> catalog**: unique value found · surviving variants · undeterminable · rejected-with-reason. It
> systematizes and completes the manual "sudoku" of the spike; it does **not** break the
> information-theoretic barrier the spike proved.

## 1. Philosophy  {#C_OMS_01}

### 1.1. Core Principle  {#C_OMS_01_01}

The `.ofw` keystream `K` (514 bytes, additive, shared across all 180 sectors) is **107/514 recovered**
and — with C2-readback locked (spike §5.1) — file-only analysis is the only non-invasive path. Prior
recovery was **manual and ad hoc** (lattice mode, hex-LUT cribs, the L=0 LJMP grid). This concept turns
that into a **repeatable, exhaustive, disciplined program** with three jobs, matching the request:

1. For each unknown column, produce the **list/range of candidate bytes** (§C_OMS_03_02).
2. **Verify** candidates by hard signals — 8051 opcodes on code segments, plus other structural signals (§C_OMS_03_03).
3. Emit, **per column**, a result record: unique found value · possible variants · undeterminable · rejected-and-why (§C_OMS_03_04).

**Honest yield (set expectations, not a "just in case" promise).** The cipher is *positional* (columns
independent), so most unanchored columns are information-theoretically undeterminable from 3 images —
this is proven, not pessimism (spike §2, §4). The solver's value is therefore **completeness and
documentation**, not a full mask: it (a) prunes provably-wrong candidates, (b) uniquely fixes the rare
tightly-constrained columns the manual pass missed (the L=0 LJMP grid found +5 this way), (c) records for
every column exactly *why* it is or isn't determinable — turning "we think it's exhausted" into an
auditable per-column ledger.

### 1.2. Design Constraints  {#C_OMS_01_02}

- **Cipher is fixed and positional.** `C[s][i] = (P[s][i] + K[i]) & 0xFF`; `K` shared over `s ∈` 180
  sectors (3 versions × 60). A single column in isolation carries **no** verification signal — any of 256
  candidates yields a valid byte. Verification is therefore always **multi-byte** (an instruction, a
  string, a table row).
- **Hard signals only.** Accept/reject only via constraints that cannot be satisfied by a wrong `K`
  (opcode-stream tiling, operand ranges, cross-version equality, known cribs). **No** statistical /
  language-model / entropy guessing — the spike proved it injects wrong `K` (§4 trap).
- **Never auto-merge into the proven mask.** Output is a **staging catalog**; unique finds are
  *promote-eligible* into `ks_partial.json` only through the existing gated review (as with the §3f bytes
  the user deferred). Variants live beside the existing `ks_conjectural.json` worksheet.
- **Offline, deterministic, three images.** No hardware, no network. Depth is fixed at 180; the barrier
  for unanchored columns is not a bug to engineer around.

## 2. Domain Model  {#C_OMS_02}

### 2.1. Key Entities  {#C_OMS_02_01}

| Entity | Responsibility |
|--------|----------------|
| **Column** `i ∈ 2..513` | A keystream position. State: `known` (in `ks_partial`) / `unknown`. Carries a cross-version class (`constant` / `varying`) and, on each logical page, a decrypted plaintext byte where `K[i]` is known. |
| **Page** (logical `L`) | A 514-byte sector addressed by `L` (spike §3a). Classified as **code** / **data-table** / **erased-lattice** / **string** — this selects which signals apply. A page may exist in 1–3 versions. |
| **Anchor** | A column with known `K`. On any page it yields a **known plaintext byte** — the terminal/interior checkpoint the window search must reproduce. |
| **Window** | A maximal run of consecutive unknown columns bounded by anchors on a given page (typically ≤7 between adjacent lattice anchors, longer where anchors are sparse). The unit of the joint search. |
| **Candidate** | A surviving value for `K[i]` (pass 1) or a joint fill of a window (pass 2). |
| **Signal** | A hard boolean predicate that rejects a candidate/fill (§C_OMS_03_03). |
| **Verdict** | Per-column outcome: `known` · `unique` · `variants` · `undeterminable` (with sub-reason: `no-signal` / `search-bounded` / `data-page`). |
| **Catalog** | The output artifact: one record per column (§C_OMS_03_04). |

### 2.2. Data Flows  {#C_OMS_02_02}

```
load 3 .ofw ──▶ split sectors ──▶ map logical L (spike §3a) ──▶ load ks_partial (anchors)
      │
      ▼
PASS 1  (all unknown columns, cheap)         PASS 2  (code pages, expensive)
  cross-version classify constant/varying      per window between anchors:
  page-class each logical page                   joint-enumerate fills, prune by
  prune impossible candidates                    opcode-tiling + operands + xver
      │                                          collect surviving K per column
      └───────────────┬───────────────────────────────────┘
                      ▼
        aggregate surviving candidates per column ──▶ verdict ──▶ CATALOG (+ summary)
                      │
                      └──▶ unique finds: promote-eligible into ks_partial (gated, manual)
```

## 3. Mechanisms  {#C_OMS_03}

### 3.1. Core Algorithm — hybrid two-pass  {#C_OMS_03_01}

**Pass 1 — isolated triage (all columns, O(columns × versions)).** For each column compute the
cross-version class: `constant` (equal ciphertext across the versions carrying the page ⇒ constant
plaintext, value still hidden) or `varying` (version-specific plaintext ⇒ true one-time-pad at that
column). Classify each logical page (code / data-table / erased-lattice / string) from its known-byte
signature and entropy. This pass alone settles the *reason* a column is or isn't attackable and prunes
candidates that any hard signal rejects independent of neighbours (rare — mostly it just labels).

**Pass 2 — anchored-window CSP on code pages (the yield).** On a code page the plaintext is known at
every anchor (≈1 byte in 8, the lattice). For each window of unknown columns between anchors:

- Treat the window as a **constraint-satisfaction** problem: assign the unknown `K` bytes so that the
  decrypted plaintext, decoded as an 8051 instruction stream, **tiles exactly** — instruction lengths
  sum to land on each anchor, and the stream **reproduces the known anchor bytes** at their positions.
- Propagate the same `K` across the **versions** that carry the page: where a page's content differs
  between versions, each version imposes its own valid-stream constraint on the *shared* `K` — divergent
  versions therefore prune *more* (the many-time-pad leverage, but via hard 8051 grammar, not n-grams).
- Enumerate by constraint propagation / bounded DFS (not blind 256^n): opcode at a boundary fixes
  instruction length and operand positions, collapsing the branching factor.
- A column's surviving-set = the union of its value across all surviving fills. `|set| == 1` ⇒ **unique**;
  `> 1` ⇒ **variants**; window unsolved within the bound ⇒ **undeterminable(search-bounded)**.

The hybrid ordering means every column gets a verdict from Pass 1 even where Pass 2 cannot run (data/
string/erased pages, or windows that explode past the search bound).

### 3.2. Candidate enumeration & range  {#C_OMS_03_02}

Default candidate set per column = `0x00..0xFF`. Narrowed *before* the expensive search by:

- **Structural position priors** (hard, not statistical): a column known to be an LJMP opcode slot ⇒
  candidate `{0x02}` (this is the §3f mechanism generalized); a column inside a confirmed known crib ⇒
  the crib byte. These come from page structure, not frequency.
- **Cross-version gate:** a `varying` column cannot be recovered by cross-version alone; it is only a
  Pass-2 candidate if it sits in a solvable code window.
- The **rejected** set is retained with a reason per value (§C_OMS_03_04) — the search is *exhaustive*
  over `0x00..0xFF`, so "rejected" is meaningful (each of the 256 was tested).

### 3.3. Verification signals (hard only)  {#C_OMS_03_03}

| # | Signal | Rejects a candidate when… | Applies to |
|---|--------|---------------------------|------------|
| **S1** | 8051 opcode validity | decoded opcode is illegal (`0xA5`) / an impossible boundary | code |
| **S2** | Instruction-stream **tiling** | instruction lengths don't land on the next anchor, or the stream's byte at an anchor ≠ the known plaintext there | code |
| **S3** | Operand range | `LJMP/LCALL/AJMP/ACALL/SJMP` target outside valid flash; `MOV direct`/SFR address impossible; page/relative branch off-image | code |
| **S4** | Cross-version coherence | shared `K` fails to yield a valid stream in *all* versions carrying the page; or a `constant`-class column's candidate contradicts equal ciphertext | code + all |
| **S5** | Known crib / string | on data/string pages, decrypted run contradicts a known table/LUT/ASCII structure (extends the spike crib-drag) | data/string |
| **S6** | Anchor consistency | a fill's derived `K` at any column that is *already* known (`ks_partial`) ≠ the known value | all |

Signals are **monotone** — a rejected candidate is never resurrected by a softer rule (there is no
softer rule). Statistical ranking is explicitly excluded (§C_OMS_01_02, DEC_02).

### 3.4. Output — per-column result catalog  {#C_OMS_03_04}

One machine-readable catalog (JSON) keyed by column, plus a human-readable summary. Each column record:

```
col: <int>
page_class / logical_pages: <where the column was attacked>
cross_version: constant | varying
verdict: known | unique | variants | undeterminable
value: <0xNN>            # when verdict == unique (or known)
candidates: [ {K:<0xNN>, basis:<signal chain that let it survive>} , ... ]   # when variants
rejected: [ {K:<0xNN>, reason:<first signal that killed it>} , ... ]         # exhaustive over 0..255
notes: <undeterminable sub-reason: no-signal | search-bounded | data-page>
```

- **unique** → promote-eligible into `ks_partial.json` via gated review (never auto-merged, DEC_03).
- **variants** → staged like `ks_conjectural.json` (candidate list + basis).
- **undeterminable** → recorded with its reason, so the ceiling is auditable, not asserted.

### 3.5. Edge Cases  {#C_OMS_03_05}

- **Combinatorial blow-up** (long anchor-sparse windows): cap the search (nodes/time); on hitting the
  cap, emit `undeterminable(search-bounded)` and **log the cap** — never silently drop coverage.
- **Non-code pages** (data-table / string / erased-lattice): S1–S3 N/A; only S4–S6 apply, so most such
  columns resolve to `undeterminable(data-page)` (matches spike §3e).
- **Contradiction with `ks_partial`** (S6 fails for *every* fill of a window): flag an **anomaly** —
  either the page-class is wrong or a known byte is suspect — for human review; do not auto-edit `ks_partial`.
- **Page present in <3 versions** (e.g. L=10 lowercase-LUT changed at 1.26): S4 weakens to the available
  versions; the record notes reduced cross-version depth.
- **Determinism:** identical inputs ⇒ identical catalog (byte-for-byte), so runs are diffable across
  future firmware versions.

## 4. Integration Points  {#C_OMS_04}

### 4.1. Dependencies  {#C_OMS_04_01}

- `firmware/ofw_crypto.py` — the additive cipher, sector split, container parse (reused, unchanged).
- `firmware/mask_lib.py` — `load()`, `L_map()`, `logical_L()`, `known_K()` (reused; may gain helpers).
- `firmware/ks_partial.json` — the 107 anchors (read-only input).
- `firmware/ks_conjectural.json` — existing candidate worksheet (the solver's variants align with its schema).
- Theory: [ofw_mask_cryptanalysis.spike.md](./ofw_mask_cryptanalysis.spike.md) (§2 recoverability theorem, §3b/§3f structural methods, §4 the trap).

No dependency on the shipped oscilloscope app (C_AOS/C_DSV/C_OCL/… are a different domain — see Reuse Check).

### 4.2. API Surface  {#C_OMS_04_02}

A single CLI entry (offline): `solve` (run the two passes → write catalog + summary), plus a read-only
`report` (render the catalog) and a `promote` helper that *proposes* unique finds for `ks_partial` and
hands them to the gated review — it never writes `ks_partial` itself. Exact signatures are the spec's job.

## 5. Design Decisions  {#C_OMS_DEC}

### DEC_01 — Unit of brute-force: isolated column vs anchored window  {#C_OMS_DEC_01}

> **Status:** resolved · **Date:** 2026-07-15

**Question:** Should the solver brute-force each column in isolation or over multi-byte windows?

| Option | Consequence |
|--------|-------------|
| A — Anchored-window CSP | Strongest; exploits multi-byte coupling; more code (needs 8051 decoder). |
| B — Per-column isolated | Simplest; but a positional cipher gives an isolated column no signal → ~all undeterminable. |
| C — **Hybrid** | Pass-1 isolated triage (verdict + reason for *every* column) then Pass-2 window CSP on code pages. |

**Decision:** C — Hybrid (user).
**Rationale:** Guarantees a verdict for every column (Pass 1) while getting the real yield only where it
can exist (Pass 2 on code). Documents determinability everywhere, spends compute only where it pays.
**Rejected because:** A alone leaves non-code columns unlabeled; B alone has near-zero yield.

### DEC_02 — Candidate acceptance discipline  {#C_OMS_DEC_02}

> **Status:** resolved · **Date:** 2026-07-15

**Question:** Hard structural signals only, or also statistical/heuristic ranking?

**Decision:** **Hard signals only** (user).
**Rationale:** The spike proved statistical guessing injects wrong `K` (§4). A tool whose output can seed
the *proven* mask must never emit a byte a wrong key could also satisfy.
**Rejected because:** heuristic ranking adds speculative candidates that erode trust in the catalog and
risk polluting `ks_partial` on promotion.

### DEC_03 — Disposition of results  {#C_OMS_DEC_03}

> **Status:** resolved · **Date:** 2026-07-15

**Question:** Do unique finds auto-merge into `ks_partial.json`, or stage for gated promotion?

**Decision:** Stage in a separate catalog; unique finds are *promote-eligible* only via the existing
gated review (the same discipline that kept §3f's INT1/v15/Tmr0/Tmr2 out of `ks_partial`).
**Rationale:** `ks_partial` is the trusted validator of any future full `K`; a tool must not write it
unattended. Keeps self-learning behind the commit-approval gate.
**Rejected because:** auto-merge could silently corrupt the validator on a solver bug or a mis-classed page.

### DEC_04 — Output granularity: one catalog vs a file per column  {#C_OMS_DEC_04}

> **Status:** resolved · **Date:** 2026-07-15

**Question:** "a file with results for each column" — one catalog with per-column entries, or 400+ files?

**Decision:** One catalog file (JSON) keyed by column + a human summary.
**Rationale:** ~400 unknown columns → one diffable, queryable artifact is far more usable than hundreds of
files; still "results for each column" (one record each). A per-column export can be a later `report` view.
**Rejected because:** hundreds of tiny files are unwieldy to review, diff, and version.

## 6. Scope

**This IS:**
- Automated, exhaustive per-column candidate enumeration (`0x00..0xFF`) over the 3 file-only images.
- Hybrid search: cross-version triage (all columns) + anchored-window 8051 CSP (code pages), hard signals only.
- A per-column determinability catalog: `unique` / `variants` / `undeterminable(reason)` / `rejected(reason)`.
- A gated bridge to `ks_partial` (propose, don't write) and a `ks_conjectural`-aligned variants store.

**This IS NOT:**
- A way past the information-theoretic barrier — unanchored/one-time-pad columns stay undeterminable (proven).
- Statistical / language-model / entropy guessing (the §4 trap) — excluded by DEC_02.
- Hardware / C2 / glitch anything — offline only.
- An auto-writer of the proven mask (DEC_03) or a full disassembler (it uses partial 8051 decode as a *signal*).

## Reuse Check

Searched existing concepts: `C_AOS, C_DSV, C_OCL, C_RES, C_WEB, C_WFE, C_CAL, C_CVT, C_AAJ` — all cover the
**running oscilloscope software** (Android/Python/web live device control). This concept is **offline
firmware-RE tooling**; no functional overlap. It reuses `ofw_crypto.py` + `mask_lib.py` (cipher/loading)
rather than re-implementing them. No existing concept is superseded.

## Changelog

| Date | Change |
|------|--------|
| 2026-07-15 | Initial version. Forks DEC_01 (hybrid) & DEC_02 (hard-signals-only) resolved via Interview Mode; DEC_03/04 resolved from project discipline. |
