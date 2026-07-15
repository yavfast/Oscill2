# Specification: Signal Measurements (SP_CAL)

> **ID:** SP_CAL
> **Status:** active
> **Implements:** C_CAL
> **Depends on specs:** SP_CVT
> **Used by specs:** SP_DSV, SP_AAJ, SP_WEB
> **Changelog:**
> - Initialized from existing codebase via onboard procedure (2026-04-22)
> - 2026-07-15 code-audit reconciliation (PL_AUDIT_WEB): corrected samples_to_millivolts degenerate case — returns zeros (not []) when center ≤ 0; branch is effectively dead
> - 2026-07-15 — PL_AUDIT_WEB code-audit propagation: documented calculate_frequency_and_period both-sides invariant (freq=None if either filtered segment list is empty, avoiding ~2x-inflated frequency on asymmetric duty cycles)

## Contracts

### samples_to_hex(samples: List[int], sample_bytes: int = 1) → str
- 1-byte: 2 hex chars/sample; 2-byte: 4 hex chars/sample. Empty → "".

### samples_from_hex(hex_str: str, sample_bytes: int = 1) → List[int]
- Parses hex string back to integers. Empty → [].

### samples_to_millivolts(samples, sample_bits, config) → List[float]
- Formula: `((s - center) / center) × (v_div_mv × 4)` where center = (2^sample_bits - 1) / 2
- Returns [] if samples empty.
- Degenerate branch: if center ≤ 0, returns a list of `0.0` (one per sample), not []. Since
  center = (2^sample_bits - 1) / 2, this branch is effectively dead for any sample_bits ≥ 1.

### calculate_segments(samples, threshold) → tuple[List[int], List[int]]
- Returns (pos_segments, neg_segments): lists of consecutive-run lengths above/below threshold.
- Both lists are empty if samples is empty.

### calculate_frequency_and_period(samples, t_step_ms) → Dict
- Output: `{freq: Optional[float], period: Optional[float], segments_count: int}`
- `freq` and `period` are None if segments_count < 3 or all segments filtered.
- **Both-sides invariant (PL_AUDIT_WEB):** after noise-filtering, frequency is computed ONLY if BOTH
  the positive and negative filtered segment lists are non-empty. A full period is one positive run
  PLUS one negative run; if a strongly asymmetric duty cycle wipes out one side, the function returns
  `freq=None` (and `period=None`) rather than treating the missing side as 0 — which previously
  yielded a half-period and a ~2x-inflated frequency. `segments_count` is still reported in all cases.
- `freq` in Hz; `period` in seconds.

### calculate_measurements(frame, config) → Dict
- Input: frame dict (must have `samples`, `sample_bits`); config dict (must have `v_div`, `t_div`)
- Output: `{freq?, period?, v_pp, v_max, v_min, v_avg}` — each as `{v: float, u: str}`
- Returns {} if frame is None or has no samples.
- `freq` and `period` absent if signal is below frequency detection threshold.

## Validation Rules

- Frequency calculation requires ≥3 segments after noise filtering
- All frequency/period calculations are wrapped in try/except — errors silently return None values
- h_divs defaults to config.get("h_divs", 8) — always 8 in practice

## Known Issue

`auto_adjust_t_div` calls `calculate_frequency_and_period` with `frame.get('t_step_ms', 0.001)` but DeviceService frames do not include `t_step_ms`. See issues.md #1.
