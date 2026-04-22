# Concept: Auto Adjustment (C_AAJ)

> **ID:** C_AAJ
> **Status:** active
> **Area:** Python backend
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Philosophy

The oscilloscope needs to "frame" a signal properly: voltage scale large enough to show detail but not clip, time scale showing a few cycles, signal centered vertically, trigger at the midpoint. Auto-adjustment iteratively walks through discrete V/div and T/div steps until the signal fits the screen according to fill-factor and cycle-count targets. The order of adjustments is fixed: voltage scale first, then vertical centering, then trigger, then time scale.

## Domain Model

| Entity | Description |
|--------|-------------|
| Fill factor | Signal amplitude / full vertical range — target: 0.2 to 0.8 |
| Segment count | Number of half-periods visible — target: 4 to 8 |
| V/div step | Discrete voltage scale: [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000] mV/div |
| T/div step | Discrete time scale: [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500] ms/div |
| Adjustment order | v_div → v_offset → trigger → t_div |

## Mechanisms

**V/div auto:** Compute fill_factor = (2 × max(|Vmax|, |Vmin|)) / (V/div × 8). If > 0.8 → step up; if < 0.2 → step down. Recurse until optimal or at boundary.

**T/div auto:** Count half-period segments. If < 4 → step up (show more time); if > 8 → step down. Recurse.

**V offset:** Compute signal center = (Vmax + Vmin) / 2. Map to raw 0..255 offset. Apply once.

**Trigger:** Set trigger level to mean of raw sample values. Simple and effective.

**Orchestrator:** `auto_adjust_multiple()` ensures frame availability first, then applies adjustments in canonical order.

## Integration Points

- **Depends on:** `calculations` (measurements, frequency), `converters` (unit extraction)
- **Used by:** `web_api/main` via `/api/auto`
