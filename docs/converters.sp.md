# Specification: Unit Conversion (SP_CVT)

> **ID:** SP_CVT
> **Status:** active
> **Implements:** C_CVT
> **Depends on specs:** —
> **Used by specs:** SP_CAL, SP_DSV, SP_AAJ, SP_WEB
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Data Structures

### PREFIX_MAP: Dict[str, float]
| Key | Value |
|-----|-------|
| "p" | 1e-12 |
| "n" | 1e-9 |
| "u" | 1e-6 |
| "m" | 1e-3 |
| "_" | 1.0 |
| "k" | 1e3 |
| "M" | 1e6 |

### QUANTITIES: Set[str]
Values: `{"V", "s", "Hz", "_"}`

### Unit String Format
`unit: str` — either a bare quantity key OR a single-char prefix followed by a quantity key.
Examples: `"V"`, `"mV"`, `"ms"`, `"kHz"`

### Structured Value
```
{
  "v": float,    # numeric value
  "u": str       # unit string
}
```

## Contracts

### parse_unit(unit: str) → tuple[str, str]
- **Input:** unit string
- **Output:** (quantity, prefix_code) — e.g., `("V", "m")` for `"mV"`
- **Errors:** `ValueError("Unsupported unit: {unit}")` for unrecognized strings

### convert(value: float, from_unit: str, to_unit: str) → float
- **Input:** value in from_unit
- **Output:** value in to_unit, rounded to 10 decimal places
- **Errors:**
  - `ValueError` from parse_unit if unit is invalid
  - `ValueError("Cannot convert between different quantities: ...")` if quantities differ
- **Invariant:** `convert(x, u, u) == x` for any valid unit u

### get_voltage_mv(config: dict) → float
- **Input:** config dict — must contain `"v_div"` key with `{v, u}` value
- **Output:** voltage-per-division in millivolts
- **Errors:**
  - `KeyError("Missing 'v_div' configuration entry")` if key absent
  - `TypeError("'v_div' entry must be a mapping...")` if not a dict
  - `KeyError("'v_div' entry must contain 'v' and 'u' keys")` if sub-keys missing

### get_time_ms(config: dict) → float
- **Input:** config dict — must contain `"t_div"` key with `{v, u}` value
- **Output:** time-per-division in milliseconds
- **Errors:** Same pattern as get_voltage_mv (key = "t_div")

## Validation Rules

- Both from_unit and to_unit must be valid unit strings (pass parse_unit)
- from_unit and to_unit must represent the same physical quantity
- Config entries must be `{v: number, u: str}` dicts; missing keys raise descriptive errors
