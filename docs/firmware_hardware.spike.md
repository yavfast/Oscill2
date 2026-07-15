# Spike: Firmware & Programmable ICs of the Oscill Hardware

Status: concluded (investigation — no pipeline gates)
Date: 2026-07-14
Sources: `firmware/shema_1.jpeg` (PCB layout), `firmware/shema_2.jpeg` (analog part),
`firmware/Uosc126.ofw` (original firmware), `firmware/oscilnew.zip` (PC software).

## Question
Identify the programmable ICs and their programming connection, the firmware type,
and the toolset needed to program the device.

## 1. Programmable ICs

| Ref | Part | Programmable? | Role |
|-----|------|---------------|------|
| MCU | **Silicon Labs C8051F34x** (8051 core, USBXpress-class) | **YES — main firmware** | Control, ADC readout, comms |
| — | AD9280 (ADC, 8-bit 32 MSPS) | No (fixed-function) | Signal digitizing |
| — | 74HC4051 (8:1 mux) ×2 | No | Attenuator / gain range select |
| — | 74HC4053 (triple 2:1 mux) | No | AC/DC, filter, ÷25 feedback |
| — | 74HC595 (shift register) | No | Serializes range/filter control bits |
| — | ADA4860-1, KR140UD1408A | No (analog) | Amplifiers |
| — | LP2951 / 79L05 | No | Power regulators |

**Only one programmable device holds firmware: the C8051F34x microcontroller.**

### Why C8051F34x
- The board (`shema_1.jpeg`) has a header explicitly labeled **"MCU Debug Interface"** with pins
  **C2Dat**, **−RES**, **+3V3**, **GND** (plus −ERR / FB / 5V-tap). `C2Dat`/`C2Clk` is Silicon Labs'
  proprietary **C2 (2-wire) debug/programming interface** — used exclusively by the **C8051F** family.
- The PC software (`oscilnew.zip`) ships **`SiUSBXp.dll`, `SiUSB32.dll`, `SiUSB64.dll`, `SiInfo.dll`** —
  the **Silicon Labs USBXpress** driver stack. USBXpress is the on-chip USB stack of the
  **C8051F32x / C8051F34x** USB MCUs → the MCU has on-chip USB and enumerates via USBXpress.
- External 8-bit ADC (AD9280) + external mux/shift-register control fit an 8051-class MCU with
  fast parallel GPIO and USB. Firmware payload ≈ 30 KB fits the F34x flash (32–64 KB).

## 2. Programming Connection

Two distinct paths — do not confuse them:

**A. Factory / bare-metal programming (C2 interface)** — the "MCU Debug Interface" header:
```
C2 debug adapter            Board header
  C2CK  ───────────────►  (−RES / C2 clock pin)
  C2D   ───────────────►  C2Dat
  GND   ───────────────►  GND
  +3V3  ───────────────►  +3V3   (target power / sense)
```
This writes raw flash and can recover a bricked/blank MCU.

**B. Field firmware update (the `.ofw` path)** — no debug adapter, over the device's own link:
- The board also exposes a **UART header (RX / TX / +3V3 / GND)** and a **Bluetooth** module
  (`oscilnew.zip` bundles `wcl.dll`, `TestBT.exe`, Widcomm `wcl2wbt.dll`) plus **USB (USBXpress)**.
- `oscill.exe` uploads `Uosc126.ofw` to the resident bootloader over USB / UART / Bluetooth.

## 3. Firmware Type

`Uosc126.ofw` is a **vendor OTA firmware image**, not a raw hex/flash dump:
```
Offset 0x00:  75 EF 00 0D 0A "Oscill.com oscilloscope firmware."
              "Target: Uosc"  "Version: 1.26"  "Date: 15032010"  "FW:" <payload>
```
- Plain-text header, then binary payload after the `FW:` tag (offset ~0x55).
- **Payload entropy = 7.98 bits/byte** → **encrypted (or compressed+encrypted)**. It is NOT an
  Intel-HEX / OMF-51 / raw binary that a flash tool could program directly.
- Consumed only by the vendor's `oscill.exe` + bootloader, which decrypt and flash it internally.

## 4. Toolset

**To reflash / develop the MCU firmware (via C2):**
- **Programmer/debugger:** Silicon Labs **USB Debug Adapter** (EC2/EC3 or U-EC6) or a **ToolStick**.
  A cheap alternative: a "C2 flasher" (e.g. the open EC2-drivers / `c2tool`), but the official
  adapter is safest.
- **Software:** **Simplicity Studio** (current) or the legacy **Silicon Labs IDE** +
  **Flash Programming Utility**; Keil C51 / SDCC as the 8051 compiler for custom firmware.
- Device connection: the 4-pin **MCU Debug Interface** header (C2CK, C2D=C2Dat, GND, VDD/+3V3).

**To apply the original firmware (no hardware tools):**
- The bundled **`oscill_new/oscill.exe`** with the **USBXpress** driver (or Bluetooth via `wcl.dll`)
  — feed it `Uosc126.ofw`. This is the only supported way to use the encrypted `.ofw` as-is.

## 5. Live Device Query (2026-07-14, USB connected)

Device present on USB: `10c4:840e Silicon Labs Oscill USB interface`, bulk vendor class
(EP1 IN/OUT, 64 B). USB `bcdDevice = 1.25` mirrors the **hardware** version, not firmware.

Bound the CP210x driver per `docs/oscill_linux_install.md`
(`modprobe cp210x` + `echo 10c4 840e > /sys/bus/usb-serial/drivers/cp210x/new_id`) → `/dev/ttyUSB0`.
Queried OBEX device properties live via `web_oscill/oscill_client.py`:

| Property | Meaning | Value |
|----------|---------|-------|
| VNM | Model / device id | **Uosc** (base Oscill model) |
| VSN | Serial number | 6070 |
| VHW | Hardware version | 1.25 |
| **VSW** | **Firmware version** | **1.26** |

**Current firmware = 1.26** — identical to the bundled `firmware/Uosc126.ofw` and to the official
`http://oscill.com/files/fw_u126.zip`.

## 6. Latest Available Firmware (oscill.com forum)

- Firmware forum: `https://oscill.com/rus/forum.html?task=viewforum&id=2`.
- **1.26 is the latest released version.** Thread "Версия 1.27" (id=771): 1.27 was **never released**
  ("её еще нет", blocked by a frequency-synthesizer issue on cooled boards; last dev reply 2015).
- Download links: 1.26 → `http://oscill.com/files/fw_u126.zip` (already in repo, matches the device),
  1.25 → `http://oscill.com/files/fw_u125.zip`. PC software → `/files/oscilnew.zip`.
- 1.26 notes (from forum, no formal changelog): improved Bluetooth (up to 2 Mbps, 460 kbps stable);
  known slow-roll sweep drift — affected users advised to stay on 1.24/1.25.

## 7. Firmware Backup / Dump — feasibility

- The OBEX protocol exposes only **GET** (read properties/data) and **PUT** (write registers) —
  **no flash-read/dump command**. A raw firmware dump over USB is **not possible**.
- A true flash dump requires the **C2 adapter** on the debug header — and the flash is very likely
  **read-protected** (vendor OTA is encrypted), so even C2 read-back may be blocked.
- **However, a backup already exists:** `firmware/Uosc126.ofw` *is* the exact current firmware (v1.26,
  the latest release). It is the official encrypted OTA image — the only distributable form.

## 8. Caveats / Open Points
- Exact C8051F34x sub-part (F340…F347) not pin-confirmed here — read it off the physical chip
  or via `C2 device ID` once a C2 adapter is attached. Confidence in "C8051F + C2 + USBXpress": high.
- The `.ofw` encryption key/algorithm is internal to `oscill.exe`; extracting raw firmware for
  analysis would require reversing `oscill.exe`/`oscilink.dll` or dumping flash over C2
  (may be read-protected).
- `shema_2.jpeg` is the **analog front-end only**; the MCU digital section is on the
  `shema_1.jpeg` board layout.
