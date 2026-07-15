from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union
import logging
import os
import time
import orjson

import sys
sys.path.append(os.path.dirname(__file__))

from device_service import DeviceService
from converters import get_voltage_mv, get_time_ms
from calculations import (
    samples_to_hex,
    samples_from_hex,
    samples_to_millivolts,
    calculate_voltage_range,
    calculate_measurements
)
from auto_adjust import auto_adjust_multiple, VDIV_VALUES_MV, TDIV_VALUES_MS

log = logging.getLogger("web_api")


class ORJSONResponse(JSONResponse):
    """Fast JSON response using orjson for serialization."""
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_SERIALIZE_NUMPY)


app = FastAPI(title="Oscill2 Web App", default_response_class=ORJSONResponse)

# [PL_AUDIT_WEB_B7] GZip threshold raised to 1000 bytes: small/frequent status &
# frame responses in this 10 Hz polling API are below typical compression benefit.
app.add_middleware(GZipMiddleware, minimum_size=1000)

# [PL_AUDIT_WEB_07] The frontend is served same-origin by this app, so wildcard CORS
# is unnecessary. Restrict to localhost origins (any port) and drop credentialed CORS
# so a random website the user visits cannot drive the device-control API in their browser.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# In-memory singleton service instance
service = DeviceService(buffer_size=256)

class ConnectReq(BaseModel):
    port: Optional[str] = None
    baud: int = 115200

@app.post("/api/connect")
def api_connect(req: Optional[ConnectReq] = None):
    """
    Connect to device or ensure connection.
    If port is specified, explicitly connect to that port.
    If port is None/not specified, use ensure_connected (auto-detect).
    """
    try:
        if req and req.port:
            # Explicit connection to specified port
            res = service.connect(req.port, req.baud)
        else:
            # Auto-connect if needed
            baud = req.baud if req else 115200
            res = service.ensure_connected(port=None, baud=baud)
        return res
    except Exception:
        log.exception("connect failed")
        raise HTTPException(status_code=500, detail="Connection failed")

@app.post("/api/disconnect")
def api_disconnect():
    try:
        return service.disconnect()
    except Exception:
        log.exception("disconnect failed")
        raise HTTPException(status_code=500, detail="Disconnect failed")

@app.get("/api/status")
def api_status():
    # [PL_AUDIT_WEB_B15] Wrap so a device/service error surfaces as HTTP 500
    # (rule PythonCatchAndReraise500) rather than an unhandled 500 with a trace.
    try:
        return service.get_status()
    except Exception:
        log.exception("status failed")
        raise HTTPException(status_code=500, detail="Failed to read status")

class ConfigReq(BaseModel):
    v_div: Optional[Dict[str, Any]] = None
    t_div: Optional[Dict[str, Any]] = None
    v_offset: Optional[Union[int, float, Dict[str, Any]]] = None
    t_offset: Optional[Union[int, float, Dict[str, Any]]] = None
    trigger_level: Optional[int] = None
    trigger_mode: Optional[str] = None  # "Auto", "Normal", "Single"
    trigger_slope: Optional[str] = None  # "Rising", "Falling"
    coupling: Optional[str] = None  # "AC", "DC", "GND"
    filter_high: Optional[bool] = None
    filter_low: Optional[bool] = None
    sw_mode: Optional[str] = None
    sync_type: Optional[str] = None
    sync_front: Optional[bool] = None
    sync_back: Optional[bool] = None

@app.post("/api/config")
def api_config(req: ConfigReq):
    if not service.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    try:
        # Convert string values to appropriate formats
        changes = {}
        if req.v_div is not None:
            changes["v_div"] = req.v_div
        if req.t_div is not None:
            changes["t_div"] = req.t_div
        if req.v_offset is not None:
            changes["v_offset"] = req.v_offset
        if req.t_offset is not None:
            changes["t_offset"] = req.t_offset
        if req.trigger_level is not None:
            changes["trigger_level"] = req.trigger_level
        if req.trigger_mode is not None:
            # [PL_AUDIT_WEB_B3] Pass the mode name through; DeviceService owns the
            # name->register mapping (single source of truth). Do not duplicate the
            # {Auto,Normal,Single}->register map here.
            changes["trigger_mode"] = req.trigger_mode
        if req.trigger_slope is not None:
            # This might need to be handled in device_service
            changes["trigger_slope"] = req.trigger_slope
        if req.coupling is not None:
            # This might need to be handled in device_service
            changes["coupling"] = req.coupling
        if req.filter_high is not None:
            changes["filter_high"] = req.filter_high
        if req.filter_low is not None:
            changes["filter_low"] = req.filter_low
        if req.sw_mode is not None:
            changes["sw_mode"] = req.sw_mode
        if req.sync_type is not None:
            changes["sync_type"] = req.sync_type
        if req.sync_front is not None:
            changes["sync_front"] = req.sync_front
        if req.sync_back is not None:
            changes["sync_back"] = req.sync_back

        status, warnings = service.apply_config(changes)
        # Convert embedded config to UI format for consistency
        raw_cfg = status.get("config", {}) if isinstance(status, dict) else {}
        new_config = raw_cfg  # Already in correct format
        response = {"status": "ok", "config": new_config, "warnings": warnings}
        if isinstance(status, dict) and status.get("cfg_id") is not None:
            response["cfg_id"] = status["cfg_id"]
        return response
    except Exception:
        log.exception("apply config failed")
        raise HTTPException(status_code=500, detail="Failed to apply configuration")

@app.get("/api/frames")
def api_frames(since: Optional[int] = None, limit: int = 128, format: str = "hex"):
    """
    Get frames from buffer.
    
    Args:
        since: Get frames with seq > since
        limit: Maximum number of frames to return
        format: "hex" (compact hex strings) or "array" (JSON arrays)
    """
    try:
        if not service.is_connected():
            return {"status": "disconnected", "frames": []}

        # If acquisition is running and we would return an empty list, wait for frames
        data = service.get_frames(since=since, limit=limit)
        frames = data.get("frames", [])

        if not frames:
            if service.is_acquiring():
                # Wait up to 5 seconds for new frames to arrive
                max_wait_time = 5.0
                wait_interval = 0.05  # Check every 50ms
                elapsed = 0.0

                while elapsed < max_wait_time and service.is_acquiring():
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                    
                    data = service.get_frames(since=since, limit=limit)
                    frames = data.get("frames", [])
                    
                    if frames:
                        break
            else:
                # Acquisition is stopped - temporarily start it to get one frame
                try:
                    service.start()
                    # Wait for at least one frame to arrive
                    max_wait_time = 5.0
                    wait_interval = 0.05
                    elapsed = 0.0
                    
                    while elapsed < max_wait_time:
                        time.sleep(wait_interval)
                        elapsed += wait_interval
                        
                        data = service.get_frames(since=since, limit=limit)
                        frames = data.get("frames", [])
                        
                        if frames:
                            break
                finally:
                    # Always stop acquisition again
                    service.stop()
        
        # Convert config to new format
        current_config = service.get_status().get("config", {})
        new_config = current_config  # Already in correct format
        
        # Process frames and add measurements
        processed_frames = []
        use_hex = format.lower() == "hex"
        # [PL_AUDIT_WEB_B9] The client renders only the newest frame, so compute the
        # (relatively expensive) measurements just for it, not for every buffered frame.
        newest_idx = len(frames) - 1

        for i, frame in enumerate(frames):
            processed_frame = dict(frame)
            processed_frame.pop("config", None)

            # Convert samples to hex format if requested
            if use_hex:
                sample_bytes = frame.get("sample_bytes", 1)
                if "samples" in processed_frame and processed_frame["samples"]:
                    processed_frame["samples_hex"] = samples_to_hex(processed_frame["samples"], sample_bytes)
                    del processed_frame["samples"]
                if "samples_peak_min" in processed_frame and processed_frame["samples_peak_min"]:
                    processed_frame["samples_peak_min_hex"] = samples_to_hex(processed_frame["samples_peak_min"], sample_bytes)
                    del processed_frame["samples_peak_min"]
                if "samples_peak_max" in processed_frame and processed_frame["samples_peak_max"]:
                    processed_frame["samples_peak_max_hex"] = samples_to_hex(processed_frame["samples_peak_max"], sample_bytes)
                    del processed_frame["samples_peak_max"]

            if i == newest_idx:
                measurements = calculate_measurements(frame, current_config)
                if measurements:
                    processed_frame["measurements"] = measurements
            processed_frames.append(processed_frame)

        return {
            "config": new_config,
            "frames": processed_frames,
            "newest_seq": data.get("newest_seq", 0),
            "format": "hex" if use_hex else "array"
        }
    except Exception:
        log.exception("frames fetch failed")
        raise HTTPException(status_code=500, detail="Failed to fetch frames")

@app.post("/api/auto")
def api_auto(types: Optional[str] = None):
    """
    Automatically adjust oscilloscope parameters.
    
    Query parameter:
        types: Comma-separated list of adjustment types: v_div, t_div, v_offset, trigger
        Example: /api/auto?types=v_div,t_div
    
    Returns:
        Adjustment results with new configuration
    """
    if not service.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")

    try:
        # Parse types parameter
        if not types:
            # Default: auto-adjust all
            types_list = ['v_div', 't_div', 'v_offset', 'trigger']
        else:
            types_list = [t.strip() for t in types.split(',')]
        
        # Validate types
        valid_types = ['v_div', 't_div', 'v_offset', 'trigger']
        invalid_types = [t for t in types_list if t not in valid_types]
        if invalid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid adjustment types: {', '.join(invalid_types)}. "
                       f"Valid types: {', '.join(valid_types)}"
            )
        
        # Get current config
        status = service.get_status()
        if not status or 'config' not in status:
            raise HTTPException(status_code=500, detail="Cannot get current config")
        
        config = status['config'].copy()
        
        # Apply auto-adjustments
        success = auto_adjust_multiple(service, config, types_list)
        
        # Return results
        return {
            'success': success,
            'applied': types_list if success else [],
            'config': config
        }
        
    except HTTPException:
        raise
    except Exception:
        log.exception("auto-adjust failed")
        raise HTTPException(status_code=500, detail="Auto-adjust failed")

@app.post("/api/start")
def api_start():
    """Start data acquisition."""
    if not service.is_connected():
        raise HTTPException(status_code=400, detail="Not connected")
    try:
        return service.start()
    except Exception:
        log.exception("start failed")
        raise HTTPException(status_code=500, detail="Failed to start acquisition")

@app.post("/api/stop")
def api_stop():
    """Stop data acquisition."""
    try:
        return service.stop()
    except Exception:
        log.exception("stop failed")
        raise HTTPException(status_code=500, detail="Failed to stop acquisition")

@app.get("/api/config/options")
def api_config_options():
    """
    [PL_AUDIT_WEB_06] Single source of truth for constants the frontend must agree
    on: the V/div and Time/div step lists, and the display grid geometry (h_divs,
    samples_per_div). The frontend fetches these instead of hardcoding its own copies.
    """
    geometry = service.display_geometry()
    return {
        "v_div_values_mv": VDIV_VALUES_MV,
        "t_div_values_ms": TDIV_VALUES_MS,
        "h_divs": geometry["h_divs"],
        "samples_per_div": geometry["samples_per_div"],
    }

# Serve static index.html
static_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), "static"))

@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/static/{path:path}")
def static_files(path: str):
    # [PL_AUDIT_WEB_S1] Prevent path traversal: resolve the requested path and
    # confirm it stays inside static_dir before serving. Without this, a request
    # like /static/../../etc/passwd escapes the static root.
    fp = os.path.realpath(os.path.join(static_dir, path))
    if os.path.commonpath([static_dir, fp]) != static_dir:
        raise HTTPException(status_code=403, detail="Forbidden")
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404)
    return FileResponse(fp)


