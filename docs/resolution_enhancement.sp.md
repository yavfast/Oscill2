# Periodic-Signal Resolution Enhancement — Specification  {#SP_RES}

> **Code:** SP_RES
> **Status:** draft
> **Created:** 2026-07-15
> **Updated:** 2026-07-15
>
> **Concept:** [C_RES](./resolution_enhancement.concept.md)
> **Depends on:** [SP_CAL](./calculations.sp.md), [SP_DSV](./device_service.sp.md), [SP_CVT](./converters.sp.md)
> **Used by:** [SP_WEB](./web_api.sp.md)
> **Plan:** [PL_RES](./resolution_enhancement.plan.md) (draft)
>
> Defines the data structures, contracts, and validation rules for raising the *effective*
> resolution of a periodic signal's oscillogram: an **on-read** coherent sliding-window average of
> aligned, gated frames, plus an optional per-frame moving-average smoother. The enhanced trace is
> exposed as an `enhanced` block augmenting the newest frame in `/api/frames`, carried as 16-bit
> fixed-point samples over the existing hex codec. The raw single-frame path is unchanged.

## 01. Data Structures  {#SP_RES_01}

> Implements: [C_RES_02](./resolution_enhancement.concept.md#C_RES_02)

### 01_01. EnhancementSettings  {#SP_RES_01_01}

User-facing enhancement controls. Stored in the device-service **config snapshot** (extends
[SP_DSV ConfigDict](./device_service.sp.md#SP_DSV_01)); set through `apply_config`; echoed in
`get_status` / `/api/frames` config; silently clamped exactly like existing numeric params.

Fields:
| Field | Type | Required | Default | Constraints | Description |
|-------|------|----------|---------|-------------|-------------|
| enh_enabled | bool | no | false | — | Master switch. When false, no `enhanced` block is emitted; raw path only. |
| enh_depth | int | no | 16 | 2..64 (clamped) | Target rolling window depth N — number of most-recent same-config frames considered for the average. |
| enh_sma_window | int | no | 1 | 1..63, odd (clamped; even → nearest lower odd) | Moving-average window W over the sample axis. 1 = smoother off. |

Invariants:
- `enh_depth` and `enh_sma_window` are always within their ranges after `apply_config` (clamp, never reject).
- Changing any of these three fields is a config change → increments `cfg_id` → clears the frame buffer (existing SP_DSV behaviour); the accumulator is stateless on-read, so no extra reset is needed.
- These fields never reach a device register (backend-only, C_RES_DEC_04); they are not passed to `oscill_client`.

### 01_02. EnhancedBlock  {#SP_RES_01_02}

The enhancement result, attached as `enhanced` on the **newest** frame only in a `/api/frames`
response, and only when `enh_enabled` is true. It never replaces the raw `samples`/`samples_hex` of
the frame — it is additive.

Fields:
| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| averaging_active | bool | yes | — | True if a coherent average of ≥2 aligned frames was produced. |
| smoothing_active | bool | yes | — | True if the SMA smoother was applied (W>1). |
| status_reason | enum | yes | see below | Why averaging is/*isn't* active. `"ok"` when active. |
| samples_hex | string | yes | 4 hex chars/sample | Enhanced trace as 16-bit fixed-point, big-endian, via the existing 2-byte hex codec (SP_CAL samples_to_hex, sample_bytes=2). |
| sample_bits | int | yes | = 16 | Fixed 16 — enables SP_CAL samples_to_millivolts to reuse its 16-bit center path unchanged. |
| sample_bytes | int | yes | = 2 | Fixed 2. |
| length | int | yes | = len(newest raw samples) | Enhanced trace has the same length as the reference frame. |
| frames_accumulated | int | yes | 0..enh_depth | Accepted+aligned frames folded in (includes the reference). |
| frames_rejected | int | yes | ≥0 | Frames in the window rejected by the gate. |
| mean_correlation | float | yes | 0.0..1.0 | Mean alignment correlation over accepted non-reference frames (1.0 if only the reference). |
| effective_bits_gain | float | yes | ≥0.0 | Estimated added vertical bits = `0.5 · log2(max(1, frames_accumulated))`. |
| depth_requested | int | yes | = enh_depth | Echo of the requested window depth. |

`status_reason` ∈ { `"ok"`, `"not-periodic"`, `"peak-mode"`, `"insufficient-frames"`, `"error"` }.

Invariants:
- `averaging_active == (status_reason == "ok")`.
- When `averaging_active` is false, `samples_hex` still carries a valid trace: the SMA-smoothed
  newest frame (if W>1) or the newest frame upscaled to 16-bit (if W=1). So an `enhanced` block, once
  emitted, always renders.
- `samples_hex` decodes to exactly `length` 16-bit samples.
- The enhanced samples are the averaged/smoothed value scaled by 257 (0..255 → 0..65535), so
  `samples_to_millivolts(enhanced, 16, config)` yields the same physical mV mapping as the raw 8-bit
  trace (see SP_RES_03_03).

### 01_03. Enhancement value scaling (16-bit fixed-point)  {#SP_RES_01_03}

The enhancement pipeline works in the real-valued 8-bit ADC domain (0.0..255.0). For transport each
output sample `x` (a float in 0..255) is encoded as `clamp(round(x · 257), 0, 65535)` — a 16-bit
integer — because `255 · 257 = 65535` maps the 8-bit full scale exactly onto the 16-bit full scale.
Decoding for display divides by 257 (or, equivalently, feeds the 16-bit value straight into the
existing 16-bit mV conversion — no rescale needed there). The factor 257 preserves ~8 bits of
sub-quantization detail recovered by averaging.

### 01_04. config.limits additions  {#SP_RES_01_04}

Extends [SP_DSV ConfigDict.limits](./device_service.sp.md#SP_DSV_01) so the client can present valid
ranges (informativeness + the clamp source):

| limits key | shape | Source |
|-----|-----|--------|
| enh_depth | `{min:2, max:64}` | structural (bounded to cap per-poll cost) |
| enh_sma_window | `{min:1, max:63}` | structural |

## 02. Contracts  {#SP_RES_02}

### 02_01. apply_config — enhancement settings  {#SP_RES_02_01}

Purpose: accept the three EnhancementSettings keys as part of an existing `apply_config` call.

Input (added to the existing `changes` dict — [SP_DSV apply_config](./device_service.sp.md#SP_DSV_02)):
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| enh_enabled | bool | no | coerced to bool |
| enh_depth | int | no | clamped to [2,64] |
| enh_sma_window | int | no | clamped to [1,63], forced odd |

Output: unchanged `apply_config` shape — `(status_dict, warnings_list)`; the reconciled config now
includes the three fields plus their `limits` entries.

Errors:
| Code | Condition | Guidance |
|------|-----------|----------|
| (none) | out-of-range value | Silently clamped — no warning (consistent with v_offset/trigger_level clamp). |
| RuntimeError | not connected | Existing apply_config behaviour, unchanged. |

Processing logic (pseudocode):
    coerce enh_enabled to bool if present
    if enh_depth present: enh_depth = clamp(int(enh_depth), 2, 64)
    if enh_sma_window present: w = clamp(int(enh_sma_window), 1, 63); if w even: w = w - 1; enh_sma_window = w
    store into config snapshot; cfg_id++ ; clear frame buffer (existing path)

### 02_02. estimate_alignment_offset  {#SP_RES_02_02}

Purpose: find the sub-sample shift that best aligns a candidate frame to the reference, with a match
quality. (Settles C_RES_DEC_06 → SP_RES_DEC_01: cross-correlation + parabolic refinement.)

Input:
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| candidate | float[] | yes | same length as reference |
| reference | float[] | yes | length ≥ 4 |
| max_lag | int | yes | 1 ≤ max_lag ≤ len/2 |

Output:
| Field | Type | Description |
|-------|------|-------------|
| shift | float | Sub-sample lag (candidate relative to reference); positive = candidate lags. |
| correlation | float | Normalized cross-correlation coefficient at the peak, 0.0..1.0. |

Processing logic (pseudocode):
    a = candidate - mean(candidate);  b = reference - mean(reference)
    FOR lag IN [-max_lag .. +max_lag]:
        r[lag] = normalized_cross_correlation(a, b, lag)   # Pearson at integer lag
    peak = argmax(r)
    # parabolic sub-sample refinement around the integer peak:
    shift = peak + 0.5*(r[peak-1]-r[peak+1]) / (r[peak-1]-2*r[peak]+r[peak+1])   # guard denom≈0 → shift=peak
    correlation = r[peak]
    RETURN {shift, correlation}

### 02_03. accept_frame (gate)  {#SP_RES_02_03}

Purpose: decide whether an aligned candidate is a valid instance of the periodic waveform (rejects
false triggers / mismatched frames — concept items #5/#4).

Input: `correlation` (from 02_02), `shift`, `max_lag`, `acceptance_threshold` (internal constant,
default 0.7).

Output: `bool accept`.

Processing logic:
    accept = (correlation >= acceptance_threshold) AND (abs(shift) <= max_lag)

Notes: `acceptance_threshold` is an internal tuning constant (not user-facing — Minimality); it may
be re-tuned during Verify against measured trigger-jitter. The reference frame itself is always
accepted with correlation 1.0, shift 0.

### 02_04. compute_enhanced_trace  {#SP_RES_02_04}

Purpose: the heart — produce the EnhancedBlock on-read from the buffered frame window. Pure function
of its inputs; performs **no** device I/O and holds **no** persistent state (C_RES_DEC_02 /
SP_RES_DEC_02).

Input:
| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| window | Frame[] | yes | most-recent-first; already fetched from the ring buffer |
| config | ConfigDict | yes | current cached config (v_div, t_div, sw_mode, enh_*, samples_per_div, h_divs) |

Output: `EnhancedBlock` (SP_RES_01_02). Never raises — internal error → `status_reason="error"`,
`averaging_active=false`, `samples_hex` = 16-bit upscale of the newest frame.

Processing logic (pseudocode):
    IF NOT config.enh_enabled: RETURN (no block)
    newest = window[0]
    base = float(newest.samples)                       # reference grid
    W = config.enh_sma_window
    reason = "ok"; accumulated = 1; rejected = 0; corr_sum = 0.0; corr_n = 0

    IF newest is peak-mode (sw_mode in {PEAK,PEAK_HI} or has samples_peak_*):
        reason = "peak-mode"                            # out of initial scope (C_RES_03_02)
    ELSE:
        period = SP_CAL.calculate_frequency_and_period(newest.samples, t_step).period
        IF period IS None: reason = "not-periodic"
        ELSE:
            period_samples = period_seconds / (t_step_seconds)
            max_lag = clamp(round(period_samples/2), 1, len(base)//2)
            sum = copy(base); ref = base
            FOR f IN window[1:] up to (enh_depth-1) more, same cfg_id AND same length as newest:
                {shift, corr} = estimate_alignment_offset(f.samples, ref, max_lag)
                IF accept_frame(corr, shift, max_lag):
                    aligned = resample(f.samples, +shift)   # linear interp onto ref grid
                    sum += aligned; accumulated += 1; corr_sum += corr; corr_n += 1
                ELSE:
                    rejected += 1
            IF accumulated >= 2: base = sum / accumulated
            ELSE: reason = "insufficient-frames"

    out = moving_average(base, W) IF W > 1 ELSE base     # SP_RES_02_05
    averaging_active = (reason == "ok" AND accumulated >= 2)
    samples16 = [clamp(round(x*257),0,65535) FOR x IN out]
    RETURN EnhancedBlock{
        averaging_active, smoothing_active=(W>1), status_reason=reason,
        samples_hex = SP_CAL.samples_to_hex(samples16, 2), sample_bits=16, sample_bytes=2,
        length=len(out), frames_accumulated=accumulated, frames_rejected=rejected,
        mean_correlation=(corr_sum/corr_n IF corr_n>0 ELSE 1.0),
        effective_bits_gain=0.5*log2(max(1,accumulated)), depth_requested=config.enh_depth }

### 02_05. moving_average (SMA)  {#SP_RES_02_05}

Purpose: symmetric moving average over the sample axis (auxiliary smoother, C_RES item #2).

Input: `samples: float[]`, `window: int (odd, ≥1)`.
Output: `float[]` of the same length.

Processing logic:
    IF window <= 1: RETURN samples
    half = window // 2
    FOR i: out[i] = mean(samples[max(0,i-half) .. min(n-1,i+half)])   # edge windows shrink
    RETURN out

Notes: window edges use a shrinking window (no padding), so length is preserved and ends are not
biased toward zero.

### 02_06. /api/frames — enhanced augmentation  {#SP_RES_02_06}

Purpose: extend the existing `/api/frames` response ([SP_WEB](./web_api.sp.md)) so the **newest**
returned frame carries an `enhanced` block when enhancement is enabled.

Input: unchanged (`since`, `limit`, `format`).

Output: unchanged response, except the newest processed frame gains `enhanced: EnhancedBlock` when
`config.enh_enabled` is true (absent otherwise). Measurements for the newest frame are computed on
the **enhanced** trace when `averaging_active` (so freq/Vpp/… reflect what is displayed); otherwise
on the raw trace, unchanged.

Errors: same as existing `/api/frames`; a failure inside enhancement never fails the request — it
degrades to no `enhanced` block (the raw frames still return).

Processing logic (pseudocode):
    ... existing frame processing ...
    IF service.enh_enabled AND processed is the newest frame:
        window = service.get_frames(...).frames  (most-recent-first, up to enh_depth)
        block = compute_enhanced_trace(window, current_config)
        IF block: processed["enhanced"] = block
                  IF block.averaging_active:
                      processed["measurements"] = calculate_measurements(enhanced_as_frame, current_config)

## 03. Validation Rules  {#SP_RES_03}

### 03_01. Settings validation  {#SP_RES_03_01}
- `enh_depth` clamped to [2,64]; `enh_sma_window` clamped to [1,63] then forced odd; `enh_enabled`
  coerced to bool. No rejection, no warning (silent clamp).

### 03_02. Window eligibility  {#SP_RES_03_02}
- Only frames whose `cfg_id` equals the newest frame's `cfg_id` are eligible (config-stable subset).
- Only frames whose sample length equals the newest frame's length are eligible.
- At most `enh_depth` frames (newest first) are considered.

### 03_03. Physical-value consistency  {#SP_RES_03_03}
- Enhanced samples are scaled ×257 and declared 16-bit so that `samples_to_millivolts(enhanced,16,cfg)`
  equals the 8-bit mapping to within rounding. This MUST hold — it is what lets the frontend reuse the
  existing mV path.

### 03_04. Non-destructiveness  {#SP_RES_03_04}
- The raw `samples`/`samples_hex` and existing frame fields are never modified or removed by
  enhancement. `enhanced` is strictly additive and only on the newest frame.

## 04. State Transitions  {#SP_RES_04}

### 04_01. Enhancement activity  {#SP_RES_04_01}

There is no persistent accumulator state (on-read). "Activity" is derived per response:

State diagram (per /api/frames poll):
    enh_enabled=false ──► (no enhanced block)
    enh_enabled=true ──► emit enhanced block, with:
        peak-mode newest            ──► averaging_active=false, reason="peak-mode"
        no detectable period        ──► averaging_active=false, reason="not-periodic"
        <2 frames accepted/eligible ──► averaging_active=false, reason="insufficient-frames"
        internal error              ──► averaging_active=false, reason="error"
        else                        ──► averaging_active=true,  reason="ok"

Transition rules:
| From | To | Condition | Side effects |
|------|----|-----------|-------------|
| any | reset (implicit) | config change (incl. enh_* change) | cfg_id++ → frame buffer cleared → window empties → averaging_active=false until buffer refills |
| averaging_active=false | true | ≥2 same-config frames align above threshold | enhanced trace becomes a coherent average; measurements recompute on it |

## 05. Verification Criteria  {#SP_RES_05}

### 05_01. Functional Expectations  {#SP_RES_05_01}
| Contract | Scenario | Input | Expected outcome |
|----------|----------|-------|------------------|
| apply_config | enable + set depth/window | enh_enabled=true, enh_depth=32, enh_sma_window=5 | config echoes enh_*, cfg_id++, buffer cleared |
| apply_config | out-of-range clamp | enh_depth=999, enh_sma_window=8 | stored as 64 and 7 (odd), no warning |
| estimate_alignment_offset | known shift | reference, candidate = reference shifted by +2.4 samples | shift ≈ +2.4 (±0.2), correlation ≈ 1.0 |
| estimate_alignment_offset | uncorrelated | reference, random candidate | correlation low (< threshold) |
| accept_frame | good match | correlation 0.95, shift 1.0, max_lag 20 | accept=true |
| accept_frame | false trigger | correlation 0.4 | accept=false |
| compute_enhanced_trace | periodic, noisy | N noisy copies of one sine, aligned | averaging_active=true, output noise stdev ≈ input/√accumulated |
| compute_enhanced_trace | DC / flat | flat samples | averaging_active=false, reason="not-periodic", block still renders |
| compute_enhanced_trace | peak mode | newest has samples_peak_* | averaging_active=false, reason="peak-mode" |
| moving_average | W=5 on step | step signal | edges softened, length preserved, ends not zero-biased |
| /api/frames | enabled | poll with enh_enabled=true | newest frame has `enhanced`; older frames do not |
| /api/frames | disabled | poll with enh_enabled=false | no `enhanced` block anywhere |

### 05_02. Invariant Checks  {#SP_RES_05_02}
| Invariant | Verification method |
|-----------|-------------------|
| Enhanced length = raw length | decode samples_hex → count == len(raw newest samples) |
| ×257 mV consistency (03_03) | mV(enhanced 16-bit) ≈ mV(raw 8-bit) within one 16-bit LSB |
| Non-destructive (03_04) | raw samples_hex byte-identical with vs without enhancement |
| SNR gain | averaged-noise stdev ≤ single-frame stdev / √(0.9·accumulated) on synthetic data |
| effective_bits_gain formula | == 0.5·log2(frames_accumulated) |
| Silent clamp | apply_config with extreme enh_* returns no warning, values in range |

### 05_03. Integration Scenarios  {#SP_RES_05_03}
| Scenario | Preconditions | Steps | Expected result |
|----------|--------------|-------|-----------------|
| Live enhancement on periodic signal | device connected, periodic input | 1. enable enh 2. poll frames repeatedly | frames_accumulated rises to depth; visibly cleaner trace; mean_correlation high |
| Config change resets window | enhancement active | change v_div | next polls: averaging_active=false (buffer cleared) then re-activates as buffer refills |
| False-trigger rejection | noisy signal with occasional bad triggers | enable enh, poll | frames_rejected > 0; averaged trace not blurred by rejected frames |
| Non-periodic fallback | aperiodic input | enable enh | status_reason="not-periodic"; smoothed (if W>1) newest still shown; raw path intact |

### 05_04. Edge Cases and Boundaries  {#SP_RES_05_04}
| Case | Input | Expected behavior |
|------|-------|-------------------|
| Single frame in buffer | window length 1 | averaging_active=false, reason="insufficient-frames", block = upscaled newest |
| enh_depth=2 | two aligned frames | averaging over 2; effective_bits_gain=0.5 |
| Very high frequency | few samples/cycle, period≈2 samples | max_lag≥1; likely low correlation → rejects → insufficient-frames fallback |
| Amplitude clipping | railed samples | averaging proceeds; clipped region unrecovered (not an error) |
| W even (e.g. 8) | enh_sma_window=8 | stored/used as 7 |
| Mixed-length frames in window | buffer spans a config change | only same-cfg_id, same-length frames folded in |

## 06. Reversibility  {#SP_RES_06}

### 06_01. Rollback Strategy  {#SP_RES_06_01}
| Aspect | Rollback approach |
|--------|-------------------|
| Data/state changes | None persistent. On-read compute holds no state; config gains 3 optional fields with safe defaults. Setting `enh_enabled=false` (or removing the fields) fully reverts to raw behaviour. |
| Artifacts | New backend module for the enhancement functions + new frontend controls/decode. Removing them and the 3 config fields is a clean deletion — no migrations, no stored data. |
| Dependent modules | SP_WEB (adds optional `enhanced` block — additive, older clients ignore it); SP_DSV (adds 3 optional config fields + 2 limits entries — additive). Nothing breaks if reverted. |
| External contracts | `/api/frames` gains an **optional, additive** `enhanced` field on the newest frame; the raw contract is unchanged, so existing consumers are unaffected. |

## 07. Design Decisions  {#SP_RES_DEC}

### DEC_01 — Alignment estimator  {#SP_RES_DEC_01}

> **Status:** resolved (closes [C_RES_DEC_06](./resolution_enhancement.concept.md#C_RES_DEC_06))
> **Date:** 2026-07-15

**Question:** How is the sub-sample alignment offset estimated?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — Cross-correlation over a bounded lag + parabolic sub-sample refinement | Robust, shape-agnostic; needs only a coarse period to bound the lag search |
| B — Period-phase alignment from the detected period | Cheaper but depends on an accurate period estimate and a detectable phase reference |

**Decision:** A — cross-correlation + parabolic refinement.
**Rationale:** Works on any periodic shape, tolerates the coarse integer period from the segment
detector (used only to bound `max_lag`), and yields the correlation coefficient the gate needs for
free. Jitter *magnitude* only tunes `max_lag`/threshold and can be re-tuned in Verify — no hardware
needed to settle the method.
**Rejected because:** B couples alignment quality to period-estimate accuracy and gives no natural
match-quality signal for gating.

### DEC_02 — Compute site & state model  {#SP_RES_DEC_02}

> **Status:** resolved
> **Date:** 2026-07-15

**Question:** Where is the coherent average computed and how is its state held?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — On-read sliding-window, stateless per poll, over the ring buffer | No acq-thread burden; automatic reset (buffer already cleared on config change); recompute per poll |
| B — Producer-side incremental EMA in the acquisition loop | Infinite memory; adds correlation CPU to acq thread + cross-thread state + explicit reset |
| C — Producer-side FIFO ring of aligned frames | Exact window, no recompute, but most state + most acq-thread work |

**Decision:** A — on-read sliding-window *(developer-selected)*.
**Rationale:** Keeps the acquisition thread untouched, needs no cross-thread state, and resets fall
out of the existing buffer-clear-on-config-change behaviour. Per-poll cost (≤64×len mults at ~100 ms)
is negligible.
**Rejected because:** B/C burden the real-time acquisition thread and add stateful concurrency for a
memory characteristic (unbounded history) that isn't required.

### DEC_03 — Enhanced-trace wire representation  {#SP_RES_DEC_03}

> **Status:** resolved
> **Date:** 2026-07-15

**Question:** How does the real-valued enhanced trace reach the frontend?

**Options considered:**
| Option | Consequence |
|--------|-------------|
| A — 16-bit fixed-point (×257) via existing hex codec, in an `enhanced` block on `/api/frames` | Reuses hex transport + 16-bit mV path unchanged; one poll; ~8 sub-quant bits preserved |
| B — JSON float array | Simplest to produce; larger payload; new frontend decode + mV path |
| C — Dedicated `/api/frames/enhanced` endpoint | Clean separation; second poll loop + duplicated plumbing |

**Decision:** A — 16-bit fixed-point hex in `/api/frames` *(developer-selected)*.
**Rationale:** Maximum reuse (`SingleSourceForSharedConstants`, existing hex + mV code), single poll,
additive/optional field so old clients are unaffected. 255×257=65535 makes the scaling exact.
**Rejected because:** B bypasses the hex codec and duplicates the mV path; C adds a second polling
surface for no separation benefit.

## Changelog

| Date | Change |
|------|--------|
| 2026-07-15 | Initial version — on-read sliding-window coherent average + SMA; 16-bit fixed-point hex `enhanced` block; settles concept DEC_06 (alignment) + DEC_02 (compute model). |
