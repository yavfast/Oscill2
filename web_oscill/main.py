from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import os

import sys
import os
sys.path.append(os.path.dirname(__file__))

from oscill_client import OscillClient
from device_service import DeviceService
from converters import get_voltage_mv, get_time_ms, get_offset_v

app = FastAPI(title="Oscill2 Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory singleton service instance
service = DeviceService(buffer_size=256)
client: Optional[OscillClient] = None  # backwards-compat variable name used in handlers

class ConnectReq(BaseModel):
    port: Optional[str] = None
    baud: int = 115200

@app.post("/api/connect")
def api_connect(req: ConnectReq):
    global client
    try:
        res = service.connect(req.port, req.baud)
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
        frame = service.get_latest_frame()
        if not frame:
            raise HTTPException(status_code=502, detail="No data")
        # compute scaled mV values from raw samples given current V/div in frame's config
        cfg = (frame or {}).get("config", {})
        v_div_mv = get_voltage_mv(cfg)
        t_div_ms = get_time_ms(cfg)
        samples = frame.get("samples", [])
        samples_mv = None
        min_mv = None
        max_mv = None
        if v_div_mv is not None and samples:
            full_scale_mv = v_div_mv * 8.0
            center = 127.5
            # The offset is applied on the device, so raw samples are already shifted.
            # We just need to scale them to the voltage range.
            samples_mv = [ ((s - center) / 128.0) * (full_scale_mv / 2.0) for s in samples ]
            try:
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
            "samples_voltage": {"values": samples_mv, "u": "mV"} if samples_mv else None,
            "min_voltage": {"v": min_mv, "u": "mV"} if min_mv is not None else None,
            "max_voltage": {"v": max_mv, "u": "mV"} if max_mv is not None else None,
            "channels": frame.get("channels", 1),
            "time": frame.get("time"),
            "time_iso": frame.get("time_iso"),
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
    v_offset: Optional[Dict[str, Any]] = None
    t_offset: Optional[Dict[str, Any]] = None
    trigger_level: Optional[int] = None
    trigger_mode: Optional[str] = None  # "Auto", "Normal", "Single"
    trigger_slope: Optional[str] = None  # "Rising", "Falling"
    coupling: Optional[str] = None  # "AC", "DC", "GND"
    # Legacy support
    v_div_mV: Optional[int] = None
    t_div_s: Optional[float] = None
    offset_V: Optional[float] = None
    t_offset_samples: Optional[int] = None

@app.post("/api/config")
def api_config(req: ConfigReq):
    if not service._client:
        raise HTTPException(status_code=400, detail="Not connected")
    try:
        # Convert string values to appropriate formats
        changes = {}
        if req.v_div is not None:
            changes["v_div"] = req.v_div
        elif req.v_div_mV is not None:  # Legacy
            changes["v_div"] = {"v": req.v_div_mV, "u": "mV"}
        if req.t_div is not None:
            changes["t_div"] = req.t_div
        elif req.t_div_s is not None:  # Legacy
            changes["t_div"] = {"v": req.t_div_s * 1000, "u": "ms"}
        if req.v_offset is not None:
            changes["v_offset"] = req.v_offset
        elif req.offset_V is not None:  # Legacy
            changes["v_offset"] = {"v": req.offset_V, "u": "V"}
        if req.t_offset is not None:
            changes["t_offset"] = req.t_offset
        elif req.t_offset_samples is not None:  # Legacy
            changes["t_offset"] = {"v": req.t_offset_samples, "u": "samples"}
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

        status, warnings = service.apply_config(changes)
        # Convert embedded config to UI format for consistency
        raw_cfg = status.get("config", {}) if isinstance(status, dict) else {}
        new_config = raw_cfg  # Already in correct format
        return {"status": "ok", "config": new_config, "warnings": warnings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/frames")
def api_frames(since: Optional[int] = None, limit: int = 64):
    try:
        if not service._client:
            return {"status": "disconnected", "frames": []}
        data = service.get_frames(since=since, limit=limit)
        frames = data.get("frames", [])
        
        # Convert config to new format
        current_config = service.get_status().get("config", {})
        new_config = current_config  # Already in correct format
        
        # Process frames and add measurements
        processed_frames = []
        for frame in frames:
            processed_frame = dict(frame)
            samples = frame.get("samples", [])
            if samples:
                measurements = calculate_measurements(samples, current_config)
                processed_frame["measurements"] = measurements
            processed_frames.append(processed_frame)
        
        return {
            "config": new_config,
            "frames": processed_frames,
            "newest_seq": data.get("newest_seq", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/acquisition/start")
def api_acquisition_start():
    if not service._client:
        raise HTTPException(status_code=400, detail="Not connected")
    try:
        res = service.start_acquisition()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/acquisition/stop")
def api_acquisition_stop():
    try:
        res = service.stop_acquisition()
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

def calculate_measurements(samples: List[int], config: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate measurements from samples: frequency, period, Vpp, Vmax, Vmin, Vavg"""
    if not samples:
        return {}
    
    # Convert raw samples to voltage values
    v_div_mv = get_voltage_mv(config)
    offset_v = get_offset_v(config)
    t_div_ms = get_time_ms(config)
    
    # Full scale is 8 divisions * v_div
    full_scale_mv = v_div_mv * 8.0
    center = 127.5
    
    # We do not add offset_v here because the device already applied it.
    # The raw samples are shifted. We just scale them.
    voltages_mv = []
    for s in samples:
        # Convert ADC value to voltage in mV
        v_mv = ((s - center) / 128.0) * (full_scale_mv / 2.0)
        voltages_mv.append(v_mv)
    
    if not voltages_mv:
        return {}
    
    # Basic measurements
    v_min = min(voltages_mv)
    v_max = max(voltages_mv)
    v_pp = v_max - v_min
    v_avg = sum(voltages_mv) / len(voltages_mv)
    
    # Frequency and period calculation (simple zero-crossing method)
    freq = None
    period = None
    
    try:
        # Find zero crossings
        zero_crossings = []
        threshold = v_avg  # Use average as threshold
        
        for i in range(1, len(voltages_mv)):
            if (voltages_mv[i-1] <= threshold and voltages_mv[i] > threshold) or \
               (voltages_mv[i-1] >= threshold and voltages_mv[i] < threshold):
                zero_crossings.append(i)
        
        if len(zero_crossings) >= 2:
            # Calculate average period between crossings
            periods = []
            for i in range(1, len(zero_crossings)):
                periods.append(zero_crossings[i] - zero_crossings[i-1])
            
            if periods:
                avg_period_samples = sum(periods) / len(periods)
                
                # Convert to time units
                t_div_ms = get_time_ms(config)
                samples_per_div = config.get("samples_per_div", 32)
                total_samples_per_div = samples_per_div  # Assuming 10 horizontal divs
                
                # Time per sample
                time_per_sample = (t_div_ms / 1000) / total_samples_per_div
                
                period_s = avg_period_samples * time_per_sample
                freq_hz = 1.0 / period_s if period_s > 0 else None
                
                freq = freq_hz
                period = period_s
    except Exception:
        pass  # Frequency calculation failed, leave as None
    
    measurements = {}
    if freq is not None:
        measurements["freq"] = {"v": freq, "u": "Hz"}
    if period is not None:
        measurements["period"] = {"v": period, "u": "s"}
    measurements["v_pp"] = {"v": v_pp / 1000.0, "u": "V"}  # Convert to V
    measurements["v_max"] = {"v": v_max / 1000.0, "u": "V"}
    measurements["v_min"] = {"v": v_min / 1000.0, "u": "V"}
    measurements["v_avg"] = {"v": v_avg / 1000.0, "u": "V"}
    
    return measurements
