# Plan: Unit Conversion (PL_CVT)

> **ID:** PL_CVT
> **Status:** completed
> **Implements:** SP_CVT
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Technology Decisions

- **Language:** Python 3.10+ (uses `tuple[str, str]` type hint syntax requiring 3.10+)
- **Dependencies:** stdlib only — no external libraries needed for pure arithmetic
- **Precision:** `round(result, 10)` to suppress IEEE 754 floating-point noise

## Implementation Phases

- [DONE] Define PREFIX_MAP and QUANTITIES constants
- [DONE] Implement parse_unit() with quantity/prefix splitting
- [DONE] Implement convert() with quantity validation and factor ratio
- [DONE] Implement _extract_structured_entry() helper
- [DONE] Implement get_voltage_mv() and get_time_ms() convenience wrappers

## Backlog

- Consider adding `get_freq_hz(config)` convenience function for symmetry with get_voltage_mv / get_time_ms (low priority — frequency is not currently in config dicts)
- Expose unit conversion via `/api/convert` endpoint for frontend use (currently frontend has its own independent format.js implementation)
