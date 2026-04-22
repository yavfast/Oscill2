# Concept: OBEX Device Driver (C_OCL)

> **ID:** C_OCL
> **Status:** active
> **Area:** Python backend
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Philosophy

`OscillClient` is the hardware abstraction layer for the Python backend. It speaks the OBEX-over-serial protocol to the oscilloscope, translating high-level commands ("set V/div to 200mV") into binary register writes and parsing raw frame bytes into structured sample arrays. The rest of the Python system never touches serial bytes — they only call OscillClient's typed methods.

## Domain Model

| Entity | Description |
|--------|-------------|
| OBEX Connection | Active serial session with the device, identified by a 4-byte connection ID |
| Register | Named 2-letter device parameter (e.g., "V1" = voltage/div, "TS" = sample period) |
| Property | Read-only device characteristic (e.g., "VNM" = device name) |
| Frame | One acquired waveform: binary blob parsed into sample array + metadata |
| Sample Format | Encoding mode: NORMAL, AVG, AVG_HIRES, PEAK_INTERLACED, PEAK_DOUBLE |

## Mechanisms

**OBEX framing:** Every device interaction is an OBEX GET or PUT request. GET reads a register or property; PUT writes a register. Each packet has a 3-byte header (opcode + length), followed by typed headers (connection ID, register name, value).

**Register access:** `get_reg_N(name)` / `set_reg_N(name, val)` handle 1/2/4-byte values with proper endianness. High-level methods (get_v_div_mV, set_time_div_ms) translate physical units to/from raw register values using the device's timing formulas.

**Frame acquisition:** `get_data_single()` sends a GET DATA "D" command, handles multi-chunk OBEX Continue responses, and estimates wait time from current acquisition parameters. `parse_frame()` decodes the binary format: frame attributes → channel count → per-channel attrs, size, and raw data bytes, dispatching to format-specific sample processors.

**Auto port detection:** `auto_find_port()` scans for CP210x USB-serial adapters by VID/PID (0x10c4/0x840E), with fallback to common /dev/ttyUSB* paths.

## Integration Points

- **Used by:** `device_service` (all device I/O), `web_api/main` (legacy reference only)
- **Depends on:** `pyserial` (serial port I/O)
- **Protocol reference:** `docs/protocol/protocol.md`
