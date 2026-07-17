# Spike: What bounds the maximum sample-array length (QSh), and would changing the CPU base frequency change it?

> **Status:** concluded
> **Created:** 2026-07-15
> **Updated:** 2026-07-15
> **Author:** claude-opus
> **Time-box:** 1 session (codebase + protocol docs)
> **Scope:** codebase (protocol.md, oscill.pdf source, oscill_client.py, obex_protocol skill)
> **Mode:** single
>
> **Target concept:** — (informs `task_20260715_090617_scope-zero-offset`; no concept change)
> **Serves:** developer question — "can changing the base (CPU) frequency raise the max sample count / fix the 254?"
> **Question(s):**
> 1. What does the maximum sample-array length (QSh) depend on, per the device documentation?
> 2. How does the CPU base frequency (MC) relate to sampling, and does it affect the sample **count**?
> 3. Would changing the base frequency give more samples (or a clean 256 instead of 254)?

## Context

The device returns 254 samples for QS=256 (see the scope-zero-offset task). The developer
asked whether the maximum sample count is bounded by the CPU base frequency, and whether
changing it (the device already runs an overclock: 70 MHz vs the 50 MHz default) could raise
the count or remove the "−2". This spike settles the dependency chain before any such change.

## Exploration Log

### Entry 1 — 2026-07-15 — Protocol source: QSh / QS / TS / MC definitions

**What was researched:** `docs/protocol/protocol.md` (transcription) + the authoritative Russian
source `docs/protocol/oscill.pdf` (via `pdftotext`), cross-checked with the `obex_protocol` skill's
Key Derived Formulas and `web_oscill/oscill_client.py`.

**Findings:**
- **QSh** — "Максимальний розмір вихідного масиву" (max output array). The source states its
  dependencies **explicitly**: *"зависит от способа оцифровки **RS** + периода дискретизации **TS**
  (три набора), обработки выборок **M1**, наличия усредняющих/пиконакопительных проходов **AP**."*
  → QSh depends on **RS, TS (in three regimes), M1, AP**. **CPU cycle MC is NOT listed.**
- Contrast: **TPl** (min parallel period) *does* explicitly list *"тривалості машинного циклу (MC)"*
  as a dependency (oscill.pdf line 113). So the docs distinguish MC-dependent properties from QSh —
  the omission of MC from QSh is deliberate, not an oversight.
- **QS** (register) — "Максимальное значение: свойство QSh"; depends on **RS, TS, M1**. Default in this
  project = `SAMPLES_PER_DIV(32) × H_DIVS(8) = 256` (`oscill_client.ensure_qs`).
- **CPU frequency knob** = **MC** register (machine-cycle duration, 10 ps units).
  `CPU_MHz = 1e5 / MC` (obex skill). `MCd` = safe default (50 MHz), `MCl` = max overclock (100 MHz).
- **Sample-period relation** (obex skill + `oscill_client.get_sample_period_ps`):
  `sample_period_ps = TS × MC × 10`. So MC scales the **time per sample**; `TS` is expressed in
  *machine-cycles×256*, and `set_time_div_ms` derives TS from the requested t_div **and** the current MC.

**Open questions:** the numeric value of QSh for the current settings is device-reported (protocol
example = "N/A") and is not exposed via the current HTTP API — resolved in Entry 2 by a direct read.

---

### Entry 2 — 2026-07-15 — Live device read (QSh + clock properties)

**What was tried:** briefly freed the serial port and read the properties directly via
`DeviceService` (auto-connect + `get_property`), under the device lock, then restored the service.
Device: Uosc on `/dev/ttyUSB0`, current settings (AVG, QS=256, t_div=5ms).

**Findings (measured):**
- **QSh = 1788** — max output samples for the current settings. Current **QS = 256**, so there is
  **~1532 samples of headroom** — the array could be ~7× larger without any frequency change.
- **TCh = 1787** (max presamples ≈ QSh−1).
- **MCd = 1248** (10 ps) → **80.1 MHz default**, **MCl = 800** → **125 MHz** max overclock.
  Current **MC = 1423 → 70.3 MHz** — i.e. the project runs *below* this device's own default clock,
  **not** an overclock. (The protocol's "50 MHz" is a generic base-model example, not this unit.)
- **TS = 2810963** (machine-cycles×256) at 5 ms/div.

**Conclusion of entry:** QSh=1788 confirms the count ceiling is far above 256 and is a memory/regime
property — independent of raising or lowering the CPU clock. The lever for more samples is QS, not MC.

## Alternatives Considered

| # | Lever to change the sample **count** | Effect | Verdict |
|---|--------------------------------------|--------|---------|
| 1 | **Change CPU base frequency (MC)** | Changes absolute **sample period** → reachable timebase range / time resolution. Does **not** change QSh (not a listed dependency); count ceiling is memory/regime-bound. | **rejected** — wrong lever for count |
| 2 | **Raise QS toward QSh** | More samples per frame (finer horizontal resolution) **if QSh > current 256**. Orthogonal to CPU freq. Would also need `SAMPLES_PER_DIV` to stay consistent with the grid. | **candidate** — needs QSh value (read from device) |
| 3 | **Change mode (M1) / AP** | Peak mode halves usable count (254→127); AVG_HIRES doubles bytes/sample. Changes QSh per the doc. | not for "more/clean" count |
| 4 | **Accept 254 and reconcile in code** | Already done in the scope-zero-offset fix (delivered-length geometry). "−2" is a stable output overhead independent of MC and QS. | **in place** |

## Conclusion

**Verdict:** Changing the CPU base frequency will **not** increase the maximum sample count nor turn
254 into 256. **QSh depends on the sampling regime (RS/TS), the processing mode (M1), and averaging
passes (AP) — not on the CPU machine cycle (MC).** The base frequency governs **time resolution**
(sample period, achievable timebase range), which is exactly why the project already overclocks to
70 MHz — for faster sweeps, not for more samples. The maximum sample **count** is a device
memory/regime ceiling; the lever for it is **QS (bounded by QSh)**, orthogonal to CPU frequency.

**Key constraints discovered:**
- QSh dependency set = {RS, TS(×3 regimes), M1, AP}. MC is explicitly excluded (while TPl explicitly includes it — the distinction is intentional).
- `sample_period = TS × MC × 10 ps`; MC = time-per-sample scaler, not a count scaler.
- The "−2" (QS→delivered) is a fixed output overhead for these settings, independent of MC and of the QS value (stable across the TC probe); already handled by delivered-length reconciliation.
- **Measured (this device, AVG @ 5ms/div): QSh = 1788, TCh = 1787.** Current QS = 256 → ~1532 headroom.
- **Measured clock: MCd = 80.1 MHz (device default), MCl = 125 MHz (max), current MC = 70.3 MHz.** So the project runs **below** this device's default clock — the earlier "70 MHz overclock vs 50 MHz" note was based on the generic protocol example, not this unit.

**Recommendations:**
- Do **not** change the base frequency to affect sample count — QSh (1788) does not depend on MC.
- **Sample count is nowhere near the ceiling:** QS=256 vs QSh=1788. If **higher horizontal resolution** is wanted, that is a **separate** effort — raise `QS` (up to ~1788) with `SAMPLES_PER_DIV`/grid kept consistent, plus a wider adaptive acquisition-wait. Unrelated to the zero-offset fix; its own concept/spec change (bigger frames = more payload/CPU, so measure before maximizing).
- The current delivered-length reconciliation is the correct handling of the 254; no frequency change is warranted by the zero-offset task.

**Artifacts to keep:** — (findings persisted to `.dev_flow/skills/obex_protocol/`)

**Artifacts to discard:** — (no prototype code; read-only investigation)
