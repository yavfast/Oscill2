# Plan: Signal Measurements (PL_CAL)

> **ID:** PL_CAL
> **Status:** completed
> **Implements:** SP_CAL
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Technology Decisions

- **Language:** Python 3.10+; no numpy in calculations.py (numpy is in requirements but not imported here)
- **Frequency algorithm:** segment counting (matches Android OscillData.java) — chosen over FFT for simplicity and no dependency
- **Hex encoding:** plain string operations — fast enough for 256-sample arrays

## Implementation Phases

- [DONE] Hex encode/decode functions
- [DONE] ADC-to-millivolt conversion
- [DONE] Segment detection and length calculation
- [DONE] Noise filtering (short segment removal)
- [DONE] Frequency/period from segment averages
- [DONE] Composite calculate_measurements() with all standard metrics

## Backlog

- Fix: `auto_adjust_t_div` uses wrong t_step_ms (Issue #1) — add t_step_ms to frame payload in DeviceService or compute in auto_adjust from config.
- Consider computing RMS voltage alongside Vavg for AC signals.
- The segment-counting algorithm returns None if signal has <3 segments (DC, very low freq). A DC detection path that returns freq=0 would improve UX.
