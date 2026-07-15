# Concept: Periodic-Signal Resolution Enhancement  {#C_RES}

> **Code:** C_RES
> **Status:** draft
> **Created:** 2026-07-15
> **Updated:** 2026-07-15
> **Author:** claude-opus
> **Owner:** Python backend — signal-processing layer (alongside C_CAL / C_DSV)
> **Complexity:** high (stateful cross-frame pipeline; alignment + gating correctness)
>
> **Depends on:** [C_CAL](./calculations.concept.md), [C_DSV](./device_service.concept.md), [C_CVT](./converters.concept.md)
> **Used by:** [C_WEB](./web_api.concept.md), [C_WFE](./web_frontend.concept.md)
> **Spike:** [sample_array_length.spike.md](./sample_array_length.spike.md) (QSh headroom); ETS-feasibility spike — pending (see C_RES_DEC_03)
> **Specification:** [SP_RES](./resolution_enhancement.sp.md) (draft)
> **Plan:** [PL_RES](./resolution_enhancement.plan.md) (draft)
>
> Raise the *effective* resolution of the displayed oscillogram for **periodic** signals by combining
> information across multiple acquired frames — align each frame to a reference sub-sample, reject
> false-trigger frames, and maintain a continuous rolling average — plus an optional per-frame moving
> -average smoother. The single-shot raw path is unchanged; enhancement is an opt-in mode.

## 1. Philosophy  {#C_RES_01}

### 1.1. Core Principle  {#C_RES_01_01}

A single acquired frame is one 8-bit single-shot snapshot: its amplitude resolution is bounded by
the ADC quantization step and the per-sample noise floor. **When the signal is periodic, many
triggered acquisitions are noisy copies of one underlying waveform.** If those copies are aligned
precisely in phase and averaged, uncorrelated noise averages down (≈ √N for N frames) and amplitude
detail *below* the single-shot quantization/noise floor emerges — the trace gains **effective bits**
of vertical resolution without any hardware change.

Precise alignment is not optional: the hardware trigger fires with **sub-sample timing jitter** and
can **mis-fire on local gradients / noise** (a false trigger). Averaging misaligned frames is a
low-pass that *blurs the edges* — destroying the very resolution the averaging is meant to add. So
the two enabling mechanisms the user identified — **sub-sample offset correction** and **false
-trigger rejection** — are prerequisites of the average, not separate features.

This concept therefore has one heart: a **coherent multi-frame accumulator** (align → gate →
average). It also carries one auxiliary, independent lever: an optional **moving-average (SMA)
smoother** that trades bandwidth for lower noise on a single frame.

### 1.2. Design Constraints  {#C_RES_01_02}

- **Periodic + stationary only.** Enhancement is meaningful only when the signal is periodic and not
  changing. The pipeline MUST detect this precondition (a stable period is derivable) and **degrade
  gracefully** to the raw single-frame trace when it does not hold. It never fabricates detail.
- **Opt-in, non-destructive.** The raw single-shot path (C_DSV frame → C_WEB → C_WFE) is unchanged.
  Enhancement is a mode the user enables. **Rollback = disable the mode**; the system reverts to raw
  frames with no residual state.
- **Backend only.** All accumulation, alignment, and gating live in the Python backend, consistent
  with `HardwareAccessOnlyThroughDeviceService` and the thin-frontend principle (C_WFE). The frontend
  only sends enhancement settings and renders the enhanced frame like any other frame.
- **No device I/O in the enhancement hot path.** The accumulator consumes frames the acquisition loop
  (C_DSV) already produced; it adds no serial reads per frame.
- **Respect existing sample-space conventions.** Accumulation happens in a consistent per-mode sample
  space and MUST honour delivered-length geometry and peak-mode 2× expansion (see the
  `signal_processing` skill). Initial scope targets single-sample modes (NORMAL / AVG / AVG_HIRES);
  min/max envelope (PEAK / PEAK_HI) handling is out of initial scope (see C_RES_03_02).
- **Bounded resources.** Rolling depth N is bounded; the accumulator reuses the existing frame ring
  buffer as its source and holds one running average plus a reference — not N full frames unless the
  chosen model requires it (settled in spec, see C_RES_DEC_02).
- **Amplitude precision.** The enhanced trace is real-valued (extended precision), not re-quantized to
  8 bits — otherwise the recovered sub-quantization detail is thrown away before display.

## 2. Domain Model  {#C_RES_02}

### 2.1. Key Entities  {#C_RES_02_01}

| Entity | Responsibility |
|--------|----------------|
| **Enhancement mode** | User-facing state: enabled flag, target rolling depth N, SMA window W, plus derived status (active / inactive-with-reason). |
| **Reference frame** | The trace all candidates are aligned to (established from the first accepted frame after enable/reset). Defines the phase grid of the accumulated output. |
| **Alignment offset** | The sub-sample (fractional) shift that best aligns a candidate frame to the reference, with an associated match quality (correlation peak). |
| **Frame gate** | The accept/reject decision for a candidate: is it a valid instance of the periodic waveform? Rejects false triggers, degenerate/non-matching frames, and config-mismatched frames. |
| **Accumulator** | The running, real-valued rolling average over the last N *accepted, aligned* frames — the enhanced trace. |
| **Quality metrics** | Observability of the enhancement: frames accumulated, mean match quality, estimated effective-bit gain, accept/reject rate. |
| **Smoother (SMA)** | Optional, independent per-frame moving average over the sample axis (window W); W = 1 means off. |

```
              ┌───────────────────────── Enhancement mode (enabled, N, W) ─────────────┐
              │                                                                          │
  raw frame ──┤ periodic? ──no──────────────────────────────────────────► raw passthrough (status: inactive)
 (from C_DSV) │   │yes                                                                   │
              │   ▼                                                                       │
              │ Frame gate ──reject──► drop (count); K rejects in a row ──► reset ref     │
              │   │accept                                                                 │
              │   ▼                                                                       │
              │ Alignment (cross-correlate → sub-sample shift) ──► resample to ref grid   │
              │   │                                                                       │
              │   ▼                                                                       │
              │ Accumulator (rolling avg, depth N) ──► enhanced float trace + quality     │
              └───┬───────────────────────────────────────────────────────────────────┘
                  ▼
             optional SMA (window W) ──► emitted frame (to C_WEB / C_WFE)
```

### 2.2. Data Flows  {#C_RES_02_02}

1. A raw frame is produced by the C_DSV acquisition loop and carries its `cfg_id`.
2. If enhancement is disabled → the frame passes through untouched (existing behaviour).
3. If enabled: the **periodicity precondition** is checked (a stable period is derivable via C_CAL's
   segment-frequency detection). No stable period → passthrough, status `inactive: not-periodic`.
4. On the first accepted frame after enable/reset, a **reference** is captured (real-valued copy).
5. Each subsequent frame is **gated** against the reference (match quality + sanity). Rejected frames
   are dropped and counted; K consecutive rejects (signal changed) → reset reference & accumulator.
6. Accepted frames are **aligned** (sub-sample shift onto the reference grid) and folded into the
   **rolling average**.
7. The accumulator emits the **enhanced frame**: a real-valued sample array plus **quality metrics**.
8. If SMA is on (W > 1), the smoother is applied (to the enhanced trace, or the raw trace when the
   accumulator is inactive).
9. Measurements (C_CAL) are recomputed on the emitted trace so freq/Vpp/… reflect what is displayed.
10. **Reset triggers:** `cfg_id` change (config changed — C_DSV already clears the frame buffer, the
    accumulator must reset too), mode re-enable, or sustained rejection.

## 3. Mechanisms  {#C_RES_03}

### 3.1. Core Algorithm  {#C_RES_03_01}

**Coherent rolling average (the heart).** For each incoming accepted frame:

1. **Periodicity guard.** Derive the period (reuse the segment-counting detector from C_CAL). If no
   stable period is found → do not accumulate; emit raw with `inactive: not-periodic`.
2. **Reference.** If no reference exists, adopt the current frame as the real-valued reference R and
   seed the accumulator with it.
3. **Alignment offset.** Estimate the shift between the candidate F and R:
   - Compute a cross-correlation of F against R over a bounded lag window (the lag search is bounded
     by roughly one period, so ambiguity from periodicity is contained).
   - Take the integer lag at the correlation maximum, then **refine to sub-sample** by interpolating
     around the correlation peak (e.g. parabolic peak / phase estimate). The output is a fractional
     shift plus the peak correlation coefficient as a **match quality**.
   - *(The precise estimator — full cross-correlation vs period-phase alignment — is a spec-altitude
     choice; see C_RES_DEC_06.)*
4. **Gate (false-trigger rejection).** Accept F only if: match quality ≥ acceptance threshold, and
   |shift| within a sane bound, and amplitude within range. Otherwise **reject** (false trigger / not
   the same waveform / degenerate) and increment the consecutive-reject counter.
5. **Resample.** Shift F by the fractional offset onto R's sample grid (interpolation), so it lands in
   phase with the accumulator.
6. **Accumulate.** Fold the aligned F into the rolling average of depth N (true sliding-window mean or
   an exponential moving average of equivalent depth — settled in spec, C_RES_DEC_02). Update the fill
   level and quality metrics (accumulated count, mean quality, estimated effective-bit gain).
7. **Emit.** Output the real-valued enhanced trace + quality metrics.

**SMA smoother (auxiliary, independent).** A moving average of window W over the sample axis. It
reduces high-frequency noise but **lowers effective bandwidth** (edges soften) — it does not add
information and is not a substitute for coherent averaging. W is user-set; W = 1 disables it. It may
be applied whether or not the accumulator is active.

### 3.2. Edge Cases  {#C_RES_03_02}

| Situation | Behaviour |
|-----------|-----------|
| Non-periodic / transient / DC-flat signal | No reference/period → raw passthrough, status `inactive: not-periodic`. |
| Config change mid-accumulation (`cfg_id` changes) | Reset reference + accumulator (C_DSV clears the frame buffer on config change; enhancement mirrors that). |
| Sustained rejection (signal changed but still periodic) | After K consecutive rejects, drop reference and re-baseline from the next frame. |
| Very high frequency (few samples/cycle) | Alignment ambiguous → gate rejects; falls back to raw with a status reason. |
| Amplitude clipping (railed signal) | Clipped regions can't be recovered; averaging still lowers noise elsewhere. Not treated as an error. |
| PEAK / PEAK_HI modes (2× min/max envelope) | Out of initial scope — enhancement inactive with a status reason; averaging min/max envelopes is deferred. |
| Slow timebase (frames arrive slowly) | Rolling average fills slowly but correctly; interacts with `TD_…slow-timebase-timeout` (acquisition-timing, separate). |

## 4. Integration Points  {#C_RES_04}

### 4.1. Dependencies  {#C_RES_04_01}

- **[C_CAL]** — segment-frequency/period detection (periodicity guard + period-bounded alignment
  window); measurements are recomputed on the emitted enhanced trace.
- **[C_DSV]** — frame source (acquisition loop + ring buffer); `cfg_id` reset signal; the enhancement
  stage is a backend post-processing step between frame acquisition and API exposure.
- **[C_CVT]** — unit conversion for quality metrics where physical units are surfaced.

### 4.2. API Surface  {#C_RES_04_02}

Exposed abstractly (concrete contracts belong to SP_RES / SP_WEB):

- **Enhancement settings (in):** `enabled`, target rolling depth `N`, SMA window `W`.
  (Acceptance threshold and lag bound are internal tuning, not user-facing unless a need appears.)
- **Enhanced frame (out):** a real-valued sample array (extended precision) plus **quality metadata**:
  accumulated frame count, mean match quality, estimated effective-bit gain, and an
  `active | inactive:<reason>` status.
- **Reset:** implicit on `cfg_id` change / re-enable / sustained rejection (no explicit client call
  required for the initial scope).

## 5. Design Decisions  {#C_RES_DEC}

### DEC_01 — Concept scope & structure  {#C_RES_DEC_01}

> **Status:** resolved
> **Date:** 2026-07-15

**Question:** How broad is this concept — which of the user's six items does it commit to, and is it one concept or an epic?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — Averaging core (#3+#4+#5) + SMA (#2), one focused concept; QS-raise (#1) & ETS (#6) separate | Highest-value, cohesive, self-contained; two related levers pursued elsewhere |
| B — Full suite as an epic (averaging + SMA + QS + ETS) | Most complete; most work; slowest to first result |
| C — Everything in one flat concept | Risks a bloated concept mixing independent responsibilities |
| D — Cheap wins only (SMA + gating + QS) | Skips the biggest amplitude-resolution win (coherent averaging) |

**Decision:** A — one focused concept = coherent averaging core + SMA.
**Rationale:** Coherent averaging is what "the signal is periodic" most directly unlocks (vertical/SNR
bits) and it is self-contained. QS-raise is a single-frame config lever already filed as
`TD_20260715_110813_higher-hres-qs`; ETS is a distinct temporal mechanism with unverified device
feasibility (DEC_03). Keeping them separate keeps this concept coherent and shippable.
**Rejected because:** B/C over-scope one concept; D forgoes the primary win.

### DEC_02 — Accumulation model  {#C_RES_DEC_02}

> **Status:** resolved
> **Date:** 2026-07-15

**Question:** Continuous rolling average vs explicit N-frame capture?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — Continuous rolling average, user depth N | Live-updating enhanced trace; matches existing continuous-polling UX |
| B — Explicit "capture N & average" one-shot | Simpler state; not live |
| C — Both | More API/UI surface |

**Decision:** A — continuous rolling average, user-set depth N.
**Rationale:** Fits the existing continuous acquisition/polling model (C_DSV / C_WFE); the trace
improves visibly as frames accrue. *(Sliding-window mean vs equivalent-depth EMA is a spec detail.)*
**Rejected because:** B loses the live feel; C adds surface without a stated need yet.

### DEC_03 — Equivalent-time sampling (ETS)  {#C_RES_DEC_03}

> **Status:** open
> **Date:** 2026-07-15

**Question:** Include equivalent-time sampling (interleaving sub-sample phase-shifted acquisitions of
the periodic signal for finer *temporal* resolution) in this concept?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — Defer to a separate concept + research spike | Keeps this concept shippable; verifies device feasibility before committing |
| B — Include now | Commits to ETS immediately, accepting feasibility risk |
| C — Drop entirely | Real-time QS-raise is the only horizontal lever |

**Decision:** OPEN — see resolution trigger. Working direction: A (defer + spike).
**Rationale:** ETS requires the device to acquire at controlled sub-sample **trigger delays** (phase
diversity). Whether this device exposes a controllable sub-sample delay is **unverified**; committing
now would be building on an unconfirmed capability (a Pre-Concept-Checklist violation).
**Rejected because:** B risks designing around a capability the device may not have; C forecloses the
biggest horizontal-resolution win for periodic signals prematurely.
**Resolution trigger:** when horizontal (time) resolution beyond real-time QS is required — run a
`/dev-flow research` spike on device controlled-sub-sample-trigger-delay feasibility, then author a
separate ETS concept.

### DEC_04 — Processing location  {#C_RES_DEC_04}

> **Status:** resolved
> **Date:** 2026-07-15

**Question:** Where does the enhancement pipeline run — backend or frontend?

**Decision:** Backend only (no interview — rule-driven).
**Rationale:** `HardwareAccessOnlyThroughDeviceService` (must) + the thin-frontend principle (C_WFE)
mandate that signal processing stays in the Python backend; the frontend renders the enhanced frame
like any frame. Also, cross-frame state is far cheaper to hold once in the backend than per client.

### DEC_05 — New concept vs extend C_CAL  {#C_RES_DEC_05}

> **Status:** resolved
> **Date:** 2026-07-15

**Question:** Extend the existing measurement concept (C_CAL) or create a new one?

**Decision:** New concept (C_RES).
**Rationale:** C_CAL is **stateless, per-frame** measurement; this is a **stateful, cross-frame**
accumulation pipeline with a different responsibility and change rate (SRP for documents). C_RES
depends on C_CAL rather than absorbing it.

### DEC_06 — Alignment estimator  {#C_RES_DEC_06}

> **Status:** resolved (in [SP_RES_DEC_01](./resolution_enhancement.sp.md#SP_RES_DEC_01))
> **Date:** 2026-07-15

**Question:** How is the sub-sample alignment offset estimated — full cross-correlation with
parabolic-peak refinement, or period-phase alignment using the detected period?

**Decision:** Cross-correlation over a bounded lag + parabolic sub-sample refinement — settled at
spec altitude (SP_RES_DEC_01).
**Rationale:** Shape-agnostic, tolerates the coarse integer period (used only to bound the lag
search), and yields the correlation coefficient the gate needs for free. Jitter magnitude only tunes
the lag bound/threshold (re-tunable in Verify) — no hardware needed to settle the method.
**Rejected because:** period-phase alignment couples quality to period-estimate accuracy and gives no
natural match-quality signal for gating.

## Changelog

| Date | Change |
|------|--------|
| 2026-07-15 | Initial version — coherent averaging core + SMA; ETS & alignment-estimator left as open decisions. |
