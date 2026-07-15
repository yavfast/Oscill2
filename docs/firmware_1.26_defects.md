# Firmware 1.26 — Defect Register (for repair research)

Status: draft (analysis)
Date: 2026-07-14
Device under test: Uosc, HW 1.25, S/N 6070, firmware **1.26** (own device).
Sources: oscill.com forum (`forum.html?task=viewforum&id=2`), official firmware pages
(`/rus/oscilloscopes/usb/usbfirmware/*`), Windows software strings (`oscilnew.zip`).

Context: manufacturer discontinued support; 1.26 is the last released firmware
(1.27 was announced but never released). All experiments on the owner's own device.

## D-01 — Slow-roll sweep drift  *(primary fix candidate)*
- **Symptom:** "осциллограмма уходит от предыдущей развертки при медленной roll дискретизации"
  — the trace drifts away from the previous sweep during **slow roll-mode sampling**.
- **Scope:** appears only at very slow sweep speeds (roll mode). **Regression introduced in 1.26** —
  absent in 1.24 / 1.25.
- **Developer position:** acknowledged, deemed "not significant for most users"; advised affected
  users to stay on / downgrade to 1.24 or 1.25.
- **Likely firmware locus:** timebase / roll-mode sweep buffering & frame-stitching logic
  (sample-to-screen mapping at long acquisition periods). A pointer/offset not reset or
  accumulated between consecutive roll frames.
- **Fixability:** firmware-only, self-contained in the sweep/roll routine — good candidate for a
  targeted patch if the working code can be read/disassembled (see `firmware_update_method.spike.md`).

## D-02 — Bluetooth high-speed instability
- **Symptom:** at 921.6 kbps Bluetooth link, "unstable operation" with some adapter combinations.
- **State:** devices shipped at 460 kbps for stability; 1.26 *added* the higher-speed BT capability
  (up to 2 Mbps) vs the old 9600-baud limit — so this is a new-feature rough edge, not a regression.
- **Fixability:** UART/BT baud & flow-control timing in firmware; lower priority, hardware-dependent
  (HC-06 module + host adapter), harder to validate.

## D-03 — Firmware-update failure with new USB driver + old shell  *(PC-side, not firmware)*
- **Symptom:** "Firmware update failed. Reconnect oscill and repeat"; device drops to `BOOT` state
  ("Device state: BOOT / Need to upload firmware. Process?").
- **Root cause (per developer):** combination of **new USB driver (v3) + old winoscill** → short
  transmission buffer during transfer. Fixed by updating winoscill (old ~v1.4 refused to flash the
  latest firmware). A user also broke their unit with the `setpid` utility (changed device PID
  without installing a driver for the new PID).
- **Fixability:** already fixed on the PC side; relevant here only as an operational caution when
  we drive updates ourselves (respect buffer/packet sizing — see `MaxOBEXpacketSize`).

## Known-good baseline
- **1.25** is the last release *without* D-01. It has: 25-clock sampling, Free-Run sweep,
  extended sync wait. Bluetooth limited to 9600 baud (slow frames) — the tradeoff 1.26 addressed.
- Both `fw_u125.zip` and `fw_u126.zip` are archived on the vendor site; `firmware/Uosc126.ofw`
  in this repo == the installed 1.26.

## Fix strategy (summary)
Target **D-01** first: it is a firmware-local regression with a clear known-good reference (1.25).
Two research tracks, detailed in `firmware_update_method.spike.md`:
1. **Diff 1.25 ↔ 1.26** once both images are readable — the sweep/roll delta localizes the bug.
2. Patch the 1.26 working code and re-flash via the bootloader (`.ofw` path) or via the C2
   programmer as a fallback.
