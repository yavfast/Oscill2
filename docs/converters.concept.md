# Concept: Unit Conversion (C_CVT)

> **ID:** C_CVT
> **Status:** active
> **Area:** Python backend
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Philosophy

A small but load-bearing utility: every physical measurement value that flows between device registers, the HTTP API, and the frontend carries a unit. The conversion module enforces a universal, unit-aware value representation using SI prefixes. Any value can be converted to any compatible unit without loss of precision, and the system fails loudly (ValueError) if incompatible quantities are mixed.

## Domain Model

| Entity | Description |
|--------|-------------|
| Quantity | Physical quantity kind: Voltage (V), Time (s), Frequency (Hz), or dimensionless (_) |
| Prefix | SI prefix multiplier: pico (p), nano (n), micro (u), milli (m), base (_), kilo (k), mega (M) |
| Unit string | Composed form: prefix + quantity, e.g., "mV" = "m"+"V", "ms" = "m"+"s" |
| Structured value | `{v: number, u: unit_string}` — the canonical wire format for physical values |

## Mechanisms

**Universal conversion:** `convert(value, from_unit, to_unit)` parses both units into (quantity, prefix) pairs, verifies matching quantities, then applies the ratio of prefix factors. The result is rounded to 10 decimal places to suppress floating-point noise.

**Structured config extraction:** `get_voltage_mv(config)` and `get_time_ms(config)` are convenience functions that unwrap the `{v, u}` dict format, invoke convert(), and return a plain float in the requested unit.

## Integration Points

- **Used by:** `calculations` (voltage conversion), `device_service` (config value conversion), `auto_adjust` (V/div and T/div arithmetic), `web_api/main` (implicit via device_service)
- **Depends on:** nothing

## Invariants

- Unit strings not matching `QUANTITIES` or `{prefix}{quantity}` form → ValueError
- Cross-quantity conversion (e.g., V→s) → ValueError
- Empty input list → empty output (graceful degradation)
