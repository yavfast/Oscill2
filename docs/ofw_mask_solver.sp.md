# OFW Mask Solver — Specification  {#SP_OMS}

> **Code:** SP_OMS
> **Status:** draft
> **Created:** 2026-07-15
> **Updated:** 2026-07-15
>
> **Concept:** [C_OMS](./ofw_mask_solver.concept.md)
> **Depends on:** `firmware/ofw_crypto.py`, `firmware/mask_lib.py` (reused; not dev-flow specs) · [ofw_mask_cryptanalysis.spike.md](./ofw_mask_cryptanalysis.spike.md) (theory)
> **Used by:** —
> **Plan:** [PL_OMS](./ofw_mask_solver.plan.md) (draft)
>
> Defines the data structures, contracts, validation rules, and verification criteria for the offline
> `.ofw` mask solver: a two-pass search (Pass-1 cross-version + page triage over all unknown columns →
> Pass-2 anchor-seeded 8051 constraint search on code pages) that emits a per-column **determinability
> catalog** (`unique` / `variants` / `undeterminable` / `rejected`). Hard signals only; never writes the
> proven mask. All arithmetic is `mod 256`; `col` indexes a keystream position `2..513` (col 0 = CRC,
> col 1 = SEQ are out of scope — already characterized by the spike).

## 01. Data Structures  {#SP_OMS_01}

> Implements: [C_OMS_02](./ofw_mask_solver.concept.md#C_OMS_02)

### 01_01. SolverConfig  {#SP_OMS_01_01}

Run parameters. All have defaults; the tool runs with zero arguments.

| Field | Type | Required | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| images | list[str] | no | `["Uosc123.ofw","Uosc125.ofw","Uosc126.ofw"]` | ≥1 existing `.ofw` under `firmware/` | Ciphertext inputs (all share `K`). |
| ks_partial_path | str | no | `firmware/ks_partial.json` | readable JSON | Known anchors (read-only). |
| catalog_out | str | no | `firmware/ks_solver_catalog.json` | writable path | Output catalog. |
| flash_ranges | list[[int,int]] | no | `[[0x0400,0x7BFF],[0xF000,0xFFFF]]` | each `lo≤hi`, within `0x0000..0xFFFF` | Valid absolute jump/call target ranges (app region + high-flash bootloader). |
| search_bound | int | no | 200000 | ≥1 | Max decode-tree nodes explored per window before the window yields `undeterminable(search-bounded)`. |
| max_window | int | no | 64 | ≥8 | Max unknown-byte span a window may cover before it is declared `search-bounded` without search. |

Invariants:
- `flash_ranges` are treated as a set union; a target is in-range iff it falls in any range.
- Changing `search_bound`/`max_window`/`flash_ranges` may change `variants`↔`undeterminable` verdicts but MUST NOT change any `unique` value (a `unique` result is signal-forced, not bound-dependent) — see [SP_OMS_05_02](#SP_OMS_05_02).

### 01_02. Instr8051  {#SP_OMS_01_02}

Decoded-instruction descriptor from the canonical MCS-51 opcode map. Backing table is a static 256-entry
map (opcode → length/kind); `0xA5` is the single reserved opcode.

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| opcode | int | yes | 0..255 | First byte. |
| length | int | yes | 1 \| 2 \| 3 | Total instruction bytes (canonical MCS-51). `0xA5` → 1 (but see `illegal`). |
| kind | enum | yes | `abs_jump` \| `abs_call` \| `page_jump` \| `page_call` \| `rel_branch` \| `other` | Selects the operand check in S3. `LJMP`=`abs_jump`, `LCALL`=`abs_call`, `AJMP`/`SJMP` etc. as applicable. |
| illegal | bool | yes | — | True only for `0xA5`. |

Invariants:
- `instr_len` is a **total** function over `0..255` → `{1,2,3}` (never raises).
- The table is a static constant — identical across runs (contributes to determinism).

### 01_03. PageInfo  {#SP_OMS_01_03}

Per-logical-page classification (Pass 1), computed once, keyed by logical page `L` (spike §3a).

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| L | int \| "E" | yes | 0..58 or sentinel | Logical flash page. |
| versions | list[str] | yes | subset of `images` | Which images carry this page. |
| page_class | enum | yes | `code` \| `data-table` \| `string` \| `erased-lattice` \| `mixed` | Drives which signals apply. |
| entry_points | list[int] | yes | cols | Known instruction boundaries to seed decode (vector LJMP opcode cols on L=0; empty elsewhere unless a seed is derivable). |

Invariants:
- `page_class == erased-lattice` ⟹ only the offset-4 lattice is 0xFF; such pages yield no new columns (spike §5.0a).
- A page present in <3 versions weakens signal S4 (recorded in each affected ColumnRecord's `notes`).

### 01_04. ColumnRecord  {#SP_OMS_01_04}

The catalog entry for one keystream column — the tool's primary product (req 3).

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| col | int | yes | 2..513 | Keystream position. |
| verdict | enum | yes | `known` \| `unique` \| `variants` \| `undeterminable` | Outcome (see [SP_OMS_04](#SP_OMS_04)). |
| value | str \| null | when `known`/`unique` | `0x00`..`0xFF` | The determined `K[col]`. Null otherwise. |
| cross_version | enum | yes | `constant` \| `varying` \| `n/a` | Pass-1 class (`n/a` if <2 versions carry every page at this col). |
| page_class | enum | yes | as PageInfo, or `mixed` | Aggregated over the pages where the column was attacked. |
| attacked_on | list[int\|"E"] | yes | logical pages | Pages that contributed a signal for this column. |
| candidates | list[CandidateEntry] \| "unconstrained" | when `variants`/`undeterminable(no-signal)` | — | Surviving `K` values (variants), or the literal `"unconstrained"` when no signal reached the column. |
| rejected | list[RejectedEntry] | yes | — | Candidates eliminated by a signal (empty when no signal fired). |
| notes | str | no | `no-signal` \| `search-bounded` \| `data-page` \| free text | Sub-reason for `undeterminable`, or caveats (e.g. reduced cross-version depth). |

Invariants:
- `verdict == known` ⟺ `col ∈ ks_partial` (the solver never overrides a known byte; it may *corroborate* it).
- `verdict == unique` ⟹ `len(candidates surviving) == 1` and `value` = that survivor.
- `verdict == variants` ⟹ `len(candidates) ≥ 2`.
- `verdict == undeterminable` ⟹ `value == null` and (`candidates == "unconstrained"` with `notes==no-signal`) OR (`notes ∈ {search-bounded, data-page}`).
- **Exhaustiveness (code windows):** where any signal fired, every value in `0x00..0xFF` is accounted for — it is either a surviving candidate or appears in `rejected`. Where no signal fired, `candidates=="unconstrained"`, `rejected==[]` (all 256 trivially survive; not enumerated — [SP_OMS_DEC_01](#SP_OMS_DEC_01)).

### 01_05. CandidateEntry / RejectedEntry  {#SP_OMS_01_05}

CandidateEntry (a survivor):
| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| K | str | yes | `0x00`..`0xFF` | Candidate keystream byte. |
| P | str | yes | `0x00`..`0xFF` | Implied plaintext on the reference page/version (`(C−K)&0xFF`). |
| basis | str | yes | non-empty | Signal chain that let it survive (e.g. `"LJMP tiling @L0 slot16; xver ok"`). |

RejectedEntry (an eliminated value):
| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| K | str | yes | `0x00`..`0xFF` | Rejected keystream byte. |
| reason | enum | yes | `S1` \| `S2` \| `S3` \| `S4` \| `S6` | First signal that killed it (S5 is a data-page survivor filter, recorded as basis, not a rejection code here). |

### 01_06. Catalog  {#SP_OMS_01_06}

Top-level output (`catalog_out`).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| meta | object | yes | `{tool, generated_from[], ks_partial_n, total:514, search_bound, flash_ranges, summary:{known,unique,variants,undeterminable}}`. No timestamp (determinism — [SP_OMS_05_02](#SP_OMS_05_02)). |
| columns | object | yes | Map `str(col) → ColumnRecord` for every col `2..513`. |

Invariants:
- `columns` has exactly 512 entries (cols 2..513); `meta.summary` counts partition them.
- `known` count in `meta.summary` == `ks_partial_n` restricted to cols 2..513 = **106** (the 107th
  anchor is col 1 SEQ, out of catalog scope per §01). `meta.ks_partial_n` reports this in-scope 106.

## 02. Contracts  {#SP_OMS_02}

> Implements: [C_OMS_03](./ofw_mask_solver.concept.md#C_OMS_03), [C_OMS_04](./ofw_mask_solver.concept.md#C_OMS_04)

### 02_01. solve  {#SP_OMS_02_01}

Purpose: run both passes and write the catalog. The single top-level operation (CLI `solve`).

Input:
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| config | SolverConfig | no | valid per 01_01 |

Output:
| Field | Type | Description |
|-------|------|-------------|
| catalog | Catalog | written to `config.catalog_out` and returned |

Errors:
| Code | Condition | Guidance |
|------|-----------|----------|
| E_NO_IMAGE | an `images` path missing / not an `.ofw` | Abort; name the file. |
| E_KS_INVALID | `ks_partial` unreadable / not `{col:hex}` | Abort; do not fall back to an empty anchor set (would corrupt S6). |
| E_KS_CONFLICT | an anchor’s `K` is internally inconsistent across the loaded images (cannot happen for a correct file) | Abort; the input mask is wrong. |
| E_CONFIG | a `SolverConfig` numeric/range field is malformed (`search_bound<1`, `max_window<8`, empty/ill-formed `flash_ranges`) | Abort; fix the run parameter (distinct from the `ks_partial` input error). |

Processing logic (pseudocode):

    FUNCTION solve(config):
        images, anchors = load(config)              # 02_07-style loader; anchors = {col:K}
        pages = classify_pages(images)              # 02_03
        colclass = classify_columns(images)         # 02_02
        records = {col: seed_record(col, anchors, colclass, pages) for col in 2..513}
        FOR page IN pages WHERE page.page_class == "code":
            FOR window IN windows_of(page, anchors):        # unknown runs bounded by anchors
                result = solve_window(window, page, images, anchors, config)   # 02_04
                merge(result, records)                       # union survivors per column
        finalize_verdicts(records)                  # apply 01_04 invariants
        catalog = build_catalog(records, config)
        write_json(config.catalog_out, catalog)     # deterministic serialization
        RETURN catalog

### 02_02. classify_columns  {#SP_OMS_02_02}

Purpose: Pass-1 cross-version class per column (cheap, all columns).

Input: `images`. Output: `{col → "constant"|"varying"|"n/a"}`.

Processing logic:

    FOR col IN 2..513:
        FOR each logical page L present in ≥2 images:
            collect ciphertext C_v[col] across the versions carrying L
        col is "constant" iff C is equal across versions on EVERY such page;
        "varying" iff it differs on any; "n/a" iff no page has ≥2 versions at col.

Note: `constant` means the plaintext is version-invariant (value still hidden — spike §2); it does NOT
by itself determine `K`.

### 02_03. classify_pages  {#SP_OMS_02_03}

Purpose: assign each logical page a `page_class` + entry points.

Input: `images`, `anchors`. Output: `{L → PageInfo}`.

Errors: none (unknown/ambiguous → `mixed`).

Processing logic (heuristics, hard-signal-compatible):
- `erased-lattice`: the known lattice cols all decrypt to 0xFF and non-lattice cols vary → structured data, not code (spike §5.0a). No entry points.
- `code`: contains a recognizable instruction structure — L=0 (vector table: entry_points = the LJMP opcode cols) or a page reachable by decode from a vector LJMP target. 
- `string` / `data-table`: printable-run or 8-byte-record signature at known cols; no clean opcode tiling.
- `mixed`: none of the above dominates.

### 02_04. solve_window  {#SP_OMS_02_04}

Purpose: Pass-2 core — recover/bound the unknown columns of one code window by anchor-seeded 8051
constraint search across the versions carrying the page. This realizes signals S1–S4, S6.

Input:
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| window | Window `{page, cols_unknown[], anchors_in_span}` | yes | cols contiguous-ish, `span ≤ max_window` |
| page, images, anchors, config | — | yes | — |

Output: `{col → set[int]}` — surviving `K` values per unknown column in the window (empty set ⟹ contradiction/anomaly; see errors).

Errors:
| Code | Condition | Guidance |
|------|-----------|----------|
| W_BOUNDED | node budget or `max_window` exceeded | Emit `undeterminable(search-bounded)` for the window’s cols; LOG the cap (no silent truncation — [SP_OMS_03](#SP_OMS_03)). |
| W_ANCHOR_ANOMALY | zero fills survive AND every fill failed S6 against a *known* anchor | Flag anomaly for human review (page mis-class or a suspect known byte). Do NOT edit `ks_partial`. |

Processing logic (pseudocode):

    FUNCTION solve_window(window, page, images, anchors, config):
        survivors = {col: set() for col in window.cols_unknown}
        seeds = decode_seeds(page)                  # known instruction boundaries
        nodes = 0
        FOR seed IN seeds:
            DFS over instruction boundaries from seed:
                at an opcode position that is unknown:
                    FOR k IN candidate_range(col):          # 0..255, minus position priors
                        p = (C_ref[col] - k) & 0xFF
                        if S1_illegal(p): reject(col,k,"S1"); continue
                        instr = decode(p, following bytes as fixed/branch)
                        if not S2_tiles(instr, anchors): reject(col,k,"S2"); continue
                        if not S3_operand_in_range(instr, config.flash_ranges): reject(col,k,"S3"); continue
                        if not S4_valid_all_versions(k, col, page, images): reject(col,k,"S4"); continue
                        if not S6_anchor_consistent(k, col, anchors): reject(col,k,"S6"); continue
                        record survivor; recurse to next boundary
                    nodes += 1; if nodes > search_bound: raise W_BOUNDED
        RETURN survivors

- **S1** illegal opcode (`0xA5`). **S2** the decoded stream’s length tiles exactly onto the next anchor
  and reproduces every known byte inside the span. **S3** `abs_jump`/`abs_call` target ∈ `flash_ranges`;
  `rel_branch` target lands inside the image. **S4** the *same* `k` yields a non-contradictory stream in
  every version carrying the page (divergent versions prune more). **S6** the derived `K` at any column
  already in `anchors` equals the known value.

> **v1 realization (PL_OMS_DEC_01 — L=0 vector table).** With Pass-2 scoped to L=0, the DFS above
> **collapses to a depth-1 search per 8-byte vector slot**: the target-hi lattice anchor at `col+1` bounds
> each slot immediately, so no multi-boundary recursion is needed. Each candidate `k` is tested
> exhaustively (`0..255`); the decrypted opcode is decoded with the MCS-51 map (`instr_info`) and a slot is
> accepted only if it is a **written vector LJMP** (`kind==abs_jump`; S3 target in a flash range) or an
> **erased slot** (`0xFF` fill; S2 tiling requires the known target-hi to be `0xFF`) — every other opcode
> fails S2. This is the exact §3f mechanism (a vendor vector table is a complete LJMP grid — see the
> `firmware_ofw_format` skill), not a statistical prior. The general instruction-boundary DFS and the
> broader `decode_stream` engine (SP_OMS_02_05) are retained for the deferred multi-page seed discovery
> (PL_OMS Backlog); v1 consumes `instr_info` (kind + illegal) for S1/S2/S3.

### 02_05. decode_stream / instr_len  {#SP_OMS_02_05}

Purpose: the MCS-51 decoder used by S1–S3.

- `instr_len(opcode:int) -> int` — total, `0..255 → {1,2,3}`.
- `instr_info(opcode:int) -> Instr8051` — length + kind + illegal.
- `decode_stream(plain:bytes, start:int) -> list[Instr8051]` — greedy linear decode from `start`.

Errors: none (total functions). Verification: [SP_OMS_05_01](#SP_OMS_05_01).

### 02_06. propose_promotions  {#SP_OMS_02_06}

Purpose: the gated bridge — surface `unique` finds for `ks_partial`, **without writing it** (C_OMS_DEC_03).

Input: `catalog`. Output: a promotion proposal list `[{col, value, basis}]` for every `unique` col not
already in `ks_partial`, plus a ready-to-review diff summary. It performs **no file write** to
`ks_partial.json`; promotion is a separate, human-approved commit step.

Errors:
| Code | Condition | Guidance |
|------|-----------|----------|
| P_CONTRADICTS_KNOWN | a `unique` value contradicts an existing `ks_partial` byte | Never propose it; escalate as an anomaly (should be impossible if S6 held). |

### 02_07. report  {#SP_OMS_02_07}

Purpose: render `catalog` as a human-readable summary (counts per verdict; the `unique` list with basis;
`variants` with candidate counts; `undeterminable` histogram by sub-reason). Read-only; no file writes
besides optional stdout/`report` text.

## 03. Validation Rules  {#SP_OMS_03}

### 03_01. Input Validation  {#SP_OMS_03_01}

- Every `images` path exists, parses as an `.ofw` (magic + `FW:`), payload length `% 514 == 0` → else `E_NO_IMAGE`.
- `ks_partial` parses to `{int col: int K}` with `0 ≤ K ≤ 255`, cols in `0..513` → else `E_KS_INVALID`.
- `search_bound ≥ 1`, `max_window ≥ 8`, `flash_ranges` non-empty and well-formed.

### 03_02. Processing Rules  {#SP_OMS_03_02}

- **No statistical acceptance.** A candidate is accepted only via S1–S6 (hard). Frequency/entropy/idiom
  priors are forbidden as acceptance criteria (C_OMS_DEC_02; entropy is shift-invariant → carries no `K`
  information, and 3-version frequency matching is the falsified §4 trap).
- **No silent truncation.** Any window that hits `search_bound`/`max_window` is reported as
  `undeterminable(search-bounded)` and its cap is logged/summarized.
- **Read-only on existing artifacts.** The solver reads `.ofw` and `ks_partial.json`; it writes only
  `catalog_out` (and optional report text). It never writes `ks_partial.json` / `ks_conjectural.json`.

## 04. State Transitions  {#SP_OMS_04}

### 04_01. Per-column verdict lifecycle  {#SP_OMS_04_01}

State diagram:

    [unknown] --classify--> [triaged] --window-search--> [unique | variants | undeterminable]
    [in ks_partial] --------------------------------------> [known]   (corroborated, never overwritten)

Transition rules:
| From | To | Condition | Side effects |
|------|----|-----------|--------------|
| unknown | known | `col ∈ ks_partial` | value copied from anchor; solver may corroborate via S6 |
| triaged | unique | exactly one `K` survives all signals across all seeds/versions | value set; promote-eligible |
| triaged | variants | ≥2 `K` survive | candidate list stored |
| triaged | undeterminable | no signal reached the col (`no-signal`), or window bounded (`search-bounded`), or non-code page (`data-page`) | reason in `notes` |

## 05. Verification Criteria  {#SP_OMS_05}

### 05_01. Functional Expectations  {#SP_OMS_05_01}

| Contract | Scenario | Input | Expected outcome |
|----------|----------|-------|------------------|
| instr_len | totality | all 256 opcodes | returns ∈ {1,2,3}; `0x02`→3, `0x12`→3, `0x80`→2, `0x00`→1; `0xA5`.illegal==true |
| solve_window | **§3f reproduction (positive control)** | `ks_partial` **minus col 133**, page L=0 | col 133 → `verdict=unique`, `value=0x29` (matches the committed byte) |
| solve_window | trap slots | `ks_partial` minus {21,125} | cols 21,125 → `variants` (or `unique`) whose candidate set **contains** the `0x02`-derived K (0xc1 / 0xdf) |
| solve_window | ambiguous FF slots | `ks_partial` minus {13,45} | cols 13,45 → `variants` (LJMP-`0x02` and erased-`0xFF` derived K both present) |
| solve | no-signal column | any high-entropy varying data column (e.g. col 300) | `undeterminable`, `notes=no-signal`, `candidates="unconstrained"` |
| solve | happy path | default config | catalog with 512 column records; `meta.summary` counts sum to 512 |
| propose_promotions | gated | catalog with a `unique` new col | returns a proposal; `ks_partial.json` byte-unchanged on disk |

### 05_02. Invariant Checks  {#SP_OMS_05_02}

| Invariant | Verification method |
|-----------|---------------------|
| Determinism | Run `solve` twice → catalog files byte-identical (no timestamps/`Date.now`). |
| Never writes proven mask | `sha256(ks_partial.json)` unchanged before/after any `solve`/`propose`. |
| No overwrite of known | Every `col ∈ ks_partial` has `verdict==known` and `value` == the anchor. |
| Exhaustiveness (code windows) | For each col with a non-empty `rejected`, `|survivors| + |distinct rejected K| == 256`. |
| Signal monotonicity | A value in `rejected` never also appears in `candidates` for the same col. |
| Bound-independence of `unique` | Re-run with `search_bound×10` → the set of `unique` cols and their `value`s is unchanged (only variants↔undeterminable may shift). |

### 05_03. Integration Scenarios  {#SP_OMS_05_03}

| Scenario | Preconditions | Steps | Expected result |
|----------|---------------|-------|-----------------|
| Anchors from ks_partial | `ks_partial` = 107 | `solve` | S6 uses all anchors as constraints; `known` count == **106** (cols 2..513; the 107th anchor is col 1 SEQ, out of scope) |
| Cross-version pruning | L=0 varies across versions | `solve_window` on an L=0 code window | a fill valid in v123 but invalid in v125/126 is rejected (S4) |
| Catalog → conjectural alignment | `variants` produced | inspect a `variants` record | schema (K + basis) is mergeable into the existing `ks_conjectural.json` worksheet shape |
| Promotion handoff | catalog has `unique` new cols | `propose_promotions` → human review → manual commit | mirrors the §3f flow (col 133 promoted, others deferred) |

### 05_04. Edge Cases and Boundaries  {#SP_OMS_05_04}

| Case | Input | Expected behavior |
|------|-------|-------------------|
| Fully-erased-lattice page | L in 14..24 | columns → `undeterminable(data-page)`; no false 0xFF harvest (spike §5.0a) |
| Page in <3 versions | L=10 (v126 changed) | S4 uses available versions; `notes` records reduced depth |
| Window explosion | long anchor-sparse code run | `undeterminable(search-bounded)`; cap logged |
| Anchor contradiction | mis-classified page forces S6 to fail for all fills | `W_ANCHOR_ANOMALY`; flagged, `ks_partial` untouched |
| Data/string page | hex-LUT page L=10/11 | opcode signals N/A; only S5 crib survivor-filter; most cols `undeterminable(data-page)` |

## 06. Reversibility  {#SP_OMS_06}

### 06_01. Rollback Strategy  {#SP_OMS_06_01}

| Aspect | Rollback approach |
|--------|-------------------|
| Data/state changes | None to existing artifacts — the tool is read-only on `.ofw`/`ks_partial`. Rollback = delete `ks_solver_catalog.json`. |
| Artifacts | New files: the solver module(s) under `firmware/`, `ks_solver_catalog.json`, optional report. All deletable without affecting the shipped app or the existing mask files. |
| Dependent modules | None. No dev-flow spec `Depends on` SP_OMS; the running oscilloscope stack is unaffected (separate domain). |
| External contracts | None published. `propose_promotions` only *proposes* — no automatic write into `ks_partial`, so a bad run cannot corrupt the trusted validator. |

## 07. Design Decisions  {#SP_OMS_DEC}

### DEC_01 — Rejected-set storage: enumerate all 256 or only signal-eliminated?  {#SP_OMS_DEC_01}

> **Status:** resolved · **Date:** 2026-07-15

**Question:** How to record the "rejected verified variants" (req 3) without a 256×512 blob?

| Option | Consequence |
|--------|-------------|
| A — store all 256 per column | ~131k entries; huge; mostly meaningless on no-signal columns |
| B — store only signal-eliminated K; no-signal cols = `"unconstrained"` | compact; audit trail only where a signal actually discriminated |

**Decision:** B.
**Rationale:** On a positional cipher a no-signal column has all 256 trivially surviving — enumerating them is noise. Rejections are meaningful only where S1–S6 fired (code windows); there the exhaustiveness invariant (`survivors + rejected == 256`) still holds.
**Rejected because:** A bloats the catalog and obscures the columns that matter.

### DEC_02 — 8051 length/kind table source  {#SP_OMS_DEC_02}

> **Status:** resolved · **Date:** 2026-07-15

**Question:** Where does the opcode length/kind map come from?

**Decision:** A static, canonical MCS-51 256-entry table baked into the module; `0xA5` = the one reserved opcode (S1).
**Rationale:** The 8051 ISA is fixed and public; a static table is deterministic and auditable.
**Rejected because:** deriving lengths at runtime from a disassembler dependency adds a library and non-determinism risk for zero benefit.

### DEC_03 — Window model: anchor-seeded DFS vs blind joint enumeration  {#SP_OMS_DEC_03}

> **Status:** resolved · **Date:** 2026-07-15

**Question:** How does Pass-2 explore a code window without `256^n` blowup?

**Decision:** Anchor-seeded bounded DFS over instruction boundaries (seed at known LJMP boundaries / decode entry points); branch only at unknown opcode positions; prune by S1–S6 at each node; cap at `search_bound`.
**Rationale:** Reproduces how §3f actually worked (the vector-table decode); opcode-at-boundary collapses branching to the few valid lengths; bounded and deterministic.
**Rejected because:** blind joint enumeration of a 7-byte gap is `256^7` and ignores the boundary structure that makes the search tractable.

## Changelog

| Date | Change |
|------|--------|
| 2026-07-15 | Initial version. Data structures, contracts (solve / classify / solve_window / decoder / propose / report), verification tied to the committed §3f ground truth, rollback (read-only tool). DEC_01–03 spec-level; DEC_01/02 (search model, hard-signals) inherited from C_OMS. |
| 2026-07-15 | Implement-phase corrections (non-breaking): in-scope `known` count is **106** (cols 2..513; col 1 SEQ is the 107th anchor, out of scope) — SP_OMS_01_06 / SP_OMS_05_03. `data-page` per-column note is deferred in v1 (positional cipher + L=0-only scope, PL_OMS_DEC_01); the SP_OMS_05_04 erased-lattice edge case is verified at the page-classification level. See PL_OMS Implementation Notes. |
