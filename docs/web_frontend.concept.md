# Concept: Web Oscilloscope Frontend (C_WFE)

> **ID:** C_WFE
> **Status:** active
> **Area:** Web frontend (web_oscill/static/)
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Philosophy

A single-page web application that presents the oscilloscope as a familiar instrument: waveform display with grid, interactive drag handles, control panel, and measurements. The frontend is intentionally thin — all signal processing and config state live in the Python backend. The frontend's job is: poll for frames, render waveform, forward user interactions as config changes.

## Domain Model

| Entity | Description |
|--------|-------------|
| Frame | Waveform snapshot with samples, cfg_id, and pre-computed measurements from backend |
| Config | Device parameter set cached locally for UI state; authoritative version from backend |
| Polling loop | setInterval at ~100ms; GET /api/frames?since=lastSeq |
| Scope view | Konva.js canvas with grid, waveform, peak fill, interactive drag handles |
| Control panel | Right-pane Konva canvas with V/div, T/div, trigger, coupling, SW mode controls |
| Measurement panel | DOM-based table showing freq, Vpp, Vmin, Vmax, Vavg |

## Mechanisms

**Incremental polling:** The app tracks `lastSeq` and polls `?since=lastSeq` to fetch only new frames. On each frame batch, the newest frame's measurements and waveform are rendered.

**Drag handles:** ScopeView provides three interactive drag handles on the oscilloscope canvas: trigger level (horizontal red dashed), V offset (cyan horizontal), T offset (magenta vertical). Drag fires config change callbacks on mouseup.

**Auto-connect:** On page load, the app calls `/api/connect` (auto-detect) and starts acquisition automatically. Last-used config is restored from localStorage.

**Config ID tracking:** Every frame includes `cfg_id`. When cfg_id changes, the control panel's UI state is updated from the new config to stay in sync.

## Integration Points

- **Depends on:** Python backend `/api/*` endpoints
- **Rendering:** Konva.js (loaded from CDN)
- **No build tools:** Pure ES modules, no bundler, no TypeScript
