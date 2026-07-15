# Specification: Web API Server (SP_WEB)

> **ID:** SP_WEB
> **Status:** active
> **Implements:** C_WEB
> **Depends on specs:** SP_DSV, SP_CAL, SP_AAJ, SP_CVT
> **Used by specs:** — (top of Python stack)
> **Changelog:**
> - Initialized from existing codebase via onboard procedure (2026-04-22)
> - 2026-07-15 code-audit reconciliation (PL_AUDIT_WEB): documented GET /api/frames side effect that temporarily starts/stops acquisition when the buffer is empty and acquisition is stopped
> - 2026-07-15 — PL_AUDIT_WEB code-audit propagation: documented new GET /api/config/options endpoint; CORS restricted to localhost (allow_credentials=False), GZip minimum_size=1000, /static/{path} 403 path-traversal guard; generic error messages (no str(e) leak)
> - 2026-07-15 — ConfigDict gains a `limits` block (per-parameter min/max) for client informativeness; apply_config silently clamps incoming values to those limits. See SP_DSV (device_service.sp.md → ConfigDict.limits).

## Middleware & Hardening

- **CORS** (PL_AUDIT_WEB): restricted to localhost origins via `allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?"` with `allow_credentials=False` (previously wildcard `*`). The frontend is served same-origin, so a random site the user visits cannot drive the device-control API from their browser.
- **GZip**: `minimum_size=1000` bytes (previously 500). The small, frequent status/frame responses in this ~10 Hz polling API fall below the compression-benefit threshold.

## Endpoints

### POST /api/connect
- **Body:** `{port?: string, baud?: int}` (optional)
- **Response:** DeviceService status dict
- **Logic:** port specified → explicit connect; no port → ensure_connected (auto-detect)

### POST /api/disconnect
- **Response:** `{status: "ok"}`

### GET /api/status
- **Response:** DeviceService status dict (cached, no device I/O)

### POST /api/config
- **Body:** ConfigReq (all fields optional)
- **Response:** `{status: "ok", config: ConfigDict, warnings: List[str], cfg_id: int}`
- **Errors:** 400 if not connected; 500 on device error

### GET /api/frames
- **Query:** `since?: int, limit?: int (default 128), format?: "hex"|"array" (default "hex")`
- **Response:** `{config: ConfigDict, frames: List[FrameDict], newest_seq: int, format: str}`
- **Logic:** If the buffer is empty:
  - device is acquiring → waits up to 5s polling every 50ms for frames to arrive (pure read).
  - device is connected but acquisition is STOPPED → **state-mutating side effect**: temporarily calls
    `service.start()`, polls up to 5s for one frame, then always calls `service.stop()` in a `finally`
    block. So this "read" endpoint may briefly start and stop device acquisition to return a frame.
  Frame dicts include `measurements: {freq?, period?, v_pp, v_max, v_min, v_avg}` each as `{v,u}`.
- **Design smell (known, revisit):** a GET/read endpoint that mutates device state (start/stop acquisition)
  is a side-effect-in-a-reader anti-pattern. Flagged for future redesign (e.g., an explicit
  "capture one frame" action or requiring acquisition to be started by the caller).

### POST /api/auto
- **Query:** `types?: string` (comma-separated: "v_div,t_div,v_offset,trigger")
- **Response:** `{success: bool, applied: List[str], config: ConfigDict}`
- **Errors:** 400 if not connected or invalid types; 500 on error

### POST /api/start / POST /api/stop
- **Response:** `{status: "ok"}`

### GET /api/config/options
- **Query/Body:** none
- **Response:** `{v_div_values_mv: List[float], t_div_values_ms: List[float], h_divs: int, samples_per_div: int}`
- **Purpose (PL_AUDIT_WEB):** single source of truth for constants the frontend must agree on — the
  V/div and Time/div step lists (from `auto_adjust`) and the display grid geometry (`h_divs`=8,
  `samples_per_div`) from `service.display_geometry()`. The frontend fetches these instead of
  hardcoding its own copies (rule `SingleSourceForSharedConstants`).

### GET /
- **Response:** FileResponse(static/index.html)

### GET /static/{path}
- **Response:** FileResponse for a file inside static/
- **Hardening (PL_AUDIT_WEB):** rejects path traversal with **403** — the requested path is resolved
  with `os.path.realpath` and must stay contained in `static_dir` (checked via `os.path.commonpath`).
  Requests like `/static/../../etc/passwd` are refused. Missing files still return 404.

## Request Models

### ConfigReq (Pydantic)
| Field | Type | Notes |
|-------|------|-------|
| v_div | Optional[{v,u}] | V/div as structured value |
| t_div | Optional[{v,u}] | T/div as structured value |
| v_offset | Optional[int\|float\|{v,u}] | Raw 0..255 or dict |
| t_offset | Optional[int\|float\|{v,u}] | In **delivered-space** samples (trigger index in the plotted array); DeviceService converts to the device TC register. See device_service.sp.md. |
| trigger_level | Optional[int] | 0..255 |
| trigger_mode | Optional[str] | "Auto"/"Normal"/"Single" |
| trigger_slope | Optional[str] | "Rising"/"Falling"/"Both"/"None" |
| coupling | Optional[str] | "AC"/"DC"/"GND" |
| filter_high | Optional[bool] | HW high-pass filter |
| filter_low | Optional[bool] | HW low-pass filter |
| sw_mode | Optional[str] | "NORMAL"/"AVG"/"AVG_HIRES"/"PEAK"/"PEAK_HI" |
| sync_type | Optional[str] | "AUTO"/"WAIT_TIMEOUT"/"FREE"/"WAIT" |
| sync_front | Optional[bool] | Rising edge trigger |
| sync_back | Optional[bool] | Falling edge trigger |

## Validation Rules

- POST /api/config → 400 if not connected (via `service.is_connected()`)
- POST /api/auto → 400 if not connected; 400 if invalid type names
- All device errors → 500 with a **generic** `detail` (e.g. "Connection failed", "Failed to apply
  configuration", "Failed to fetch frames"). Internal exception text is logged server-side
  (`log.exception`) but **no longer leaked** to the client via `str(e)` (PL_AUDIT_WEB).
