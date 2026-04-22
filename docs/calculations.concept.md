# Concept: Signal Measurements (C_CAL)

> **ID:** C_CAL
> **Status:** active
> **Area:** Python backend
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Philosophy

All signal analysis happens here. Raw ADC samples from the device are meaningless numbers (0–255 or 0–65535); this module gives them physical meaning (millivolts, Hz, seconds). The frequency algorithm mirrors the Android OscillData.java implementation: count positive and negative half-period segments, filter noise, average lengths to get period.

## Domain Model

| Entity | Description |
|--------|-------------|
| Sample | Raw ADC integer value (8-bit: 0..255; 16-bit: 0..65535) |
| Segment | Consecutive samples all above (positive) or below (negative) the mean |
| Voltage | Physical millivolt value derived from ADC code, V/div, and sample bit depth |
| Measurement | Named physical quantity with value and unit: `{v: float, u: str}` |
| Hex encoding | Compact string representation: 2 hex chars per 8-bit sample, 4 per 16-bit |

## Mechanisms

**Hex encoding:** Samples are encoded as a flat hex string for HTTP transport (e.g., 256 samples → 512 chars vs ~1280 chars as a JSON array). The codec is symmetric: `samples_to_hex` / `samples_from_hex` (Python), `samplesToHex` / `hexToSamples` (JavaScript).

**ADC-to-volts:** `samples_to_millivolts()` maps ADC code to millivolts using: center = max_code/2; scale = (v_div_mv × 8) / 2; result = (sample - center) / center × scale. This gives a symmetric ±(v_div×4) mV range around zero.

**Frequency via segments:** `calculate_frequency_and_period()` computes average amplitude as threshold, counts positive/negative runs (segments), filters short segments (noise), averages filtered lengths, derives period = avg_len × t_step_ms, frequency = 1000/period_ms. Requires ≥3 total segments.

**Composite measurements:** `calculate_measurements()` assembles freq, period, Vpp, Vmin, Vmax, Vavg from a frame dict. t_step_ms is computed from config (t_div_ms × h_divs / len(samples)) to correctly handle peak mode doubling.

## Integration Points

- **Depends on:** `converters` (get_voltage_mv, get_time_ms)
- **Used by:** `device_service` (frame processing), `auto_adjust` (frequency for T/div), `web_api/main` (frame endpoint)
