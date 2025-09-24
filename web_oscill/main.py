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
        v_div_mv = cfg.get("v_div_mV")
        t_div_s = cfg.get("t_div_s")
        samples = frame.get("samples", [])
        samples_mv = None
        min_mv = None
        max_mv = None
        if v_div_mv is not None and samples:
            full_scale_mv = v_div_mv * 8.0
            center = 127.5
            samples_mv = [ ( (s - center) / 256.0 ) * full_scale_mv for s in samples ]
            try:
                min_mv = min(samples_mv)
                max_mv = max(samples_mv)
            except Exception:
                min_mv = None
                max_mv = None
        return {
            "status": "ok",
            "v_div_mV": v_div_mv,
            "t_div_s": t_div_s,
            "samples": samples,
            "samples_mV": samples_mv,
            "min_mV": min_mv,
            "max_mV": max_mv,
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
        new_config = {}
        if "v_div_mV" in config and config["v_div_mV"] is not None:
            new_config["v_div"] = {"v": config["v_div_mV"], "u": "mV"}
        if "t_div_s" in config and config["t_div_s"] is not None:
            new_config["t_div"] = {"v": config["t_div_s"], "u": "s"}
        if "offset_V" in config and config["offset_V"] is not None:
            new_config["v_offset"] = {"v": config["offset_V"], "u": "V"}
        if "t_offset_samples" in config:
            new_config["t_offset"] = {"v": config["t_offset_samples"], "u": "samples"}
        if "trigger_level" in config:
            new_config["trigger_level"] = config["trigger_level"]
        if "trigger_mode" in config:
            new_config["trigger_mode"] = config["trigger_mode"]
        if "samples_per_div" in config:
            new_config["samples_per_div"] = config["samples_per_div"]
        if "cfg_id" in config:
            new_config["cfg_id"] = config["cfg_id"]
        st["config"] = new_config
    return st

class ConfigReq(BaseModel):
    v_div_mV: Optional[int] = None
    t_div_s: Optional[float] = None
    offset_V: Optional[float] = None
    trigger_level: Optional[int] = None
    trigger_mode: Optional[str] = None  # "Auto", "Normal", "Single"
    trigger_slope: Optional[str] = None  # "Rising", "Falling"
    coupling: Optional[str] = None  # "AC", "DC", "GND"

@app.post("/api/config")
def api_config(req: ConfigReq):
    if not service._client:
        raise HTTPException(status_code=400, detail="Not connected")
    try:
        # Convert string values to appropriate formats
        changes = {}
        if req.v_div_mV is not None:
            changes["v_div_mV"] = req.v_div_mV
        if req.t_div_s is not None:
            changes["t_div_s"] = req.t_div_s
        if req.offset_V is not None:
            changes["offset_V"] = req.offset_V
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
        return {"status": "ok", **status, "warnings": warnings}
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
        new_config = {}
        if "v_div_mV" in current_config and current_config["v_div_mV"] is not None:
            new_config["v_div"] = {"v": current_config["v_div_mV"], "u": "mV"}
        if "t_div_s" in current_config and current_config["t_div_s"] is not None:
            new_config["t_div"] = {"v": current_config["t_div_s"], "u": "s"}
        if "offset_V" in current_config and current_config["offset_V"] is not None:
            new_config["v_offset"] = {"v": current_config["offset_V"], "u": "V"}
        if "t_offset_samples" in current_config:
            new_config["t_offset"] = {"v": current_config["t_offset_samples"], "u": "samples"}
        if "trigger_level" in current_config:
            new_config["trigger_level"] = current_config["trigger_level"]
        if "trigger_mode" in current_config:
            new_config["trigger_mode"] = current_config["trigger_mode"]
        if "samples_per_div" in current_config:
            new_config["samples_per_div"] = current_config["samples_per_div"]
        if "cfg_id" in current_config:
            new_config["cfg_id"] = current_config["cfg_id"]
        
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
    v_div_mv = config.get("v_div_mV", 200)
    offset_v = config.get("offset_V", 0.0)
    
    # Full scale is 8 divisions * v_div
    full_scale_mv = v_div_mv * 8.0
    center = 127.5
    
    voltages_mv = []
    for s in samples:
        # Convert ADC value to voltage in mV
        v_mv = ((s - center) / 256.0) * full_scale_mv + (offset_v * 1000)
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
                t_div_s = config.get("t_div_s", 0.005)
                samples_per_div = config.get("samples_per_div", 32)
                total_samples_per_div = samples_per_div  # Assuming 10 horizontal divs
                
                # Time per sample
                time_per_sample = t_div_s / total_samples_per_div
                
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
