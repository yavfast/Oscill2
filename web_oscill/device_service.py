import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

from .oscill_client import OscillClient


class DeviceService:
    """
    Centralized device access and frame buffering service.

    - Serializes ALL hardware access behind a single lock.
    - Runs a background acquisition loop that pulls frames and stores them
      with a timestamp and a snapshot of the active configuration.
    - Exposes synchronous methods for connect/disconnect, status, config updates,
      and buffered frame retrieval without touching the device from the web layer.
    """

    def __init__(self, buffer_size: int = 256):
        self._client: Optional[OscillClient] = None
        self._dev_lock = threading.RLock()
        self._frames: Deque[Dict[str, Any]] = deque(maxlen=max(8, buffer_size))
        self._frames_lock = threading.Lock()
        self._seq: int = 0
        self._acq_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ---------------- Device lifecycle ----------------
    def connect(self, port: Optional[str] = None, baud: int = 115200) -> Dict[str, Any]:
        with self._dev_lock:
            # Close any existing connection
            self._stop_acquisition_locked()
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            # Auto-detect if requested
            if not port or port == "auto":
                port = OscillClient.auto_find_port()
                if not port:
                    raise RuntimeError("Device not found")
            cli = OscillClient(port, baud)
            cli.open()
            cli.reset()
            cli.connect()

            # Set CPU frequency to 70 MHz
            cli.set_cpu_freq_mhz(70)

            # Set processing mode: Realtime, Post-processing, Sync buffer
            cli.set_rs_mode(0x00)

            # Initial defaults similar to Android MainActivity.onOscillConnected
            # Processing/data path defaults where available
            # RS: realtime (0), post-processing/normal via M1 (not explicitly modeled here)
            # TD (delay) = 0
            cli.set_scan_delay(0)
            # TA/TW (max wait for auto/wait) = 500 (units 12*MC per docs)
            cli.set_max_sync_wait_auto(500)
            cli.set_max_sync_wait_on_trig(500)
            # AP/AR (averaging/ris passes) = 0
            cli.set_avg_passes(0)
            cli.set_min_ris_passes(0)
            # Channel HW: enable, DC mode, filters off (O1 bits are device-specific; skip if unknown)
            cli.set_channel_hw_mode(0x00)  # O1: Channel ON, DC input
            # SW Mode normal (M1 = 4)
            cli.set_channel_sw_mode(0x04) # M1: Normal mode
            # Sensitivity 200 mV/div and offset 0 V
            cli.set_v_div_mV(200)
            cli.set_offset_volts(0.0)
            # Trigger mode: front with hysteresis on front; level 128; type AUTO
            # T1 bit composition is device-specific; reuse Android defaults: 0x2C
            cli.set_trigger_mode(0x2C)
            cli.set_trigger_level(128)
            # Samples per div and total QS; choose 10 divs * min(64, QSh/10)
            # Ensure QS sane
            cli.ensure_qs()
            # Timebase 5 ms/div
            cli.set_time_div_s(0.005)
            # Sample offset (TC) center 0 and samples offset P (SamplesOffset) equivalent → use TC=0
            cli.set_samples_offset(0)
            # Calibrate at the end
            cli.calibrate()
            self._client = cli
            # Start acquisition
            self._start_acquisition_locked()
            return {"status": "ok", "port": port, **self._safe_status_locked()}

    def disconnect(self) -> Dict[str, Any]:
        with self._dev_lock:
            self._stop_acquisition_locked()
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            self._client = None
        with self._frames_lock:
            self._frames.clear()
            self._seq = 0
        return {"status": "ok"}

    # ---------------- Public API (synchronous) ----------------
    def get_status(self) -> Dict[str, Any]:
        with self._dev_lock:
            if not self._client:
                # Try to autoconnect silently
                try:
                    port = OscillClient.auto_find_port()
                    if port:
                        self.connect(port)
                except Exception:
                    pass
            if not self._client:
                return {"status": "disconnected"}
            try:
                return {"status": "ok", **self._client.get_current_status()}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def apply_config(self, changes: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Apply requested config atomically and return new status plus warnings.

        changes keys may include: v_div_mV, t_div_s, offset_V, trigger_level, trigger_mode.
        """
        warnings: List[str] = []
        with self._dev_lock:
            if not self._client:
                raise RuntimeError("Not connected")
            c = self._client
            try:
                if changes.get("v_div_mV") is not None:
                    c.set_v_div_mV(int(changes["v_div_mV"]))
            except Exception as e:
                warnings.append(f"set v_div_mV failed: {e}")
            try:
                if changes.get("offset_V") is not None:
                    c.set_offset_volts(float(changes["offset_V"]))
            except Exception as e:
                warnings.append(f"set offset_V failed: {e}")
            try:
                if changes.get("t_div_s") is not None:
                    c.set_time_div_s(float(changes["t_div_s"]))
            except Exception as e:
                warnings.append(f"set t_div_s failed: {e}")
            try:
                if changes.get("trigger_level") is not None:
                    c.set_trigger_level(int(changes["trigger_level"]))
            except Exception as e:
                warnings.append(f"set trigger_level failed: {e}")
            try:
                if changes.get("trigger_mode") is not None:
                    c.set_trigger_mode(int(changes["trigger_mode"]))
            except Exception as e:
                warnings.append(f"set trigger_mode failed: {e}")
            try:
                c.ensure_qs()
            except Exception as e:
                warnings.append(f"ensure_qs failed: {e}")
            try:
                status = c.get_current_status()
            except Exception as e:
                warnings.append(f"get_current_status failed: {e}")
                status = {}
        return status, warnings

    def get_latest_frame(self) -> Optional[Dict[str, Any]]:
        with self._frames_lock:
            if not self._frames:
                return None
            return dict(self._frames[-1])

    def get_frames(self, since: Optional[int] = None, limit: int = 64) -> Dict[str, Any]:
        with self._frames_lock:
            items: List[Dict[str, Any]] = []
            oldest_seq = self._frames[0]["seq"] if self._frames else 0
            newest_seq = self._frames[-1]["seq"] if self._frames else 0
            start_idx = 0
            if since is not None and self._frames:
                # Find first frame with seq > since
                for i, fr in enumerate(self._frames):
                    if fr["seq"] > since:
                        start_idx = i
                        break
                else:
                    start_idx = len(self._frames)
            for fr in list(self._frames)[start_idx:start_idx + max(1, limit)]:
                items.append(dict(fr))
            return {
                "frames": items,
                "oldest_seq": oldest_seq,
                "newest_seq": newest_seq,
                "buffer_size": self._frames.maxlen or 0,
            }

    # ---------------- Internals ----------------
    def _start_acquisition_locked(self):
        if self._acq_thread and self._acq_thread.is_alive():
            return
        self._stop_event.clear()
        self._acq_thread = threading.Thread(target=self._acq_loop, name="device-acq", daemon=True)
        self._acq_thread.start()

    def _stop_acquisition_locked(self):
        self._stop_event.set()
        t = self._acq_thread
        if t and t.is_alive():
            try:
                t.join(timeout=1.5)
            except Exception:
                pass
        self._acq_thread = None

    def _safe_status_locked(self) -> Dict[str, Any]:
        try:
            if self._client:
                return self._client.get_current_status()
        except Exception:
            pass
        return {}

    def _snapshot_config_locked(self) -> Dict[str, Any]:
        """Best-effort single snapshot of config under device lock."""
        cfg: Dict[str, Any] = {}
        c = self._client
        if not c:
            return cfg
        try:
            cfg["v_div_mV"] = c.get_v_div_mV()
        except Exception:
            cfg["v_div_mV"] = None
        try:
            cfg["t_div_s"] = c.get_time_div_s()
        except Exception:
            cfg["t_div_s"] = None
        try:
            cfg["offset_V"] = c.get_offset_volts()
        except Exception:
            cfg["offset_V"] = None
        try:
            cfg["trigger_level"] = c.get_trigger_level()
        except Exception:
            cfg["trigger_level"] = None
        try:
            cfg["trigger_mode"] = c.get_trigger_mode()
        except Exception:
            cfg["trigger_mode"] = None
        try:
            cfg["rs_mode"] = c.get_rs_mode()
        except Exception:
            cfg["rs_mode"] = None
        # Time offset (TC, samples) and optional delay (TD)
        try:
            cfg["t_offset_samples"] = c.get_reg_2('TC', signed=False)
        except Exception:
            cfg["t_offset_samples"] = 0
        try:
            cfg["t_delay"] = c.get_reg_4('TD', signed=False)
        except Exception:
            cfg["t_delay"] = 0
        # Static geometry info for UI
        try:
            cfg["samples_per_div"] = getattr(c, 'SAMPLES_PER_DIV', 32)
        except Exception:
            cfg["samples_per_div"] = 32
        return cfg

    def _record_frame(self, payload: Dict[str, Any]):
        with self._frames_lock:
            self._seq += 1
            payload["seq"] = self._seq
            self._frames.append(payload)

    def _acq_loop(self):
        # Soft loop with opportunistic device access
        backoff_s = 0.02
        while not self._stop_event.is_set():
            # Try to acquire device without blocking for too long
            got = self._dev_lock.acquire(timeout=0.1)
            if not got:
                time.sleep(backoff_s)
                continue
            try:
                if not self._client:
                    time.sleep(backoff_s)
                    continue
                # Acquire one frame from device
                fr = self._client.get_frame()
                if not fr or not fr.get("samples"):
                    time.sleep(backoff_s)
                    continue
                # Snapshot config while holding the lock to keep it consistent
                cfg = self._snapshot_config_locked()
                # Timestamp
                ts = time.time()
                iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts)) + f".{int((ts%1)*1000):03d}Z"
                # Store compact payload; keep raw samples only
                payload = {
                    "time": ts,
                    "time_iso": iso,
                    "config": cfg,
                    "channels": fr.get("channels", 1),
                    "samples": fr.get("samples", []),
                }
                self._record_frame(payload)
            except Exception:
                # Swallow and keep trying
                time.sleep(backoff_s)
            finally:
                try:
                    self._dev_lock.release()
                except RuntimeError:
                    pass
            # Pace the loop lightly to avoid hogging CPU/USB
            time.sleep(backoff_s)
