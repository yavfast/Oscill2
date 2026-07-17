# Spike: Alternative (Clean-Room) Oscill Firmware — Feasibility & Simulation

> **Status:** concluded (investigation — no pipeline gates)
> **Created:** 2026-07-17
> **Updated:** 2026-07-17
> **Author:** claude-opus-4-8
> **Time-box:** 1 session, scope = codebase + one external (Renode repo) probe
> **Scope:** codebase (protocol/hardware/firmware skills + docs) + external (`/hdd/STORE/ext_repos/renode`)
> **Mode:** single
>
> **Target concept:** to be created — `C_AFW` (Alternative Firmware)
> **Serves:** feasibility gate before authoring `C_AFW`
> **Question(s):**
> 1. Is a clean-room, **protocol-compatible** alternative firmware for the Oscill DSO feasible with the assets we have (MCU docs, schematic, working C2 write path)?
> 2. What should such firmware look like (preliminary concept)?
> 3. Can **Renode** (`/hdd/STORE/ext_repos/renode`) simulate this device?

## Context

The stock firmware (v1.26, the last release — v1.27 was never shipped, see `firmware_hardware.spike.md` §6) has defects the vendor will not fix; device support has ended. This spike asks whether we can write our own firmware **from scratch** that the existing PC/web client (`web_oscill/`) talks to unchanged.

The decisive reframe up front: the two things that have blocked all prior firmware work — the **`.ofw` encryption** (514-byte additive keystream living only in the bootloader) and the **C2 flash-readback lock** (hardware-verified, `c2-readback-locked-verified` memory) — block *reading and patching the original image*. They do **not** block *writing a clean-room replacement*: a from-scratch binary needs neither the keystream (we don't produce `.ofw`; we flash raw via C2) nor a flash dump (we don't reverse the original — we reimplement the documented protocol). **C2 *write* is unaffected by the read lock.** So the ofw-mask ceiling (111/514) is orthogonal to this effort.

## Exploration Log

### Entry 1 — 2026-07-17 — Protocol-compatibility surface (can we be a drop-in server?)

**What was researched:** `docs/protocol/protocol.md`, the `obex_protocol` skill (`device_register_map`, `device_initialization_sequence`, `sample_format_codes`), and the working reference client `web_oscill/oscill_client.py`.

**Findings:**
- The protocol is **fully reverse-engineered and exercised daily** by a working client. This is the single biggest de-risking fact: we are not guessing the contract, we have an executable oracle.
- The device is an **OBEX server**. The full wire surface a compatible firmware must implement is small and closed:
  - **Framing:** OBEX packets — Connect `0x80`→`0xA0` (returns a connection id in header `0xCB`; tail `10 00 10 00` = version/flags/max-rx), Disconnect `0x81`, Get `0x03/0x83`, Put `0x02/0x82`, Abort `0xFF`. Continue `0x90`/Success `0xA0`/BadReq `0xC0`/NotImpl `0xD1`/InternalErr `0xD0`. Oscill extensions: baud change `0x91`, repeat-last-response `0x92`.
  - **Headers:** Property name `0x70` (3-char ASCII, read-only), Register name `0x71` (2-char ASCII, R/W), Command `0x72` (1 char), Body `0x49`, value headers `0xB1` (1-byte), `0xF0` (2-byte), `0xF1` (4-byte), optional checksum `0xB0` (sum mod 256 = 0; **the live device does not emit it** — see `task_…skip-broken-frame`).
  - **Registers (R/W, 16 of them):** `MC TS RS V1 P1 S1 T1 O1 M1 QS TC TD TA TW AP AR RT` — sizes/units/ranges fully tabled in `device_register_map`. Each write is followed by a read-back that may differ from the written value (the firmware clamps/derives).
  - **Properties (read-only):** `VNM VSN VHW VSW MCd MCl TOl TOv TMl TMh TPl TCh QSh V1h V1l P1h P1l D1m` — device identity + capability limits.
  - **Commands:** `C` (calibrate), `D` (digitize → returns a `0x49` body), `F` (firmware-fragment load — the OTA path; a clean-room firmware may legitimately **omit or stub** this).
  - **Frame format:** digitization attributes (2 B) + per-channel {attrs 2 B, size 2 B, data}. Sample-format code = low 3 bits of channel attr byte 1: `0=AVG 1=AVG_HIRES(16-bit BE) 2=PEAK_INTERLACED 3=PEAK_DOUBLE 4=NORMAL`. (Note the live `size` field is **not** a reliable byte count — `sample_format_codes` pitfall.)
- The **canonical init sequence** the client drives is documented step-by-step (`device_initialization_sequence`): open → reset(abort) → connect → `MC`(clock) → `RS` → `TD` → `AP/AR` → `O1/M1` → `V1/P1` → `T1/S1` → `QS` → `TS`(timebase, derived from MC) → `TC` → calibrate. A compatible firmware must accept these in any order the client issues and keep the documented **dependencies** (e.g. `TS` depends on `MC`; `QSh` depends on `RS/TS/M1/AP`).

**Open questions:** none material for feasibility — the contract is complete. The *hard* unknowns are hardware-timing, not protocol (Entry 3).

### Entry 2 — 2026-07-17 — Hardware & flashing (can we run our own code on this silicon?)

**What was researched:** `firmware_hardware.spike.md`, `arduino_c2_programmer.md`, the two MCU memories (`mcu-is-c8051f41x-not-f34x`, `c2-readback-locked-verified`), `shema_1/2.jpeg` inventory.

**Findings:**
- **MCU = Silicon Labs C8051F41x** (C2 device id `0x0C`, REVID `0x02`), 8051 core, **32 KB flash** (→ C8051F410/411), **no on-chip USB**. USB is a **separate CP210x** UART↔USB bridge (`10c4:840e`) — so **the firmware's host link is plain UART** (115200 default; the project pushes 921600, register-negotiated via `0x91`). Bluetooth is an external RFCOMM/SPP module on the same UART — transparent to firmware (`oscill_bluetooth_transport` skill).
- **C2 write works.** The project already has a proven C2 stack: RPi 4B fast-C bit-bang (`firmware/rpi_c2/c2_rpi.c`) reliably does Device-ID read, FPCTL halt, and the flash-programming command layer. Only **Block *Read*** is locked. Writing/erasing a blank or our-own image is the normal C2 programming path and is **not** gated by the read lock. Worst case for recovery: the standard Silicon Labs USB Debug Adapter + Simplicity Studio / `Flash Programming Utility`.
- **Peripherals the firmware must drive** (from the schematic inventory):
  - **AD9280** — 8-bit, 32 MSPS parallel-output ADC. Firmware clocks it and reads an 8-bit bus (fast GPIO / EMIF-style parallel read).
  - **74HC595** shift register — serializes range/filter/coupling control bits.
  - **74HC4051 ×2** (8:1) — attenuator/gain range select; **74HC4053** — AC/DC coupling, 3 MHz / 3 kHz filters, ÷25 feedback.
  - Analog: ADA4860-1, KR140UD1408A amplifiers; LP2951/79L05 regulators (no firmware role).
- **Toolchain:** **SDCC** (free) or Keil C51 for the 8051; the Silicon Labs C8051F41x datasheet (peripheral registers, C2, flash timing) + the schematic give the pin map. Payload budget ≈ 30 KB fits 32 KB flash (the stock image is 60×512-byte pages = 30 KB).

**Open questions:** exact GPIO/port pin assignments for the ADC bus, the 595 chain, and the mux control lines must be **read off the schematic** (`shema_1.jpeg`) — deferred to the concept/RE phase; not a feasibility blocker (the header labels and IC pinouts are known).

### Entry 3 — 2026-07-17 — Where the real difficulty lives (analog timing, not protocol)

**Findings — the genuinely hard parts of a DSO firmware, ranked:**
1. **Equivalent-time (RIS / "strobed") sampling** (`RS` bit0). Reconstructs a fast periodic signal by taking one sample per trigger at a swept sub-sample **stroboscopic delay** (protocol §1: "time from sync to the nearest ADC clock"). Requires a programmable fine-delay generator (sub-ns) and careful per-pass delay stepping (`AR` = min passes per delay). **This is the crown-jewel algorithm** and the least documented in behavioural detail.
2. **Trigger engine** — analog compare against `S1` level, edge/hysteresis per `T1`, the four `RT` modes (AUTO with `TA` timeout / WAIT with `TW` / FREE / infinite-wait), pre-trigger capture (`TC` presamples) via a circular capture buffer.
3. **Timebase / sample-clock synthesis** — `sample_period = TS × MC × 10 ps`; realtime vs RIS vs parallel/roll regimes each have their own min-period property (`TOl/TMl-h/TPl`).
4. **On-device processing modes** (`M1`) — averaging (`AP` passes), hi-res (16-bit accumulate), peak-detect (min/max), normal — each with its own frame encoding.
5. **Calibration** (`C` command) — self-zero/scale of offset & trigger level against the ADC range; produces the constants the client relies on.
6. **Capability properties** must report values the client already hard-codes tolerance around (e.g. measured `QSh=1788` 8-bit / `894` 16-bit, `MCd≈80 MHz`, `MCl=125 MHz`). A compatible firmware should reproduce these or the client's derived geometry drifts.

**Consequence:** feasibility is **high for the protocol/plumbing** and **medium-to-hard for the analog acquisition core** — the latter is a hardware-RE + DSP effort, best staged (MVP realtime-only first, RIS later).

### Entry 4 — 2026-07-17 — Can Renode simulate the device? (delegated probe)

**What was researched:** delegated Explore agent over `/hdd/STORE/ext_repos/renode` — README, `tlib/arch/`, compiled core matrix, C# core wrappers, and the `platforms/cpus/silabs/` set; case-insensitive tree grep for `8051`/`mcs51`.

**Findings — definitive:**
- **Renode supports only 32/64-bit cores:** ARMv7/v8 (Cortex-A/R/M), x86/x86-64, RISC-V, SPARC, POWER/PPC, Xtensa. Confirmed three ways: `README.md`, the `tlib/arch/` translator sources (`arm arm64 i386 ppc riscv sparc xtensa` — nothing else), and the compiled `Cores/obj/Release/*` matrix.
- **No 8-bit core of any kind** — no 8051/MCS-51, no AVR, no PIC.
- The `platforms/cpus/silabs/` directory is a **false lead**: it holds only EFM32/EFR32/EZR32 parts, every one declaring `cpu: CPU.CortexM` (ARM). The C8051F41x (8051 line) is a different product family and is absent. Every `8051`/`mcs51` grep hit is in unrelated third-party libs (ELFSharp, bc-csharp crypto).
- **To run C8051 code in Renode you would have to author a new `tlib/arch/mcs51/` translator** (TCG opcode gen for a Harvard 8-bit ISA unlike any existing target), wire the CMake build, and add a C# `TranslationCPU` wrapper — essentially porting a QEMU target that does not exist upstream. Python/C# **peripheral** models exist, but a peripheral cannot execute the core's instructions. GDB co-sim is for debugging Renode's own cores, not importing a foreign ISS as the CPU.

**Verdict on Q3: Renode is NOT usable for this MCU** without a from-scratch 8051 core port (a large, separate project — not proportionate to firmware development).

## Alternatives Considered

### A. Firmware target platform

| # | Approach | Pros | Cons | Verdict |
|---|----------|------|------|---------|
| 1 | **Clean-room firmware on the existing C8051F41x** (SDCC/Keil, flashed via the working C2 write path) | Drop-in; reuses the whole analog board; existing client + C2 tooling; no hardware mod | Hard 8051 real-time analog core (RIS, trigger); no ARM ecosystem; **not Renode-simulable** | **chosen** (this is "protocol-compatible alternative firmware") |
| 2 | Replacement **ARM Cortex-M** daughterboard driving the same analog front-end, same protocol | Renode-simulable; richer toolchain/DSP; more flash/RAM | Requires hardware redesign (ADC bus, mux, timing) — no longer "just firmware"; large BOM/effort | rejected for this spike (out of scope; only path where Renode helps — record as a decision input) |
| 3 | Patch the original `.ofw` | — | Blocked: encryption keystream unknown (111/514 ceiling) + per-page checksum + flash read-locked | rejected (the closed ofw-mask path) |

### B. Simulation / development harness (since Renode is out)

| # | Approach | Pros | Cons | Verdict |
|---|----------|------|------|---------|
| 1 | **Protocol-level device emulator** — a software OBEX server (Python, reusing `oscill_client.py` framing knowledge) that answers Connect/Get/Put, serves properties/registers, and returns synthetic `0x49` frames (sine/ramp/noise) | Cheap (days); reuses project code; lets us develop **the protocol/plumbing half of the firmware** and regression-test the PC/web client with **no hardware**; doubles as a client CI fixture | Models the *contract*, not the 8051 or the analog timing — won't validate RIS/trigger cycle accuracy | **chosen — primary harness** |
| 2 | **SDCC `ucSim` / `s51`** (instruction-accurate 8051 ISS, ships with SDCC) | Runs the actual 8051 build; validates control flow, timing loops, ISR logic; free | No model of AD9280/mux/UART-bridge out of the box — must script stimulus; no analog | **chosen — firmware-logic harness** (pair with #1) |
| 3 | Renode | Great *if* the core were ARM | No 8051 core (Entry 4) | rejected |
| 4 | MCU-8051-IDE simulator | GUI 8051 sim | Older/Windows-leaning; weaker automation than ucSim | fallback only |
| 5 | Full analog-mixed-signal sim (SPICE + ISS co-sim) | Highest fidelity | Enormous effort; unjustified for firmware logic | rejected (YAGNI) |

## Conclusion

**Verdict:**

- **Q1 (feasibility): YES — feasible, and de-risked on the hard-to-guess axis.** The protocol contract is fully known and has a working executable oracle; the MCU is documented and C2-writable (the read lock and `.ofw` encryption are irrelevant to a clean-room build). The concentrated risk is the **analog acquisition core** (RIS equivalent-time sampling, trigger engine, calibration) — a hardware-RE + real-time-firmware effort, best delivered in stages (realtime-only MVP → RIS/peak/roll later). Recommend proceeding to a **staged concept `C_AFW`**.
- **Q2 (concept): drafted below.**
- **Q3 (Renode): NO.** Renode has no 8051 core and only 32/64-bit targets; simulating the C8051F41x would require writing a new 8051 tlib translator from scratch. **Use a two-part harness instead:** a Python **protocol-level device emulator** (for the protocol/plumbing layer and client regression) + **SDCC ucSim/s51** (for 8051 firmware logic). Renode becomes relevant *only* under the rejected ARM-re-platform path (Alt A2).

**Key constraints discovered:**
- Firmware host link is **UART**, not USB (CP210x bridge; MCU has no on-chip USB) — no USB stack to write.
- Must fit **~30 KB / 32 KB flash** on an 8051 (8-bit, Harvard, no HW multiply/divide beyond MDU if present) — RIS delay generation and DSP must be lean.
- Must reproduce capability **properties** the client hard-codes around (`QSh` 1788/894, `MCd≈80 MHz`, `MCl 125 MHz`, `V1l/V1h` where "l/h" track *sensitivity* not V/div — `device_register_map` gotcha) or the client's derived geometry drifts.
- Register **read-back-may-differ** semantics and inter-register **dependencies** must be honoured (`TS`←`MC`; `QSh`←`RS/TS/M1/AP`).
- Checksum `0xB0` is optional and the stock device omits it — a compatible firmware may omit it too (but should accept it inbound).
- Exact GPIO pin map (ADC bus, 595 chain, mux lines) is **not yet extracted** — a concept-phase task against `shema_1.jpeg` + the C8051F41x datasheet.

**Recommendations for the concept (`C_AFW`):**
- **Scope IS:** an OBEX server on the C8051F41x reproducing the documented registers/properties/commands + realtime single-shot acquisition (AUTO/WAIT trigger, NORMAL/AVG/PEAK processing) as the MVP; RIS, roll/parallel, hi-res, and full calibration as later phases.
- **Scope IS NOT:** the `.ofw` OTA path (command `F`) in the MVP — flash via C2; producing `.ofw` images; any hardware redesign; reversing the stock image.
- Layer the design cleanly (see sketch) so the **protocol layer** is testable against the Python emulator independently of the **acquisition layer** tested in ucSim.
- Record **Alt A2 (ARM re-platform)** as an open decision input, not a committed path — it is the only route that unlocks Renode and a richer toolchain, at the cost of hardware work.

**Artifacts to keep:** none staged (analysis-only spike; all sources already in-repo).

**Artifacts to discard:** none (no prototype code written).

---

## Preliminary Concept Sketch — `C_AFW` (Alternative Firmware)

*Not a formal concept (no pipeline gate). This is the spike's proposed starting point for `/dev-flow concept`.*

### Idea
A clean-room 8051 firmware for the Oscill C8051F41x that is a **drop-in OBEX server** — byte-compatible on the wire with stock v1.26 so `web_oscill/` and any stock client work unchanged — while being ours to fix and extend.

### Architecture (layers, bottom-up)
```
┌─────────────────────────────────────────────────────────┐
│ L4  OBEX server / command dispatch                        │  ← testable vs Python emulator
│     Connect/Disconnect/Get/Put/Abort · 0x91 baud · 0x92   │
│     register & property tables · C/D/F command handlers   │
├─────────────────────────────────────────────────────────┤
│ L3  Device model — register/property store + dependency   │
│     rules (TS←MC, QSh←RS/TS/M1/AP), read-back clamping     │
├─────────────────────────────────────────────────────────┤
│ L2  Acquisition engine                                    │  ← testable vs ucSim + stimulus
│     timebase/clock (MC,TS) · trigger (S1,T1,RT,TA,TW,TC)  │
│     modes: realtime → RIS(strobe delay,AR) → parallel/roll│
│     processing: NORMAL/AVG(AP)/HIRES/PEAK (M1)            │
├─────────────────────────────────────────────────────────┤
│ L1  HAL / board drivers                                   │
│     UART (to CP210x/BT) · AD9280 parallel read · 74HC595  │
│     range/filter · 74HC4051/4053 mux · fine-delay gen     │
├─────────────────────────────────────────────────────────┤
│ L0  C8051F41x SoC init (clock/MC, ports, timers, ISRs)    │
└─────────────────────────────────────────────────────────┘
```

### Delivery phases (staged, each independently verifiable)
- **P0 — Bring-up:** SoC init, UART echo, LED/heartbeat; flash via C2; prove the toolchain + programmer round-trip.
- **P1 — Protocol skeleton (no acquisition):** OBEX Connect/Get/Put/Abort, full register/property tables with correct sizes/units/read-back, `C`/`D` accepted with a **synthetic** frame. **Verify:** the real `web_oscill` client connects, reads identity, sets every register, and renders a synthetic waveform — end-to-end, over real UART. (Mirror-tested first against the Python emulator.)
- **P2 — Realtime acquisition:** AD9280 capture, timebase from `MC/TS`, AUTO/WAIT trigger with pre-trigger `TC`, NORMAL/AVG/PEAK. Real signal on screen.
- **P3 — RIS (equivalent-time):** stroboscopic fine-delay sweep, `AR` passes — the high-frequency mode. Hardest phase.
- **P4 — Calibration + capability parity:** `C` self-cal, report `QSh/MCd/MCl/...` matching the client's expectations; roll/parallel + hi-res.

### Explicit non-goals (MVP)
`.ofw` OTA/`F` command · producing encrypted images · hardware redesign · reversing stock flash · Bluetooth-specific firmware logic (transparent UART module).

### Simulation/verification strategy (from Q3)
- **Python OBEX device emulator** — develop & regression-test L3/L4 and the PC/web client with zero hardware; also a permanent client-CI fixture.
- **SDCC ucSim/s51** — unit-test L2 acquisition/trigger logic with scripted ADC stimulus.
- **Live hardware** — the only true oracle for L0/L1 timing and the analog core; C2-flash + drive with the real client.
- **Renode — not applicable** (no 8051 core).

### Open decisions to carry into the concept interview
1. **Target platform** — C8051F41x clean-room (default) vs ARM re-platform (unlocks Renode + toolchain, needs HW work). `C_AFW_DEC_01`.
2. **MVP acquisition scope** — realtime-only first vs realtime+RIS together (RIS is the hard part; staging recommended). `C_AFW_DEC_02`.
3. **Toolchain** — SDCC (free, open) vs Keil C51 (proven 8051 codegen). `C_AFW_DEC_03`.
4. **`.ofw`/`F` support** — omit entirely (C2-only) vs implement a clean bootloader later so field updates don't need C2. `C_AFW_DEC_04`.
