# Specification: Web API Server (SP_WEB)

> **ID:** SP_WEB
> **Status:** active
> **Implements:** C_WEB
> **Depends on specs:** SP_DSV, SP_CAL, SP_AAJ, SP_CVT
> **Used by specs:** — (top of Python stack)
> **Changelog:** Initialized from existing codebase via onboard procedure (2026-04-22)

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
- **Logic:** Waits up to 5s for frames if buffer is empty and device is active.
  Frame dicts include `measurements: {freq?, period?, v_pp, v_max, v_min, v_avg}` each as `{v,u}`.

### POST /api/auto
- **Query:** `types?: string` (comma-separated: "v_div,t_div,v_offset,trigger")
- **Response:** `{success: bool, applied: List[str], config: ConfigDict}`
- **Errors:** 400 if not connected or invalid types; 500 on error

### POST /api/start / POST /api/stop
- **Response:** `{status: "ok"}`

### GET /
- **Response:** FileResponse(static/index.html)

### GET /static/{path}
- **Response:** FileResponse for any file in static/

## Request Models

### ConfigReq (Pydantic)
| Field | Type | Notes |
|-------|------|-------|
| v_div | Optional[{v,u}] | V/div as structured value |
| t_div | Optional[{v,u}] | T/div as structured value |
| v_offset | Optional[int\|float\|{v,u}] | Raw 0..255 or dict |
| t_offset | Optional[int\|float\|{v,u}] | In samples |
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

- POST /api/config → 400 if service._client is None
- POST /api/auto → 400 if not connected; 400 if invalid type names
- All device errors → 500 with `detail: str(e)`
