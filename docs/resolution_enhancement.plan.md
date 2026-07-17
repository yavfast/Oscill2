# Implementation Plan: Periodic-Signal Resolution Enhancement  {#PL_RES}

> **Code:** PL_RES
> **Status:** in-progress
> **Created:** 2026-07-15
> **Updated:** 2026-07-15
>
> **Concept:** [C_RES](./resolution_enhancement.concept.md)
> **Specification:** [SP_RES](./resolution_enhancement.sp.md)
> **Depends on:** none (extends SP_DSV / SP_WEB additively)
> **Used by:** —
>
> Implement on-read coherent sliding-window averaging (align → gate → average) of periodic-signal
> frames, plus an optional SMA smoother, exposed as an additive 16-bit-hex `enhanced` block on the
> newest `/api/frames` frame, with backend clamping of three new config fields and a frontend control
> + decode. The raw single-frame path is untouched.

## Goal

When complete: a user can enable resolution enhancement from the web UI, set the rolling depth N and
SMA window W, and — on a stable periodic signal — see a visibly cleaner, higher-effective-resolution
trace whose noise falls ≈√N and whose amplitude carries sub-quantization detail. Trigger jitter is
corrected sub-sample and false-trigger frames are rejected before averaging. Disabling the mode fully
reverts to the raw trace. (Restates the [task_C_RES intent](../.dev_flow/tasks/task_C_RES.md): raise
effective resolution by exploiting periodicity — items #2 SMA, #3 average, #4 offset-correct, #5
false-trigger-reject; #1 QS and #6 ETS are separate efforts.)

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend language | Python 3.14 (project venv) | Project standard (web_oscill backend). |
| Numerics (correlation, average) | **numpy** (already in `requirements.txt`, v2.5.1) | Vectorized/FFT cross-correlation makes the per-poll cost trivial vs pure-Python (up to ~63 frames × lag-window × N per 100 ms poll would be too slow in pure Python). No new dependency. First numpy use in the backend. |
| Enhancement module placement | New Layer-1 module `web_oscill/resolution.py` (pure functions), called from `main.py` `/api/frames` | Mirrors the existing pattern where `main.py` calls `calculations.py` per frame; keeps enhancement pure/testable and off the device path. Depends on `calculations.py` (period + hex), not the reverse — satisfies `LayerDependencyDirection`. See PL_RES_DEC_01. |
| Enhanced-trace transport | 16-bit fixed-point (×257) via existing `samples_to_hex(...,2)` / `hexToSamples(...,2)` | SP_RES_DEC_03 — reuse hex codec + 16-bit mV path (`SingleSourceForSharedConstants`). |
| Config field format | Bare scalars in the config dict (`enh_enabled` bool, `enh_depth`/`enh_sma_window` int) | These are raw control values, not physical `{v,u}` measurements — `StructuredConfigValues` applies `{v,u}` only to physical quantities. |
| Frontend | Vanilla ES modules + Konva; extend `controls/processingControl.js` | `JavaScriptESModulesOnly`, `JavaScriptAsyncAwait`; enhancement UI sits beside the existing SW-mode (Processing) controls. |
| Tests | Standalone script `scripts/test_resolution_enhancement.py` | `PythonTestsAreStandaloneScripts` (no pytest); hardware-free (synthetic frames). |

## Required Knowledge

| Kind | Ref | Applies to | Note |
|------|-----|-----------|------|
| rule | LayerDependencyDirection (must) | P1, P2, P3 | `resolution.py` depends on `calculations`/`converters`; `main`→`resolution`; no reverse/circular |
| rule | HardwareAccessOnlyThroughDeviceService (must) | P1, P3 | enhancement reads buffered frames only; no `OscillClient` access; enh_* never reach a register |
| rule | StructuredConfigValues (must) | P2 | enh_* are bare scalars (raw controls), not `{v,u}` |
| rule | SingleSourceForSharedConstants (should) | P1, P4 | reuse the one hex codec + mV mapping; do not duplicate 257/geometry per language |
| rule | ConsistentDataToPixelMapping (should) | P4 | enhanced trace renders on the same data→pixel mapping as the raw waveform (`i/(N-1)`) |
| rule | PythonTypeHintsOnPublicFunctions / PythonPrivateMethodUnderscore (should) | P1, P2 | public fns typed; internals `_`-prefixed |
| rule | JavaScriptESModulesOnly (must) / JavaScriptAsyncAwait (must) / JS camelCase (must) | P4 | frontend conventions |
| rule | PythonTestsAreStandaloneScripts (prefer) | P5 | new tests are runnable scripts in `scripts/` |
| skill (apply) | signal_processing (current) | P1 | segment-frequency/period detector for the periodicity guard + lag bound; peak-mode 2× expansion → PEAK out of scope; `t_step = total_time_ms/len(samples)` |
| skill (apply) | python_fastapi_patterns (current) | P2, P3 | apply_config clamp pattern, cached-config snapshot, `/api/frames` processing shape |
| skill (create) | — | P1 | if the coherent-averaging + sub-sample-alignment procedure proves reusable, capture it as a `signal_processing` skill entry at the reflection checkpoint |

## Progress

- [x] Phase 1 — Enhancement engine (`web_oscill/resolution.py`)
- [x] Phase 2 — Config wiring + clamp (`web_oscill/device_service.py`)
- [x] Phase 3 — API augmentation (`web_oscill/main.py`)
- [x] Phase 4 — Frontend control + decode/render (`web_oscill/static/js/…`)
- [x] Phase 5 — Hardware-free unit tests (`scripts/test_resolution_enhancement.py`)

## Phases

### Phase 1 — Enhancement engine (`web_oscill/resolution.py`) [DONE]

**Depends on:** none (uses existing `calculations.py`)
**Implements:** [SP_RES_01_02](./resolution_enhancement.sp.md#SP_RES_01_02), [SP_RES_01_03](./resolution_enhancement.sp.md#SP_RES_01_03), [SP_RES_02_02](./resolution_enhancement.sp.md#SP_RES_02_02), [SP_RES_02_03](./resolution_enhancement.sp.md#SP_RES_02_03), [SP_RES_02_04](./resolution_enhancement.sp.md#SP_RES_02_04), [SP_RES_02_05](./resolution_enhancement.sp.md#SP_RES_02_05)
**Verify:** [SP_RES_05_01](./resolution_enhancement.sp.md#SP_RES_05_01) (alignment known-shift, gate accept/reject, average SNR, peak/DC fallback), [SP_RES_05_02](./resolution_enhancement.sp.md#SP_RES_05_02) (length, ×257 mV, SNR gain, effective_bits formula), [SP_RES_05_04](./resolution_enhancement.sp.md#SP_RES_05_04) (single-frame, depth=2, high-freq, clipping, mixed-length) — plus: `compute_enhanced_trace` never raises (→ `status_reason="error"`).

What to create:
| Entity | Module | Purpose |
|--------|--------|---------|
| `estimate_alignment_offset(candidate, reference, max_lag)` | resolution.py | numpy cross-correlation + parabolic sub-sample peak → `(shift, correlation)` |
| `accept_frame(correlation, shift, max_lag, threshold=0.7)` | resolution.py | gate (false-trigger rejection) |
| `moving_average(samples, window)` | resolution.py | symmetric SMA, shrinking edges, length-preserving |
| `compute_enhanced_trace(window, config)` | resolution.py | the on-read heart → `EnhancedBlock` dict |
| `_to_fixed16(values)` | resolution.py | `clamp(round(x*257),0,65535)` scaling (SP_RES_01_03) |

Notes:
- Pure functions; **no** device I/O, **no** persistent state (SP_RES_DEC_02).
- Period guard + `t_step` via `calculations.calculate_frequency_and_period` (reuse; peak-mode → `status_reason="peak-mode"`, DC/no-period → `"not-periodic"`).
- `max_lag = clamp(round(period_samples/2), 1, len//2)`; align only same-`cfg_id`, same-length frames.
- Encode output with `calculations.samples_to_hex(fixed16, sample_bytes=2)`.
- Wrap the body so any internal error yields an inactive block with `status_reason="error"` (mirrors `calculations` silent-degradation + `PythonDeviceServiceWarningsVsExceptions`).

Pseudocode sketch: see [SP_RES_02_04](./resolution_enhancement.sp.md#SP_RES_02_04).

### Phase 2 — Config wiring + clamp (`web_oscill/device_service.py`) [DONE]

**Depends on:** none
**Implements:** [SP_RES_01_01](./resolution_enhancement.sp.md#SP_RES_01_01), [SP_RES_01_04](./resolution_enhancement.sp.md#SP_RES_01_04), [SP_RES_02_01](./resolution_enhancement.sp.md#SP_RES_02_01), [SP_RES_03_01](./resolution_enhancement.sp.md#SP_RES_03_01)
**Verify:** [SP_RES_05_01](./resolution_enhancement.sp.md#SP_RES_05_01) (enable+set, out-of-range clamp), [SP_RES_05_02](./resolution_enhancement.sp.md#SP_RES_05_02) (silent clamp) — plus: changing any enh_* bumps `cfg_id` and clears the buffer (existing path); enh_* never passed to `oscill_client`.

What to implement:
- In `_snapshot_config_locked`: seed defaults `enh_enabled=False`, `enh_depth=16`, `enh_sma_window=1`; add `limits.enh_depth={min:2,max:64}`, `limits.enh_sma_window={min:1,max:63}`.
- In `_apply_config_internal`: accept the three keys; coerce `enh_enabled` to bool; clamp `enh_depth`→[2,64]; clamp `enh_sma_window`→[1,63] then force odd (`w-1` if even). Silent (no warning), consistent with existing v_offset/trigger_level clamp.
- Ensure the three fields survive `_reconcile_display_geometry` (pass-through; they are not delivered-space).

Notes:
- Bare scalars (`StructuredConfigValues`). Backend-only — do not add to any register write path.

### Phase 3 — API augmentation (`web_oscill/main.py`) [DONE]

**Depends on:** Phase 1, Phase 2
**Implements:** [SP_RES_02_06](./resolution_enhancement.sp.md#SP_RES_02_06), [SP_RES_03_04](./resolution_enhancement.sp.md#SP_RES_03_04)
**Verify:** [SP_RES_05_01](./resolution_enhancement.sp.md#SP_RES_05_01) (`/api/frames` enabled/disabled), [SP_RES_05_02](./resolution_enhancement.sp.md#SP_RES_05_02) (non-destructive — raw `samples_hex` byte-identical), [SP_RES_05_03](./resolution_enhancement.sp.md#SP_RES_05_03) (live enhancement, config-change reset, false-trigger, non-periodic fallback).

What to implement:
- Extend `ConfigReq` (main.py request model) with optional `enh_enabled`/`enh_depth`/`enh_sma_window`; forward into `changes` in `api_config` (mirrors existing per-field forwarding).
- In `api_frames`: when `current_config.enh_enabled` and the frame is the **newest**, fetch the window (most-recent-first, up to `enh_depth`) via `service.get_frames`, call `resolution.compute_enhanced_trace(window, current_config)`, attach as `processed["enhanced"]`; when `averaging_active`, recompute `measurements` on the enhanced trace.
- Failure inside enhancement must not fail the request (degrade to no `enhanced` block).

Pseudocode sketch: see [SP_RES_02_06](./resolution_enhancement.sp.md#SP_RES_02_06).

### Phase 4 — Frontend control + decode/render (`web_oscill/static/js/…`) [DONE]

**Depends on:** Phase 3
**Implements:** consumer side of [SP_RES_02_06](./resolution_enhancement.sp.md#SP_RES_02_06) + [SP_RES_01_02](./resolution_enhancement.sp.md#SP_RES_01_02)
**Verify:** [SP_RES_05_03](./resolution_enhancement.sp.md#SP_RES_05_03) (UI toggles enhancement; status indicator reflects `status_reason`/`frames_accumulated`) — plus: enhanced trace decodes via `hexToSamples(hex,2)` and renders aligned to the raw grid (`ConsistentDataToPixelMapping`).

What to implement:
| File | Change |
|------|--------|
| `controls/processingControl.js` | Add "Resolution" controls: Enhance on/off toggle, depth N input, SMA window W input → `onConfigChange({enh_enabled, enh_depth, enh_sma_window})` |
| `api.js` | Forward the three fields in the config POST payload if not already generic |
| `scopeView.js` | If `frame.enhanced` present: decode `samples_hex` with `hexToSamples(...,2)`, map to volts via the existing 16-bit path (÷257 or direct 16-bit mV), draw as the trace; show a small status badge (accumulated / reason) |
| `measurementPanel.js` | (no change — measurements already come from backend) |

Notes:
- Bounds come from `config.limits.enh_depth/enh_sma_window` (fetched, not hardcoded — `SingleSourceForSharedConstants`).

### Phase 5 — Hardware-free unit tests (`scripts/test_resolution_enhancement.py`) [DONE]

**Depends on:** Phase 1, Phase 2, Phase 3
**Implements:** verification of Phases 1–3
**Verify:** [SP_RES_05_01](./resolution_enhancement.sp.md#SP_RES_05_01), [SP_RES_05_02](./resolution_enhancement.sp.md#SP_RES_05_02), [SP_RES_05_04](./resolution_enhancement.sp.md#SP_RES_05_04) — all rows exercised on synthetic data.

What to test (standalone, synthetic frames — no device):
- `estimate_alignment_offset`: reference vs reference-shifted-by-2.4 → shift≈2.4 (±0.2), corr≈1.0; random → corr<0.7.
- `accept_frame`: (0.95,1.0)→accept; (0.4,…)→reject.
- `moving_average`: W=5 length preserved, ends not zero-biased.
- `compute_enhanced_trace`: N noisy sine copies → `averaging_active`, output stdev ≈ input/√accumulated; flat→`not-periodic`; peak frame→`peak-mode`; single frame→`insufficient-frames`; block always decodes to `length` samples.
- ×257 mV consistency: `samples_to_millivolts(enhanced,16,cfg)` ≈ 8-bit mapping within 1 LSB.
- `effective_bits_gain == 0.5·log2(frames_accumulated)`.
- apply_config clamp: enh_depth=999→64, enh_sma_window=8→7, no warning.

## Backlog

- **PEAK / PEAK_HI mode enhancement** — return when: min/max-envelope averaging is needed (concept keeps it out of initial scope; block returns `status_reason="peak-mode"`).
- **Equivalent-time sampling (ETS)** — return when: horizontal resolution beyond real-time QS is required → run the device sub-sample-trigger-delay feasibility spike, then a separate concept ([C_RES_DEC_03](./resolution_enhancement.concept.md#C_RES_DEC_03)).
- **QS-raise (higher horizontal resolution)** — return when: `TD_20260715_110813_higher-hres-qs` is scheduled (separate config-lever effort).
- **`acceptance_threshold` as user-facing config** — return when: Verify shows the fixed 0.7 default is inadequate across signal types (currently internal constant — Minimality).

## Design Decisions  {#PL_RES_DEC}

### DEC_01 — Enhancement module placement & call site  {#PL_RES_DEC_01}

> **Status:** resolved (not contested — follows an existing pattern; no interview)
> **Date:** 2026-07-15

**Question:** Where does the enhancement code live and who invokes it per poll?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — New Layer-1 module `resolution.py`, invoked from `main.py` `/api/frames` | Pure/testable; mirrors existing `main.py`→`calculations.py` per-frame call; off the device path |
| B — Inside `device_service.py` | Couples pure DSP to the concurrency/hardware firewall; harder to unit-test hardware-free |

**Decision:** A — new `resolution.py`, called from `main.py`.
**Rationale:** Matches how `calculate_measurements` is already called from `api_frames`; keeps the DSP pure (numpy in, dict out) and directly unit-testable with synthetic frames; respects `LayerDependencyDirection` (`resolution`→`calculations`/`converters`; `main`→`resolution`). enh_* config still lives in and is clamped by `device_service` (Phase 2).
**Rejected because:** B mixes signal processing into the device concurrency firewall and complicates hardware-free testing.

## Changelog

| Date | Change |
|------|--------|
| 2026-07-15 | Initial version — 5 phases (engine / config / API / frontend / tests); numpy chosen (existing dep); module-placement decision recorded. |
