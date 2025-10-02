from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Union
import os
import time
import orjson

import sys
import os
sys.path.append(os.path.dirname(__file__))

from oscill_client import OscillClient
from device_service import DeviceService
from converters import get_voltage_mv, get_time_ms


class ORJSONResponse(JSONResponse):
    """Fast JSON response using orjson for serialization."""
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content, option=orjson.OPT_SERIALIZE_NUMPY)


app = FastAPI(title="Oscill2 Web App", default_response_class=ORJSONResponse)

# Add GZip compression middleware (applies to responses >= 1KB)
app.add_middleware(GZipMiddleware, minimum_size=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# In-memory singleton service instance
service = DeviceService(buffer_size=256)
client: Optional[OscillClient] = None  # backwards-compat variable name used in handlers

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
    global client
    try:
        if req and req.port:
            # Explicit connection to specified port
            res = service.connect(req.port, req.baud)
        else:
            # Auto-connect if needed
            baud = req.baud if req else 115200
            res = service.ensure_connected(port=None, baud=baud)
        # expose client for legacy handlers during migration
        client = service._client
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/disconnect")
def api_disconnect():
    global client
    try:
        res = service.disconnect()
        client = None
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/acquire/single")
def api_acquire_single():
    if not service._client:
        # Respond gracefully so frontends can gate polling without error spam
        return {"status": "disconnected", "message": "Not connected"}
    try:
        status = service.get_status()
        frame = service.get_latest_frame()
        if not frame:
            raise HTTPException(status_code=502, detail="No data")
        # Use current config snapshot from status (already includes cfg_id)
        cfg = (status or {}).get("config", {}) or {}
        frame_cfg_id = frame.get("cfg_id")
        if frame_cfg_id is not None and cfg.get("cfg_id") is None:
            cfg = dict(cfg)
            cfg["cfg_id"] = frame_cfg_id
        v_div_mv = get_voltage_mv(cfg)
        t_div_ms = get_time_ms(cfg)
        samples = list(frame.get("samples", []) or [])
        sample_bits = int(frame.get("sample_bits") or 8)
        peak_min = list(frame.get("samples_peak_min", []) or [])
        peak_max = list(frame.get("samples_peak_max", []) or [])

        if peak_min and peak_max and (not samples or len(samples) != min(len(peak_min), len(peak_max))):
            count = min(len(peak_min), len(peak_max))
            samples = [ (peak_min[i] + peak_max[i]) // 2 for i in range(count) ]

        samples_mv = None
        peak_min_mv = None
        peak_max_mv = None
        min_mv = None
        max_mv = None

        if v_div_mv is not None:
            if samples:
                samples_mv = _samples_to_millivolts(samples, sample_bits, cfg)
            if peak_min:
                peak_min_mv = _samples_to_millivolts(peak_min, sample_bits, cfg)
            if peak_max:
                peak_max_mv = _samples_to_millivolts(peak_max, sample_bits, cfg)

            try:
                if peak_min_mv and peak_max_mv:
                    min_mv = min(peak_min_mv)
                    max_mv = max(peak_max_mv)
                elif samples_mv:
                    min_mv = min(samples_mv)
                    max_mv = max(samples_mv)
            except Exception:
                min_mv = None
                max_mv = None
        return {
            "status": "ok",
            "v_div": {"v": v_div_mv, "u": "mV"},
            "t_div": {"v": t_div_ms, "u": "ms"},
            "samples": samples,
            "samples_peak_min": peak_min,
            "samples_peak_max": peak_max,
            "samples_voltage": {"values": samples_mv, "u": "mV"} if samples_mv else None,
            "samples_peak_min_voltage": {"values": peak_min_mv, "u": "mV"} if peak_min_mv else None,
            "samples_peak_max_voltage": {"values": peak_max_mv, "u": "mV"} if peak_max_mv else None,
            "min_voltage": {"v": min_mv, "u": "mV"} if min_mv is not None else None,
            "max_voltage": {"v": max_mv, "u": "mV"} if max_mv is not None else None,
            "channels": frame.get("channels", 1),
            "time": frame.get("time"),
            "time_iso": frame.get("time_iso"),
            "cfg_id": frame_cfg_id,
            "config": cfg,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
def api_status():
    st = service.get_status()
    if st.get("status") == "ok":
        # Convert config to new format with units
        config = st.get("config", {})
        new_config = config  # Already in correct format
        st["config"] = new_config
    return st

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
    if not service._client:
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
            # Convert string to int (assuming mapping)
            mode_map = {"Auto": 0x2C, "Normal": 0x2D, "Single": 0x2E}
            changes["trigger_mode"] = mode_map.get(req.trigger_mode, 0x2C)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        if not service._client:
            return {"status": "disconnected", "frames": []}
        
        # If acquisition is running and we would return an empty list, wait for frames
        data = service.get_frames(since=since, limit=limit)
        frames = data.get("frames", [])
        
        if not frames:
            if service._is_acquiring:
                # Wait up to 5 seconds for new frames to arrive
                max_wait_time = 5.0
                wait_interval = 0.05  # Check every 50ms
                elapsed = 0.0
                
                while elapsed < max_wait_time and service._is_acquiring:
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
        
        for frame in frames:
            processed_frame = dict(frame)
            processed_frame.pop("config", None)
            
            # Convert samples to hex format if requested
            if use_hex:
                sample_bytes = frame.get("sample_bytes", 1)
                if "samples" in processed_frame and processed_frame["samples"]:
                    processed_frame["samples_hex"] = _samples_to_hex(processed_frame["samples"], sample_bytes)
                    del processed_frame["samples"]
                if "samples_peak_min" in processed_frame and processed_frame["samples_peak_min"]:
                    processed_frame["samples_peak_min_hex"] = _samples_to_hex(processed_frame["samples_peak_min"], sample_bytes)
                    del processed_frame["samples_peak_min"]
                if "samples_peak_max" in processed_frame and processed_frame["samples_peak_max"]:
                    processed_frame["samples_peak_max_hex"] = _samples_to_hex(processed_frame["samples_peak_max"], sample_bytes)
                    del processed_frame["samples_peak_max"]
            
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/start")
def api_start():
    """Start data acquisition."""
    if not service._client:
        raise HTTPException(status_code=400, detail="Not connected")
    try:
        res = service.start()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stop")
def api_stop():
    """Stop data acquisition."""
    try:
        res = service.stop()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serve static index.html
static_dir = os.path.join(os.path.dirname(__file__), "static")

@app.get("/")
def index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/static/{path:path}")
def static_files(path: str):
    fp = os.path.join(static_dir, path)
    if not os.path.isfile(fp):
        raise HTTPException(status_code=404)
    return FileResponse(fp)

def _samples_to_hex(samples: List[int], sample_bytes: int = 1) -> str:
    """Convert samples list to hex string for compact transmission."""
    if not samples:
        return ""
    if sample_bytes == 1:
        return ''.join(f'{s:02x}' for s in samples)
    elif sample_bytes == 2:
        return ''.join(f'{s:04x}' for s in samples)
    else:
        return ''.join(f'{s:02x}' for s in samples)


def _samples_from_hex(hex_str: str, sample_bytes: int = 1) -> List[int]:
    """Decode hex string back to samples list."""
    if not hex_str:
        return []
    chars_per_sample = sample_bytes * 2
    return [int(hex_str[i:i+chars_per_sample], 16) 
            for i in range(0, len(hex_str), chars_per_sample)]


def _samples_to_millivolts(samples: List[int], sample_bits: int, config: Dict[str, Any]) -> List[float]:
    if not samples:
        return []
    v_div_mv = get_voltage_mv(config)
    full_scale_mv = v_div_mv * 8.0
    max_code = (1 << sample_bits) - 1
    center = max_code / 2.0
    if center <= 0:
        return [0.0 for _ in samples]
    scale = full_scale_mv / 2.0
    return [((s - center) / center) * scale for s in samples]


def calculate_measurements(frame: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate measurements from frame metadata: frequency, period, Vpp, Vmax, Vmin, Vavg."""
    if not frame:
        return {}

    sample_bits = int(frame.get("sample_bits") or 8)
    samples = list(frame.get("samples") or [])
    peak_min = frame.get("samples_peak_min") or []
    peak_max = frame.get("samples_peak_max") or []

    if peak_min and peak_max:
        count = min(len(peak_min), len(peak_max))
        peak_min = list(peak_min[:count])
        peak_max = list(peak_max[:count])
        if not samples or len(samples) != count:
            samples = [(lo + hi) // 2 for lo, hi in zip(peak_min, peak_max)]

    if not samples:
        return {}

    voltages_mv = _samples_to_millivolts(samples, sample_bits, config)
    if not voltages_mv:
        return {}

    if peak_min and peak_max:
        voltages_min_mv = _samples_to_millivolts(peak_min, sample_bits, config)
        voltages_max_mv = _samples_to_millivolts(peak_max, sample_bits, config)
        v_min_mv = min(voltages_min_mv) if voltages_min_mv else min(voltages_mv)
        v_max_mv = max(voltages_max_mv) if voltages_max_mv else max(voltages_mv)
    else:
        v_min_mv = min(voltages_mv)
        v_max_mv = max(voltages_mv)

    v_pp_mv = v_max_mv - v_min_mv
    v_avg_mv = sum(voltages_mv) / len(voltages_mv)

    # Frequency and period calculation (simple zero-crossing method) on averaged waveform
    freq = None
    period = None
    try:
        zero_crossings: List[int] = []
        threshold = v_avg_mv
        for i in range(1, len(voltages_mv)):
            prev = voltages_mv[i - 1]
            current = voltages_mv[i]
            if (prev <= threshold < current) or (prev >= threshold > current):
                zero_crossings.append(i)
        if len(zero_crossings) >= 2:
            diffs = [zero_crossings[i] - zero_crossings[i - 1] for i in range(1, len(zero_crossings))]
            if diffs:
                avg_period_samples = sum(diffs) / len(diffs)
                samples_per_div = config.get("samples_per_div", 32)
                t_div_ms = get_time_ms(config)
                time_per_sample = (t_div_ms / 1000.0) / max(1, samples_per_div)
                period_s = avg_period_samples * time_per_sample
                if period_s > 0:
                    freq = 1.0 / period_s
                    period = period_s
    except Exception:
        pass

    measurements: Dict[str, Any] = {}
    if freq is not None:
        measurements["freq"] = {"v": freq, "u": "Hz"}
    if period is not None:
        measurements["period"] = {"v": period, "u": "s"}
    measurements["v_pp"] = {"v": v_pp_mv / 1000.0, "u": "V"}
    measurements["v_max"] = {"v": v_max_mv / 1000.0, "u": "V"}
    measurements["v_min"] = {"v": v_min_mv / 1000.0, "u": "V"}
    measurements["v_avg"] = {"v": v_avg_mv / 1000.0, "u": "V"}

    return measurements
