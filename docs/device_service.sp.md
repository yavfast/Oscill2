# Specification: Device Service (SP_DSV)

> **ID:** SP_DSV
> **Status:** active
> **Implements:** C_DSV
> **Depends on specs:** SP_OCL, SP_CVT
> **Used by specs:** SP_WEB, SP_AAJ
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

## Data Structures

### DeviceService constructor
```
DeviceService(buffer_size: int = 256)
```
- `buffer_size`: max frames in ring buffer (deque maxlen)

### Status dict (from get_status / connect)
```json
{
  "status": "ok" | "disconnected",
  "is_connected": bool,
  "is_acquiring": bool,
  "config": ConfigDict,       # present when status="ok"
  "cfg_id": int,              # present when status="ok"
  "port": str,                # present in connect() response only
  "error": str                # present in ensure_connected() on failure
}
```

### ConfigDict (from get_status / apply_config)
| Key | Type | Notes |
|-----|------|-------|
| v_div | {v,u} | mV/div |
| t_div | {v,u} | ms/div |
| v_offset | int | raw 0..255 |
| trigger_level | int | raw 0..255 |
| trigger_mode_bits | int | T1 register value |
| trigger_slope | str | "Rising"/"Falling"/"Both"/"None" |
| sync_front | bool | Rising edge trigger enabled |
| sync_back | bool | Falling edge trigger enabled |
| coupling | str | "DC"/"AC"/"GND" |
| sw_mode | str | "NORMAL"/"AVG"/"AVG_HIRES"/"PEAK"/"PEAK_HI" |
| sync_type | str | "AUTO"/"WAIT_TIMEOUT"/"FREE"/"WAIT" |
| filters | {high: bool, low: bool} | HW filter state |
| samples_total | int | QS register value |
| t_offset | int | TC register (pre-trigger samples) |
| cfg_id | int | Config version counter |

### Frame dict (from get_frames / get_latest_frame)
| Key | Type | Notes |
|-----|------|-------|
| seq | int | Monotonically increasing |
| time | float | Unix timestamp |
| cfg_id | int | Config version when frame was acquired |
| samples | List[int] | Raw ADC values |
| sample_bits | int | 8 or 16 |
| sample_bytes | int | 1 or 2 |
| sample_format | int | 0..4 |
| samples_peak_min | Optional[List[int]] | Peak mode only |
| samples_peak_max | Optional[List[int]] | Peak mode only |

## Contracts

### connect(port=None, baud=115200) → Dict
- **Errors:** `TimeoutError` (5s timeout), `RuntimeError("Device not found")` if port=None and no device
- **Side effects:** starts acquisition loop; snapshots config

### ensure_connected(port=None, baud=115200) → Dict
- Returns current status if already connected; calls connect() otherwise
- Never raises — returns `{status: "disconnected", error: ...}` on failure

### disconnect() → Dict
- Stops acquisition; closes serial; clears frame buffer; clears cached config

### get_status() → Dict
- No device I/O — returns cached config

### apply_config(changes: Dict) → Tuple[Dict, List[str]]
- `changes` keys: v_div, v_offset, t_div, t_offset, trigger_level, trigger_mode, trigger_slope, coupling, filter_high, filter_low, sw_mode, sync_type, sync_front, sync_back
- Returns (status_dict, warnings_list)
- Frame buffer cleared after any config change
- **Errors:** `TimeoutError` (5s); `RuntimeError` if not connected

### get_frames(since=None, limit=64) → Dict
- Returns: `{frames: List[Dict], oldest_seq, newest_seq, buffer_size}`
- Thread-safe read only — never touches device

### get_latest_frame() → Optional[Dict]
- Returns copy of most recent frame or None

### ensure_frame_available(timeout=2.0) → Optional[Dict]
- Starts acquisition temporarily if needed; polls up to timeout; stops if it started

### start() / stop() → Dict
- Both return `{status: "ok"}`

## Validation Rules

- v_offset clamped to [0, 0xFF]
- t_offset clamped to [0, 0xFF]
- trigger_slope: "RISING"/"FALLING"/"BOTH"/"NONE" (case-insensitive via _normalize_key)
- coupling: "DC"/"AC"/"GND" (case-insensitive)
- Invalid sw_mode / sync_type → warning in list, not error
