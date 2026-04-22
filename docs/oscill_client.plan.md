# Plan: OBEX Device Driver (PL_OCL)

> **ID:** PL_OCL
> **Status:** completed
> **Implements:** SP_OCL
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Technology Decisions

- **Language:** Python 3.10+
- **Serial library:** `pyserial` — cross-platform serial port I/O
- **Port detection:** pyserial `list_ports.comports()` by VID/PID 0x10c4/0x840E (CP210x)
- **Frame parsing:** pure Python byte manipulation (no struct module)
- **Timeout strategy:** adaptive — budget = estimated_acquisition_time + 1.0s, capped at 10s

## Implementation Phases

- [DONE] OBEX protocol framing (_build_packet, _build_byte_seq, _build_4byte)
- [DONE] OBEX response parsing (_read_exact, _read_resp, _parse_headers)
- [DONE] GET/PUT property and registry operations
- [DONE] 1/2/4-byte register read/write with endianness handling
- [DONE] High-level config accessors (V1, P1, TS, MC, O1, M1, S1, T1, QS, TC, etc.)
- [DONE] Frame acquisition (get_data_single with Continue handling)
- [DONE] Frame parsing (parse_frame, all 5 sample formats)
- [DONE] Peak mode interpolation (_process_peak_samples, _process_peak_double_samples)
- [DONE] Auto port detection (auto_find_port)

## Backlog

- `get_data_single` multi-chunk handling has a `max_chunks=4` limit. For very long frames (large QS + slow timebases) this may return partial data. Consider increasing limit or removing it when EoB is reliably expected.
- `ensure_qs` does not verify against `QSh` property — could request more samples than device supports. Add a check.
- No reconnection logic — if the serial connection drops mid-operation, the caller gets an IOError with no automatic retry.
