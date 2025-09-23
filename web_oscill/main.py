from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import os

from .oscill_client import OscillClient
from .device_service import DeviceService

app = FastAPI(title="Oscill2 Web Prototype")

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
    return st

class ConfigReq(BaseModel):
    v_div_mV: Optional[int] = None
    t_div_s: Optional[float] = None
    offset_V: Optional[float] = None
    trigger_level: Optional[int] = None
    trigger_mode: Optional[int] = None

@app.post("/api/config")
def api_config(req: ConfigReq):
    if not service._client:
        raise HTTPException(status_code=400, detail="Not connected")
    try:
        status, warnings = service.apply_config({
            "v_div_mV": req.v_div_mV,
            "t_div_s": req.t_div_s,
            "offset_V": req.offset_V,
            "trigger_level": req.trigger_level,
            "trigger_mode": req.trigger_mode,
        })
        return {"status": "ok", **status, "warnings": warnings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/frames")
def api_frames(since: Optional[int] = None, limit: int = 64):
    try:
        if not service._client:
            return {"status": "disconnected", "frames": []}
        data = service.get_frames(since=since, limit=limit)
        return {"status": "ok", **data}
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
