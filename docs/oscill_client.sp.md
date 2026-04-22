# Specification: OBEX Device Driver (SP_OCL)

> **ID:** SP_OCL
> **Status:** active
> **Implements:** C_OCL
> **Depends on specs:** —
> **Used by specs:** SP_DSV
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Data Structures

### OscillClient
| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `port` | str | — | Serial device path |
| `baud` | int | 115200 | Baud rate |
| `timeout` | float | 3.0 | Serial read timeout (s) |
| `ser` | Optional[serial.Serial] | None | Open only between open()/close() |
| `conn_id` | Optional[bytes] | None | 4-byte OBEX connection ID |
| `SAMPLES_PER_DIV` | int (class) | 32 | Samples per horizontal division |
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
OscillClient(port, baud, timeout=3.0)
  .open()          → opens serial.Serial; AssertionError if called again without close()
  .reset()         → sends ABORT, drains serial buffer; 300ms sleep
  .connect()       → OBEX CONNECT; sets conn_id; IOError on non-0xA0 response
  .calibrate()     → PUT DATA "C"; returns True on 0xA0/0x90
  .close()         → closes serial, clears conn_id
```

### Register access
```
get_reg_1/2/4(name: str, signed: bool = False) → int
set_reg_1/2/4(name: str, val: int, signed: bool = False) → int  # returns confirmed value
```
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
ensure_qs(total=None) → int                 # QS = total or SAMPLES_PER_DIV*H_DIVS
```

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
time_per_div (ms) = sample_period × SAMPLES_PER_DIV / 1e9
MC target = round(1e5 / freq_mhz)       # 70 MHz → MC = 1429
TS target = round(sample_ps × 256 / (MC × 10))
```

## Validation Rules

- All serial operations require `self.ser is not None` (assert)
- Register values clamped to valid ranges before write
- OBEX response codes checked: IOError on unexpected opcodes
- `connect()` must be called before any register access
