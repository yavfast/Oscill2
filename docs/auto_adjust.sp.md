# Specification: Auto Adjustment (SP_AAJ)

> **ID:** SP_AAJ
> **Status:** active
> **Implements:** C_AAJ
> **Depends on specs:** SP_CAL, SP_CVT
> **Used by specs:** SP_WEB
> **Changelog:**
> - Initialized from existing codebase via onboard procedure (2026-04-22)
> - 2026-07-15 — PL_AUDIT_WEB code-audit propagation: auto_adjust_multiple now reports success honestly (dict helpers judged by `success`, any helper failed if apply_config warned "config update failed"); recursive v_div/t_div have a MAX_AUTO_ITERATIONS depth guard; find_next_vdiv/tdiv are thin wrappers over shared find_next_step

## Constants

| Name | Value | Meaning |
|------|-------|---------|
| VDIV_VALUES_MV | [20,50,100,200,500,1000,2000,5000,10000] | Valid V/div steps |
| TDIV_VALUES_MS | [0.1,0.2,0.5,1,2,5,10,20,50,100,200,500] | Valid T/div steps |
| FILL_FACTOR_MIN | 0.2 | Minimum vertical fill ratio |
| FILL_FACTOR_MAX | 0.8 | Maximum vertical fill ratio |
| SEGMENTS_COUNT_MIN | 4 | Min half-periods on screen |
| SEGMENTS_COUNT_MAX | 8 | Max half-periods on screen |
| V_OFFSET_CENTER | 128 | Center raw offset |
| MAX_AUTO_ITERATIONS | len(TDIV_VALUES_MS)+2 (=14) | Recursion depth cap for auto_adjust_v_div/_t_div |

## Contracts

### find_next_vdiv(current_mv, direction: +1|-1) → Optional[float]
- Returns adjacent V/div step or None at boundary.
- **(PL_AUDIT_WEB)** Now a thin wrapper over the shared `find_next_step(values, current, direction)`
  helper (internal refactor; public contract unchanged).

### find_next_tdiv(current_ms, direction: +1|-1) → Optional[float]
- Returns adjacent T/div step or None at boundary.
- **(PL_AUDIT_WEB)** Thin wrapper over shared `find_next_step` (see find_next_vdiv).

### auto_adjust_v_div(device_service, config) → bool
- Recursively adjusts until fill_factor in [0.2, 0.8]. Modifies config in-place.
- Returns False if no signal (no frame or no measurements), or if an `apply_config` write fails.
- **(PL_AUDIT_WEB)** Recursion bounded by `MAX_AUTO_ITERATIONS` depth guard (oscillation/RecursionError guard).

### auto_adjust_t_div(device_service, config) → bool
- Recursively adjusts until segments_count in [4, 8]. Modifies config in-place.
- **(PL_AUDIT_WEB)** Recursion bounded by `MAX_AUTO_ITERATIONS` depth guard.
- **Known bug:** reads t_step_ms from frame dict (missing key, fallback 0.001ms is wrong).

### auto_adjust_v_offset(device_service, config) → Dict
- Single-shot centering. Returns `{success, old_value, new_value, reason}`.

### auto_adjust_trigger_level(device_service, config) → Dict
- Sets trigger to sample mean. Returns `{success, old_value, new_value, reason}`.

### auto_adjust_multiple(device_service, config, types: List[str]) → bool
- Valid type values: `'v_div'`, `'v_offset'`, `'trigger'`, `'t_div'`
- Applied in fixed order regardless of input order.
- Returns False if no frame available or any adjustment fails.
- **(PL_AUDIT_WEB) Honest success reporting:** dict-returning helpers (v_offset, trigger) are judged
  by their `success` flag — not mere truthiness of the returned dict; any helper is treated as failed
  if `apply_config` returned a `"config update failed"` warning (checked via `_apply_failed`, since
  `_apply_config_internal` swallows hardware write errors into a warning rather than raising).
  Previously a failed adjustment could be reported as success.

## Validation Rules

- `auto_adjust_multiple` calls `ensure_frame_available()` — returns False if no frame within timeout
- **(PL_AUDIT_WEB)** Max recursion depth for both v_div and t_div = `MAX_AUTO_ITERATIONS`
  (= len(TDIV_VALUES_MS) + 2 = 14), enforced by an explicit `_depth` guard.
