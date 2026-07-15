# Oscill2 — Dev-Flow Documentation Index

> **Generated:** 2026-04-22 via onboard procedure
> **Project type:** Polyglot — Android app + Python FastAPI backend + Vanilla JS web frontend
> **Note:** Files with `.concept.md` / `.sp.md` / `.plan.md` extensions are dev-flow generated docs.
>           Files with `.md` extension only are human-written project docs — do not overwrite.

---

## System Overview

Oscill2 is a USB oscilloscope platform with three independent clients sharing the same hardware device via the oscilloscope's OBEX-over-serial protocol:

1. **Android app** — native Android client with USB OTG, direct device connection
2. **Python FastAPI server** — HTTP backend serving the web frontend, with USB serial device access
3. **Web frontend** — browser-based oscilloscope UI, polling the Python server

---

## Python Backend

### Layer 0 — Foundation

| Concept | Spec | Plan | Description |
|---------|------|------|-------------|
| [C_CVT](converters.concept.md) | [SP_CVT](converters.sp.md) | [PL_CVT](converters.plan.md) | Unit conversion (V/mV, ms/s, Hz) |
| [C_OCL](oscill_client.concept.md) | [SP_OCL](oscill_client.sp.md) | [PL_OCL](oscill_client.plan.md) | OBEX device driver over USB serial |

### Layer 1 — Signal processing + device service

| Concept | Spec | Plan | Description |
|---------|------|------|-------------|
| [C_CAL](calculations.concept.md) | [SP_CAL](calculations.sp.md) | [PL_CAL](calculations.plan.md) | Signal measurements (freq, Vpp, hex encoding) |
| [C_DSV](device_service.concept.md) | [SP_DSV](device_service.sp.md) | [PL_DSV](device_service.plan.md) | Thread-safe device service + frame buffer |

### Layer 2 — Auto adjustment

| Concept | Spec | Plan | Description |
|---------|------|------|-------------|
| [C_AAJ](auto_adjust.concept.md) | [SP_AAJ](auto_adjust.sp.md) | [PL_AAJ](auto_adjust.plan.md) | Auto V/div, T/div, offset, trigger |
| [C_RES](resolution_enhancement.concept.md) | [SP_RES](resolution_enhancement.sp.md) | [PL_RES](resolution_enhancement.plan.md) | Periodic-signal resolution enhancement — coherent multi-frame averaging (align+gate+avg) + SMA; status `draft` |

### Layer 3 — HTTP API

| Concept | Spec | Plan | Description |
|---------|------|------|-------------|
| [C_WEB](web_api.concept.md) | [SP_WEB](web_api.sp.md) | [PL_WEB](web_api.plan.md) | FastAPI REST server + static file serving |

---

## Web Frontend

| Concept | Description |
|---------|-------------|
| [C_WFE](web_frontend.concept.md) | Web oscilloscope SPA — Konva canvas display, control panel, measurement panel |

_(Detailed frontend specs and plans deferred — frontend is a single cohesive SPA; refer to concept for architecture)_

---

## Android App

| Concept | Description |
|---------|-------------|
| [C_AOS](android_oscilloscope.concept.md) | Android oscilloscope app — USB OTG, OBEX, event bus, waveform display |

_(Detailed Android specs and plans deferred — refer to existing docs/ for Android-specific documentation)_

---

## Investigations (spikes — no pipeline gates)

| Document | Status | Description |
|----------|--------|-------------|
| [sample_array_length.spike.md](sample_array_length.spike.md) | concluded | What bounds max sample count (QSh = RS/TS/M1/AP, not CPU freq); CPU freq = time resolution, not count |
| [firmware_hardware.spike.md](firmware_hardware.spike.md) | concluded | Programmable ICs, PCB layout, firmware type, programming toolset |
| [firmware_update_method.spike.md](firmware_update_method.spike.md) | concluded | How the Windows software updates firmware; `.ofw` format + encryption; modification feasibility |
| [ofw_mask_cryptanalysis.spike.md](ofw_mask_cryptanalysis.spike.md) | concluded | Math foundation for unpacking `.ofw`: many-time-pad model, stride-8 0xFF crib → 64/514 mask recovered ciphertext-only; full mask needs 1 known page (C2); test-fw = validator, not oracle |
| [firmware_1.26_defects.md](firmware_1.26_defects.md) | draft (analysis) | Defect register for firmware 1.26 (slow-roll sweep drift, etc.) |

_Durable `.ofw` findings are captured in skill [firmware_ofw_format](../.dev_flow/skills/firmware_ofw_format/SKILL.md); tooling in `firmware/ofw_crypto.py`._

---

## Rules & Standards

- [Naming Rules](.dev_flow/rules/naming.md)
- [Architecture Rules](.dev_flow/rules/architecture.md)
- [Error Handling Rules](.dev_flow/rules/error-handling.md)
- [Code Structure Rules](.dev_flow/rules/structure.md)
- [Style Rules](.dev_flow/rules/style.md)
- [Testing Rules](.dev_flow/rules/testing.md)

---

## Issues Requiring Attention

See [.dev_flow/onboard/issues.md](../.dev_flow/onboard/issues.md) — 8 issues, including:
- **High:** Bug in auto_adjust_t_div (wrong t_step_ms)
- **Medium:** Blocking polls in async ASGI endpoint
- **Low:** Duplicated V/div and T/div step lists in Python + JS
