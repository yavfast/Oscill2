# Specification: OBEX Device Driver (SP_OCL)

> **ID:** SP_OCL
> **Status:** active
> **Implements:** C_OCL
> **Depends on specs:** —
> **Used by specs:** SP_DSV
> **Changelog:**
> - Initialized from existing codebase via onboard procedure (2026-04-22)
> - 2026-07-15 code-audit reconciliation (PL_AUDIT_WEB): removed nonexistent `signed` parameter from get_reg_1/set_reg_1 (only reg_2/reg_4 accept it)
> - 2026-07-15 — task_qs-raise: sampling density is now the per-instance `samples_per_div`, derived from the device QSh per mode (`refresh_samples_per_div`), replacing the fixed 32. QS rises to ~1784 (8-bit) / 888 (hi-res). `SAMPLES_PER_DIV` kept as fallback; added `MAX_SAMPLES_PER_DIV`. Timing/QS formulas now use the instance density.
> - 2026-07-15 — task_qs-raise: added serial speed control (SET-SPEED opcode 0x91, ack 0x0F) — init at 115200 then `raise_speed()` to 921600 (default on; `OSCILL_HIGH_BAUD=0` opts out); `restore_default_speed`/`open_and_handshake`/`close(restore)` keep the device recoverable. Added a cached per-frame acquisition wait (`_frame_wait_s`) to drop per-frame QS/TS reads. Net measured on hardware: frame 291 ms → 132 ms, ~3.4 → ~7 fps at QS=1784, stable.
> - 2026-07-17 — **SP_BTT**: the driver is now constructed **over a `Transport`** (byte-stream abstraction) instead of holding a `serial.Serial` directly. `self.ser` → `self._transport`; canonical ctor `OscillClient(transport, timeout=3.0)`, back-compat `OscillClient.over_serial(port, baud, timeout)`. The serial speed-raise is capability-gated (`transport.capabilities.supports_speed_change`) — inert on Bluetooth RFCOMM. OBEX framing byte-identical. See [SP_BTT](./bluetooth_transport.sp.md) for the Transport contract + Serial/RFCOMM implementations.

## Data Structures

### OscillClient
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `_transport` | Transport | — | Byte-stream link (SerialTransport / RfcommTransport). Replaces the former `ser` handle — see [SP_BTT](./bluetooth_transport.sp.md). |
| `baud` | int | 115200 | Host-side baud bookkeeping for the serial speed-raise; inert on RFCOMM |
| `timeout` | float | 3.0 | Read timeout (s) |
| `conn_id` | Optional[bytes] | None | 4-byte OBEX connection ID |
| `SAMPLES_PER_DIV` | int (class) | 32 | **Default/fallback** sampling density. The active density is the instance `samples_per_div` (below). |
| `MAX_SAMPLES_PER_DIV` | int (class) | 256 | Safety ceiling on the derived density. |
| `samples_per_div` | int (instance) | =SAMPLES_PER_DIV | **Active** samples-per-division. `refresh_samples_per_div()` derives it from the device QSh (mode-dependent) at connect and on mode change: `clamp(QSh // H_DIVS, SAMPLES_PER_DIV, MAX_SAMPLES_PER_DIV)`. Drives `ensure_qs` (QS = samples_per_div × H_DIVS), `set_time_div_ms`/`get_time_div_ms` (time-per-sample = t_div / samples_per_div), and the transmitted display geometry. Measured QSh: 1788 (NORMAL/AVG/PEAK → 223), 894 (AVG_HIRES/PEAK_HI → 111), flat over all timebases. |
| `H_DIVS` | int (class) | 8 | Horizontal divisions |

### SampleFormat
| Code | Name | value_bits | components | Notes |
|------|------|-----------|------------|-------|
| 0x00 | AVG | 8 | 1 | Averaged 8-bit |
| 0x01 | AVG_HIRES | 16 | 1 | Averaged 16-bit |
| 0x02 | PEAK_INTERLACED | 8 | 1 | Interleaved min/max |
| 0x03 | PEAK_DOUBLE | 8 | 2 | Paired min/max |
| 0x04 | NORMAL | 8 | 1 | Standard 8-bit |

### Frame Dict (output of parse_frame / get_frame)
| Key | Type | Notes |
|-----|------|-------|
| channels | int | Channel count (always 1 in current use) |
| samples | List[int] | Sample values (0..255 for 8-bit, 0..65535 for 16-bit) |
| sample_format | int | Format code 0..4 |
| sample_format_label | str | e.g., "NORMAL", "PEAK_INTERLACED" |
| sample_bytes | int | 1 or 2 |
| sample_bits | int | 8 or 16 |
| sample_components | int | 1 or 2 |
| frame_attrs | int | 2-byte frame attributes bitfield |
| channel_attrs | int | 2-byte channel attributes bitfield |
| samples_peak_min | Optional[List[int]] | Peak mode only |
| samples_peak_max | Optional[List[int]] | Peak mode only |

## Contracts

### Connection lifecycle
```
OscillClient(transport, timeout=3.0)          # canonical; transport = SerialTransport | RfcommTransport
OscillClient.over_serial(port, baud=115200, timeout=3.0)   # back-compat serial helper (SP_BTT)
  .open()          → transport.open(); AssertionError if called again without close()
  .reset()         → sends ABORT, drains transport buffer; 300ms sleep
  .connect()       → OBEX CONNECT; sets conn_id; IOError on non-0xA0 response
  .calibrate()     → PUT DATA "C"; returns True on 0xA0/0x90
  .close()         → transport.close(), clears conn_id
  .describe_transport() → human-readable link label (SP_BTT_02_06)
```

### Register access
```
get_reg_1(name: str) → int
get_reg_2/4(name: str, signed: bool = False) → int
set_reg_1(name: str, val: int) → int                            # returns confirmed value
set_reg_2/4(name: str, val: int, signed: bool = False) → int    # returns confirmed value
```
(Note: reg_1 accessors have NO `signed` parameter; only the 2-byte and 4-byte variants do.)
All values clamped to type range before write: 1B [0,255], 2B [0,0xFFFF], 4B [0,0xFFFFFFFF].

### High-level config API
```
get/set_v_div_mV(mv: int) → int             # V1 register
get/set_offset_raw(0..255) → int            # P1 mapped ±128
get/set_trigger_level(0..255) → int         # S1 register
get/set_trigger_mode(bits: int) → int       # T1 bitfield
get/set_channel_hw_mode(bits: int) → int    # O1 bitfield
get/set_channel_sw_mode(bits: int) → int    # M1 bits 0-2
get/set_time_div_ms(ms: float) → float      # sets TS via formula
get_time_div_ms() → float                   # derived from TS+MC
set_cpu_freq_mhz(mhz: float) → int          # sets MC; invalidates _cpu_tick_10ps cache
set_sync_type(bits: int) → int              # RT register
set_samples_offset(0..0xFFFF) → int         # TC register
ensure_qs(total=None) → int                 # QS = total or samples_per_div*H_DIVS (instance)
refresh_samples_per_div() → int             # derive samples_per_div = clamp(QSh//H_DIVS, SAMPLES_PER_DIV, MAX_SAMPLES_PER_DIV)
                                            # caller holds the lock, has applied any mode change,
                                            # and re-applies set_time_div_ms + ensure_qs afterwards
```

### Serial speed control (task_qs-raise)
```
DEFAULT_BAUD = 115200, HIGH_BAUD = 921600 (host); device 921000 = 1842000/coeff(0x02)
SPEED_115200 = 0x10, SPEED_921000 = 0x02, OSCILL_SPEED opcode = 0x91

set_speed(coeff) → bool                     # OBEX opcode 0x91 + 1-byte coeff; ack opcode = 0x0F.
                                            # Device switches its UART on RECEIPT (ack at OLD baud),
                                            # so caller MUST switch the host regardless of the bool.
raise_speed(coeff=0x02, baud=921600) → int  # after low-speed init: SET-SPEED, switch host, verify
                                            # (read QS); revert to 115200 on failure. Returns baud.
restore_default_speed()                     # SET-SPEED(0x10)+host→115200; best-effort (safe if dead)
open_and_handshake()                        # open@115200 + reset + connect; rescues a device left
                                            # high by a prior crash (reopen@921600 → SET-SPEED(0x10))
close(restore=True)                         # restores 115200 before closing (device keeps UART speed
                                            # across an OBEX disconnect; reset() is ABORT, not a UART reset)
```
Sequence: **init/handshake/calibrate at 115200, then `raise_speed()` to 921600** (per device docs —
the session starts at low speed). Enabled by default; `OSCILL_HIGH_BAUD=0` opts out. Measured: frame
transfer 1782 B ≈ 155 ms @115200 → ≈ 19 ms @921600.

### Per-frame acquisition wait cache (task_qs-raise)
`get_data_single` uses a cached `_frame_wait_s` (= QS × sample_period × 1.05, capped 3 s) instead of
reading QS/TS every frame. Invalidated on any QS/TS/MC change (`ensure_qs`, `set_ts_native`,
`set_cpu_freq_mhz`) and recomputed lazily on the next frame. Eliminates ~2 serial round-trips/frame.

### Frame acquisition
```
get_data_single(before_delay_ms=0) → Optional[bytes]
  # Sends GET DATA "D", estimates wait, handles Continue responses
  # Returns raw binary or None on timeout/empty response
  
parse_frame(body: bytes) → Dict  # static; see Frame Dict above

get_frame() → Optional[Dict]    # = parse_frame(get_data_single())
```

## Timing Formula
```
sample_period (ps) = TS × (MC × 10)  / 256
time_per_div (ms) = sample_period × samples_per_div / 1e9   # instance density (mode-aware)
MC target = round(1e5 / freq_mhz)       # 70 MHz → MC = 1429
TS target = round(sample_ps × 256 / (MC × 10))
```

## Validation Rules

- All I/O operations require `self._transport.is_open` (assert)
- Register values clamped to valid ranges before write
- OBEX response codes checked: IOError on unexpected opcodes
- `connect()` must be called before any register access
