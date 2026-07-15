# Oscill2 — Framework Map

> **Maintained by:** onboard + `audit code` scope (not hand-authored per feature).
> **Loaded as code-touch context** alongside `_index.md`. Overview only — enforceable
> detail lives in `.dev_flow/rules/` and `.dev_flow/skills/`, linked below.
> **Last updated:** 2026-07-15 (PL_AUDIT_WEB code-audit propagation — DeviceService boundary restored).

## System shape

Three independent clients over one OBEX-over-serial oscilloscope device:
Android app · Python FastAPI backend + web frontend. The two OBEX implementations
(Android `com/oscill/obex/`, Python `OscillClient`) are parallel, not shared —
protocol changes must land in both (onboard issue #7).

## Python backend — layered core

```
Layer 3  main.py (FastAPI REST + static serving)        [C_WEB / SP_WEB]
            │  MUST go through DeviceService only
Layer 2  auto_adjust.py (auto V/T/div, offset, trigger) [C_AAJ / SP_AAJ]
Layer 1  device_service.py (singleton, thread-safe)     [C_DSV / SP_DSV]
         calculations.py (measurements, hex, freq)      [C_CAL / SP_CAL]
Layer 0  oscill_client.py (OBEX driver)                 [C_OCL / SP_OCL]
         converters.py (unit model {v,u})               [C_CVT / SP_CVT]
```

Dependency direction is clean (no cycles). **Boundary restored (PL_AUDIT_WEB, 2026-07-15):**
`main.py` no longer imports `OscillClient` or reaches into DeviceService private state — it uses the
public `is_connected()` / `is_acquiring()` / `display_geometry()` accessors instead. The `must` rule
`HardwareAccessOnlyThroughDeviceService` is now honored. The shared-constant single-source concern is
resolved via the new `GET /api/config/options` endpoint (backed by `DeviceService.display_geometry()`
and the `auto_adjust` step lists), which the frontend fetches instead of hardcoding its own copies.

## Core abstractions

| Abstraction | Home | Detail |
|-------------|------|--------|
| Serialized hardware access | `DeviceService` — single-worker `ThreadPoolExecutor` + `RLock` + 5s timeout | skill `python_fastapi_patterns/device_service_executor_pattern` |
| Structured config value `{v, u}` vs bare register int | `converters` + DeviceService snapshot | skill `python_fastapi_patterns/config_dict_format`; rule `StructuredConfigValues` |
| OBEX register protocol + init sequence | `OscillClient` | skills `obex_protocol/*` (register map, init sequence, sample formats) |
| Signal processing (segment freq, peak expansion, hex) | `calculations` + `oscill_client` | skills `signal_processing/*` |
| Frame buffer + `cfg_id` staleness token | `DeviceService` bounded deque (maxlen 256) | skill `config_dict_format` |

## Web frontend

`api.js` is the sole HTTP boundary; `app.js` is the composition root wiring modules
via callbacks; per-control modules (`controls/*`) depend only on `uiHelpers`+`format`.
No cross-module cycles. **Shared-constant duplication with the backend** was the frontend's main
structural debt (rule `SingleSourceForSharedConstants`); the V/T-div step lists and grid geometry
(`h_divs`) are now fetched from `GET /api/config/options` rather than hardcoded. The hex codec and
SI unit model remain duplicated (residual debt).

## Conventions & extension points

- Layer/dependency rules, singleton, cross-area HTTP boundary → `.dev_flow/rules/architecture.md`
- Naming / structure / style / error-handling → `.dev_flow/rules/*.md`
- Tests are standalone scripts in `scripts/` (no pytest) → `.dev_flow/rules/testing.md`
- Ossified extension point: `main.py` `/api/config` per-field if-chain and the
  auto-adjust type list are hand-maintained in the web layer, duplicating the
  DeviceService/auto_adjust contract — flagged for consolidation.

_Android app is documented at the concept level only (`C_AOS`); it has no spec/plan
and was **excluded** from the 2026-07-15 code audit — see the run report._
