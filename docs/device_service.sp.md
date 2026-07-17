# Specification: Device Service (SP_DSV)

> **ID:** SP_DSV
> **Status:** active
> **Implements:** C_DSV
> **Depends on specs:** SP_OCL, SP_CVT
> **Used by specs:** SP_WEB, SP_AAJ
> **Changelog:**
> - Initialized from existing codebase via onboard procedure (2026-04-22)
> - 2026-07-15 code-audit reconciliation (PL_AUDIT_WEB): documented start() "Not connected" RuntimeError path (stop() remains unconditional ok)
> - 2026-07-15 — PL_AUDIT_WEB code-audit propagation: added public is_connected()/is_acquiring()/display_geometry() contracts; ConfigDict now includes h_divs alongside samples_per_div; acquisition loop reuses cached config per frame (no per-frame register re-read)
> - 2026-07-15 — task_qs-raise: samples_per_div is now the live per-mode density (223/111, from QSh) not a fixed 32; display_geometry() is an instance method reading it; apply_config re-derives density on mode change (re-applying t/div) and resets _last_delivered_len before the response snapshot to avoid stale cross-mode geometry
> - 2026-07-17 — **SP_BTT**: `connect`/`ensure_connected` are now a backward-compatible superset accepting a `ConnectionEndpoint` (serial | bluetooth) in addition to legacy `(port, baud)`; the driver is built via `build_transport` over a `Transport`. Executor budget is transport-aware (serial 5s, Bluetooth 50s — SDP + RFCOMM bring-up); serial speed-raise gated to serial endpoints; `DeviceNotFound`/`BluetoothUnreachable`/`ChannelResolutionError`/`ConfigError` error surface. See [SP_BTT](./bluetooth_transport.sp.md).
> - 2026-07-17 — **SP_BTT increment 2**: added `connect_auto` (USB→BT auto-select); `ensure_connected()` (no args) now uses it; status/connect responses carry `transport_kind` (serial|bluetooth|null). BT address resolves by device name among paired devices (SP_BTT_02_11).

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
  "port": str,                # connect() response only: serial path, or BD_ADDR for bluetooth
  "transport": str,           # connect() response only: link label, e.g. "serial:/dev/ttyUSB0@115200" (SP_BTT)
  "transport_kind": str|null, # "serial"|"bluetooth" when connected, null when disconnected (SP_BTT_02_09)
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
| samples_total | int | **Delivered** sample count = actual plotted array length. Reconciled from the raw QS register: the device returns fewer samples than QS (empirically QS−2 in AVG/NORMAL). See _reconcile_display_geometry. |
| t_offset | int | Trigger index in the **delivered** array = `TC − (QS − delivered) − 1` (delivered-space), so the client's zero/trigger marker sits on the real trigger. Raw TC (pre-trigger samples) is not exposed. |
| samples_per_div | int | Display geometry — the **live per-connection** density (`OscillClient.samples_per_div`), derived from QSh per mode: 223 (8-bit NORMAL/AVG/PEAK), 111 (16-bit AVG_HIRES/PEAK_HI). No longer the fixed 32. |
| h_divs | int | Horizontal division count (device H_DIVS, =8 — NOT 10) |
| limits | {param: {min, max}} | Valid range per parameter, for client informativeness + clamping. See below. |
| cfg_id | int | Config version counter |

### ConfigDict.limits (parameter ranges)
Built at snapshot; device-authoritative where a property exists, else structural/derived.
Two shapes, discriminated by key:
- **Stepped params** (fixed set of allowed values) → `{"values": [...], "u": unit}`.
- **Continuous params** → `{"min": N, "max": N}`.

Delivered-space entries (samples_total, t_offset) are reconciled like their current values.

| limits key | shape | Source |
|-----|-----|--------|
| v_div | `{values: [mV,…], u:"mV"}` | OscillClient.VDIV_VALUES_MV, filtered to the device sensitivity range (V1l/V1h) |
| t_div | `{values: [ms,…], u:"ms"}` | OscillClient.TDIV_VALUES_MS (full supported step set) |
| v_offset | `{min:0, max:255}` | structural raw range |
| trigger_level | `{min:0, max:255}` | structural raw range |
| samples_total | `{min:1, max:int}` | device prop QSh, reconciled to delivered-space (QSh − drop) |
| t_offset | `{min:0, max:int}` | derived: delivered samples_total − 1 |

`apply_config` **silently clamps** each incoming value before writing the register — to `[min,max]`
for continuous params, and to `[min(values), max(values)]` for stepped params (consistent with the
existing v_offset/trigger_level clamping; no warning appended).

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

### connect(endpoint=None, *, port=None, baud=115200) → Dict
- [SP_BTT_02_09] Backward-compatible superset: legacy `connect("/dev/ttyUSB0", 115200)` still works
  (first positional str is routed to `port`). Prefer a `ConnectionEndpoint` (serial | bluetooth);
  when none is given the env/legacy default resolves it ([SP_BTT_02_08]).
- **Errors:** `TimeoutError` (serial 5s / Bluetooth 50s budget), `DeviceNotFound` if serial-auto
  finds no CP210x, `BluetoothUnreachable` / `ChannelResolutionError` / `ConfigError` for the BT path
  ([SP_BTT_02_09]).
- **Side effects:** starts acquisition loop; snapshots config. The response adds a `transport`
  label (link description); the serial speed-raise is gated to serial endpoints only.

### connect_auto(baud=115200) → Dict  *(SP_BTT_02_12)*
- Auto-selects the transport: tries **USB serial first**, then **Bluetooth** (address resolved by
  name among paired devices) if a paired scope exists. First candidate that connects wins; a failed
  attempt is fully torn down before the next. Executor budget = Bluetooth (50s) when a BT candidate
  is present, else serial (5s).
- **Errors:** `DeviceNotFound("no transport available…")` when neither USB nor a paired BT connects.

### ensure_connected(endpoint=None, *, port=None, baud=115200) → Dict
- Returns current status if already connected. With no endpoint and no port → **auto** path
  (`connect_auto`, USB→BT); an explicit endpoint/port → `connect()`.
- Never raises — returns `{status: "disconnected", error: ...}` on failure

### disconnect() → Dict
- Stops acquisition; closes serial; clears frame buffer; clears cached config

### is_connected() → bool
- Public accessor: True when a device is connected (`_is_connected and _client`).
- **(PL_AUDIT_WEB)** The web layer uses this instead of touching the private `_client` handle
  (rule `HardwareAccessOnlyThroughDeviceService`).

### is_acquiring() → bool
- Public accessor: True when the background acquisition loop is running.
- Used by the web layer in place of the private `_is_acquiring` flag.

### display_geometry() → Dict  *(instance method)*
- Returns `{h_divs: int, samples_per_div: int}` = `{OscillClient.H_DIVS (8), <live density>}`.
- **(task_qs-raise)** `samples_per_div` is the connected client's live per-mode density (223 / 111),
  falling back to the class default (32) when disconnected. Changed from a staticmethod to an
  instance method so it can read the live density. Call site `service.display_geometry()` unchanged.
- **(PL_AUDIT_WEB)** Single source of truth for display grid geometry so the web layer need not
  import `OscillClient` directly nor hardcode a copy.

### get_status() → Dict
- No device I/O — returns cached config

### apply_config(changes: Dict) → Tuple[Dict, List[str]]
- `changes` keys: v_div, v_offset, t_div, t_offset, trigger_level, trigger_mode, trigger_slope, coupling, filter_high, filter_low, sw_mode, sync_type, sync_front, sync_back
- Returns (status_dict, warnings_list)
- Frame buffer cleared after any config change
- **(task_qs-raise)** After applying a mode change, the sampling density is re-derived from QSh
  (`OscillClient.refresh_samples_per_div`); if it changed, the current t/div is re-applied before
  `ensure_qs` so the timebase is preserved at the new density. The delivered-length cache
  (`_last_delivered_len`) is reset before the response snapshot, so the apply response reconciles
  against the requested QS-space rather than a stale cross-mode delivered length (e.g. AVG_HIRES 887 →
  NORMAL 1784); the first new frame re-establishes the real delivered count.
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
- **Errors:** `start()` raises `RuntimeError("Not connected")` if no client is connected.
  `stop()` has no error path — it returns `{status: "ok"}` unconditionally.

### Background acquisition loop (`_acq_loop`)
- Pulls one frame at a time under `_dev_lock` and appends it to the ring buffer.
- **(PL_AUDIT_WEB, behavioral/non-breaking)** No longer re-reads the full register config per frame.
  It reuses the **cached** config (refreshed under lock on connect / apply_config); each frame's
  `cfg_id` is taken from that cache. A broken device is still detected by `get_frame()` (which
  raises), so the previous per-frame config snapshot health-check was redundant. This removes ~15
  serial register reads per frame.

## Validation Rules

- v_offset clamped to [0, 0xFF]
- t_offset (incoming) is in **delivered-space** and converted back to the device TC register via `TC = delivered_index + (QS − delivered) + 1` (inverse of the read-side reconcile), then clamped to [0, 0xFF]. Reported t_offset is clamped to [0, delivered−1].
- trigger_slope: "RISING"/"FALLING"/"BOTH"/"NONE" (case-insensitive via _normalize_key)
- coupling: "DC"/"AC"/"GND" (case-insensitive)
- Invalid sw_mode / sync_type → warning in list, not error
