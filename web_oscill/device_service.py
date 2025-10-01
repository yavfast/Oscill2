import threading
import logging
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

import sys
import os
sys.path.append(os.path.dirname(__file__))

from oscill_client import OscillClient
from converters import convert


SW_MODE_BITS = {
    "AVG": 0x00,
    "AVG_HIRES": 0x01,
    "PEAK": 0x02,
    "PEAK_HI": 0x03,
    "NORMAL": 0x04,
}

SW_MODE_LABEL_BY_VALUE = {value: key for key, value in SW_MODE_BITS.items()}

SYNC_TYPE_BITS = {
    "AUTO": 0x00,
    "WAIT_TIMEOUT": 0x01,
    "FREE": 0x02,
    "WAIT": 0x03,
}

SYNC_TYPE_LABEL_BY_VALUE = {value: key for key, value in SYNC_TYPE_BITS.items()}


def _normalize_key(value: Any) -> str:
    return str(value).strip().replace('-', '_').replace(' ', '_').upper()


def _set_bits(value: int, mask: int, enabled: bool) -> int:
    if enabled:
        return value | mask
    return value & ~mask


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
        # Basic logging setup (safe to call multiple times)
        logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')
        self._log = logging.getLogger(self.__class__.__name__)
        self._client: Optional[OscillClient] = None
        self._dev_lock = threading.RLock()
        self._frames: Deque[Dict[str, Any]] = deque(maxlen=max(8, buffer_size))
        self._frames_lock = threading.Lock()
        self._seq: int = 0
        self._acq_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._cfg_id: int = 0  # Configuration ID for tracking config changes
        self._is_connected = False
        self._is_acquiring = False

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
            # Sensitivity 200 mV/div and center offset
            cli.set_v_div_mV(200)
            cli.set_offset_raw(128)
            # Trigger mode: front with hysteresis on front; level 128; type AUTO
            # T1 bit composition is device-specific; reuse Android defaults: 0x2C
            cli.set_trigger_mode(0x2C)
            cli.set_trigger_level(128)
            # Samples per div and total QS; choose 10 divs * min(64, QSh/10)
            # Ensure QS sane
            total_samples = cli.ensure_qs()
            # Timebase 5 ms/div
            cli.set_time_div_ms(5)
            # Center the sweep offset so the trigger is in the middle of the displayed window.
            center_offset = total_samples // 2 if isinstance(total_samples, int) and total_samples > 0 else 0
            center_offset = max(0, min(0xFFFF, center_offset))
            cli.set_samples_offset(center_offset)
            # Calibrate at the end
            cli.calibrate()
            self._client = cli
            self._is_connected = True
            # Start acquisition automatically after successful connection
            self._start_acquisition_locked()
            self._is_acquiring = True
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
            self._is_connected = False
            self._is_acquiring = False
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
                return {"status": "disconnected", "is_connected": False, "is_acquiring": False}
            try:
                config = self._snapshot_config_locked()
                return {"status": "ok", "config": config, "cfg_id": self._cfg_id, "is_connected": self._is_connected, "is_acquiring": self._is_acquiring}
            except Exception as e:
                return {"status": "error", "message": str(e), "is_connected": self._is_connected, "is_acquiring": self._is_acquiring}

    def apply_config(self, changes: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Apply requested config atomically and return new status plus warnings.

                Supported keys include:
                    - v_div, t_div: structured {v, u} values for vertical/time divisions
                    - v_offset, t_offset: raw 0..255 offsets
                    - trigger_level: integer 0..255
                    - trigger_mode: legacy raw register value (optional)
                    - trigger_slope: "rising", "falling", "both", "none"
                    - coupling: "DC", "AC", "GND"
                    - filter_high, filter_low: booleans for hardware filters
                    - sw_mode: processing mode ("normal", "avg", "avg_hires", "peak", ...)
                    - sync_type: acquisition sync type ("auto", "wait_timeout", "free", "wait")
                    - sync_front, sync_back: booleans enabling trigger edges
        """
        warnings: List[str] = []
        with self._dev_lock:
            if not self._client:
                raise RuntimeError("Not connected")
            c = self._client
            try:
                if changes.get("v_div") is not None:
                    v_div = changes["v_div"]
                    value_mv = int(convert(v_div["v"], v_div["u"], "mV"))
                    c.set_v_div_mV(value_mv)
                if changes.get("v_offset") is not None:
                    v_offset_raw = changes["v_offset"]
                    if isinstance(v_offset_raw, dict):
                        v_offset_raw = v_offset_raw.get("v")
                    if v_offset_raw is None:
                        raise ValueError("v_offset requires a value")
                    raw_value = max(0, min(0xFF, int(float(v_offset_raw))))
                    self._log.info(f"Applying raw v_offset request: {raw_value}")
                    c.set_offset_raw(raw_value)
                if changes.get("t_div") is not None:
                    t_div = changes["t_div"]
                    value_ms = float(convert(t_div["v"], t_div["u"], "ms"))
                    c.set_time_div_ms(value_ms)
                if changes.get("t_offset") is not None:
                    t_offset_raw = changes["t_offset"]
                    if isinstance(t_offset_raw, dict):
                        unit = t_offset_raw.get("u")
                        if unit and unit != "samples":
                            raise ValueError(f"Unsupported unit for t_offset: {unit}")
                        t_offset_raw = t_offset_raw.get("v")
                    if t_offset_raw is None:
                        raise ValueError("t_offset requires a value")
                    raw_samples = max(0, min(0xFF, int(float(t_offset_raw))))
                    c.set_samples_offset(raw_samples)
                if changes.get("trigger_level") is not None:
                    c.set_trigger_level(int(changes["trigger_level"]))
                hw_mode_value: Optional[int] = None
                if any(key in changes for key in ("coupling", "filter_high", "filter_low")):
                    hw_mode_value = c.get_channel_hw_mode()
                    coupling_value = changes.get("coupling")
                    if coupling_value is not None:
                        coupling_key = _normalize_key(coupling_value)
                        if coupling_key == "GND":
                            hw_mode_value = _set_bits(hw_mode_value, 0x01, True)
                            hw_mode_value = _set_bits(hw_mode_value, 0x02, False)
                        elif coupling_key == "AC":
                            hw_mode_value = _set_bits(hw_mode_value, 0x01, False)
                            hw_mode_value = _set_bits(hw_mode_value, 0x02, True)
                        else:  # DC fallback
                            hw_mode_value = _set_bits(hw_mode_value, 0x01, False)
                            hw_mode_value = _set_bits(hw_mode_value, 0x02, False)
                    if "filter_high" in changes and changes["filter_high"] is not None:
                        hw_mode_value = _set_bits(hw_mode_value, 0x04, bool(changes["filter_high"]))
                    if "filter_low" in changes and changes["filter_low"] is not None:
                        hw_mode_value = _set_bits(hw_mode_value, 0x08, bool(changes["filter_low"]))
                    c.set_channel_hw_mode(hw_mode_value)
                if changes.get("sw_mode") is not None:
                    sw_key = _normalize_key(changes["sw_mode"])
                    sw_bits = SW_MODE_BITS.get(sw_key)
                    if sw_bits is not None:
                        c.set_channel_sw_mode(sw_bits)
                    else:
                        warnings.append(f"Unsupported sw_mode '{changes['sw_mode']}'")
                t1_bits: Optional[int] = None
                t1_modified = False
                if changes.get("trigger_mode") is not None:
                    tm_value = changes["trigger_mode"]
                    parsed_value: Optional[int] = None
                    if isinstance(tm_value, str):
                        mode_map = {"AUTO": 0x2C, "NORMAL": 0x2D, "SINGLE": 0x2E}
                        parsed_value = mode_map.get(_normalize_key(tm_value))
                        if parsed_value is None:
                            try:
                                parsed_value = int(tm_value, 0)
                            except ValueError:
                                warnings.append(f"Invalid trigger_mode value '{tm_value}'")
                    else:
                        parsed_value = int(tm_value)
                    if parsed_value is not None:
                        t1_bits = parsed_value
                        t1_modified = True
                if changes.get("trigger_slope") is not None:
                    if t1_bits is None:
                        t1_bits = c.get_trigger_mode()
                    slope_key = _normalize_key(changes["trigger_slope"])
                    if slope_key in ("RISING", "RISE"):
                        t1_bits = _set_bits(t1_bits, 1 << 5, True)
                        t1_bits = _set_bits(t1_bits, (1 << 2) | (1 << 3), True)
                        t1_bits = _set_bits(t1_bits, 1 << 4, False)
                        t1_bits = _set_bits(t1_bits, (1 << 0) | (1 << 1), False)
                        t1_modified = True
                    elif slope_key in ("FALLING", "FALL"):
                        t1_bits = _set_bits(t1_bits, 1 << 4, True)
                        t1_bits = _set_bits(t1_bits, (1 << 0) | (1 << 1), True)
                        t1_bits = _set_bits(t1_bits, 1 << 5, False)
                        t1_bits = _set_bits(t1_bits, (1 << 2) | (1 << 3), False)
                        t1_modified = True
                    elif slope_key in ("BOTH", "RISE_FALL"):
                        t1_bits = _set_bits(t1_bits, 1 << 5, True)
                        t1_bits = _set_bits(t1_bits, (1 << 2) | (1 << 3), True)
                        t1_bits = _set_bits(t1_bits, 1 << 4, True)
                        t1_bits = _set_bits(t1_bits, (1 << 0) | (1 << 1), True)
                        t1_modified = True
                    elif slope_key in ("NONE",):
                        t1_bits = _set_bits(t1_bits, 1 << 5, False)
                        t1_bits = _set_bits(t1_bits, (1 << 2) | (1 << 3), False)
                        t1_bits = _set_bits(t1_bits, 1 << 4, False)
                        t1_bits = _set_bits(t1_bits, (1 << 0) | (1 << 1), False)
                        t1_modified = True
                    else:
                        warnings.append(f"Unsupported trigger_slope '{changes['trigger_slope']}'")
                if any(key in changes for key in ("sync_front", "sync_back")):
                    if t1_bits is None:
                        t1_bits = c.get_trigger_mode()
                    if "sync_front" in changes and changes["sync_front"] is not None:
                        front_enabled = bool(changes["sync_front"])
                        t1_bits = _set_bits(t1_bits, 1 << 5, front_enabled)
                        t1_bits = _set_bits(t1_bits, (1 << 2) | (1 << 3), front_enabled)
                        t1_modified = True
                    if "sync_back" in changes and changes["sync_back"] is not None:
                        back_enabled = bool(changes["sync_back"])
                        t1_bits = _set_bits(t1_bits, 1 << 4, back_enabled)
                        t1_bits = _set_bits(t1_bits, (1 << 0) | (1 << 1), back_enabled)
                        t1_modified = True
                if t1_modified and t1_bits is not None:
                    c.set_trigger_mode(t1_bits)
                if changes.get("sync_type") is not None:
                    sync_key = _normalize_key(changes["sync_type"])
                    sync_bits = SYNC_TYPE_BITS.get(sync_key)
                    if sync_bits is not None:
                        c.set_sync_type(sync_bits)
                    else:
                        warnings.append(f"Unsupported sync_type '{changes['sync_type']}'")
                c.ensure_qs()
                # Increment config ID on any config change
                self._cfg_id += 1
                status = {"config": self._snapshot_config_locked(), "cfg_id": self._cfg_id}
            except Exception as e:
                warnings.append(f"config update failed: {e}")
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
                fr_copy = dict(fr)
                fr_copy.pop("config", None)
                items.append(fr_copy)
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
            v_div_mv = c.get_v_div_mV()
            cfg["v_div"] = {"v": v_div_mv, "u": "mV"}
        except Exception:
            cfg["v_div"] = {"v": 200, "u": "mV"}  # Default
        try:
            t_div_ms = c.get_time_div_ms()
            cfg["t_div"] = {"v": round(t_div_ms, 6), "u": "ms"}
        except Exception:
            cfg["t_div"] = {"v": 5, "u": "ms"}  # Default
        try:
            cfg["v_offset"] = c.get_offset_raw()
        except Exception:
            cfg["v_offset"] = 128
        try:
            cfg["trigger_level"] = c.get_trigger_level()
        except Exception:
            cfg["trigger_level"] = 128
        try:
            cfg["trigger_mode_bits"] = c.get_trigger_mode()
        except Exception:
            cfg["trigger_mode_bits"] = 0x2C
        cfg["trigger_mode"] = {"v": cfg["trigger_mode_bits"], "u": "bits"}
        try:
            cfg["rs_mode"] = c.get_rs_mode()
        except Exception:
            cfg["rs_mode"] = 0x00
        # Time offset (TC, samples) and optional delay (TD)
        try:
            cfg["t_offset"] = c.get_reg_2('TC', signed=False)
        except Exception:
            cfg["t_offset"] = 0
        try:
            cfg["t_delay"] = c.get_reg_4('TD', signed=False)
        except Exception:
            cfg["t_delay"] = 0
        try:
            total_samples = c.get_reg_2('QS', signed=False)
        except Exception:
            samples_per_div = cfg.get("samples_per_div", 32)
            horiz_divs = getattr(c, 'H_DIVS', 10)
            total_samples = samples_per_div * horiz_divs
        cfg["samples_total"] = max(0, int(total_samples))
        # Static geometry info for UI
        try:
            cfg["samples_per_div"] = getattr(c, 'SAMPLES_PER_DIV', 32)
        except Exception:
            cfg["samples_per_div"] = 32
        # Channel hardware/software modes and sync metadata
        try:
            o1 = c.get_channel_hw_mode()
            channel_enabled = (o1 & 0x01) == 0
            high_filter = bool(o1 & 0x04)
            low_filter = bool(o1 & 0x08)
            if o1 & 0x01:
                coupling = "GND"
            elif o1 & 0x02:
                coupling = "AC"
            else:
                coupling = "DC"
            cfg["channel_enabled"] = channel_enabled
            cfg["coupling"] = coupling
            cfg["filters"] = {"high": high_filter, "low": low_filter}
            cfg["hw_mode_bits"] = o1
        except Exception:
            cfg.setdefault("coupling", "DC")
            cfg.setdefault("filters", {"high": False, "low": False})
            cfg.setdefault("channel_enabled", True)
        try:
            sw_bits = c.get_channel_sw_mode() & 0x07
            cfg["sw_mode"] = SW_MODE_LABEL_BY_VALUE.get(sw_bits, "NORMAL")
            cfg["sw_mode_bits"] = sw_bits
        except Exception:
            cfg.setdefault("sw_mode", "NORMAL")
        try:
            sync_bits = c.get_sync_type() & 0x03
            cfg["sync_type"] = SYNC_TYPE_LABEL_BY_VALUE.get(sync_bits, "AUTO")
            cfg["sync_type_bits"] = sync_bits
        except Exception:
            cfg.setdefault("sync_type", "AUTO")
        try:
            t1 = cfg.get("trigger_mode_bits", c.get_trigger_mode())
            front_enabled = bool(t1 & (1 << 5))
            back_enabled = bool(t1 & (1 << 4))
            cfg["sync_front"] = front_enabled
            cfg["sync_back"] = back_enabled
            cfg["sync_hist_front"] = bool((t1 & (1 << 2)) and (t1 & (1 << 3)))
            cfg["sync_hist_back"] = bool((t1 & (1 << 0)) and (t1 & (1 << 1)))
            if front_enabled and not back_enabled:
                cfg["trigger_slope"] = "Rising"
            elif back_enabled and not front_enabled:
                cfg["trigger_slope"] = "Falling"
            elif front_enabled and back_enabled:
                cfg["trigger_slope"] = "Both"
            else:
                cfg["trigger_slope"] = "None"
        except Exception:
            cfg.setdefault("trigger_slope", "Rising")
        cfg["cfg_id"] = self._cfg_id  # Add config ID
        return cfg

    def _record_frame(self, payload: Dict[str, Any]):
        with self._frames_lock:
            self._seq += 1
            payload["seq"] = self._seq
            self._frames.append(payload)

    def _acq_loop(self):
        # Soft loop with opportunistic device access
        backoff_s = 0.005  # Reduced from 0.02 to 0.005 (5ms) for lower latency
        consecutive_errors = 0
        max_consecutive_errors = 5  # Disconnect if 5 consecutive errors
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
                # Timestamp
                ts = time.time()
                # Snapshot config while holding the lock to keep it consistent
                cfg = self._snapshot_config_locked()
                # Store compact payload; keep raw samples only
                payload = {
                    "time": ts,
                    "cfg_id": cfg.get("cfg_id"),
                    "channels": fr.get("channels", 1),
                    "samples": fr.get("samples", []),
                    "sample_bits": fr.get("sample_bits", 8),
                    "sample_bytes": fr.get("sample_bytes", 1),
                    "sample_components": fr.get("sample_components", 1),
                    "sample_format": fr.get("sample_format"),
                    "sample_format_label": fr.get("sample_format_label"),
                    "channel_attrs": fr.get("channel_attrs"),
                    "frame_attrs": fr.get("frame_attrs"),
                }
                if "samples_peak_min" in fr:
                    payload["samples_peak_min"] = fr.get("samples_peak_min")
                if "samples_peak_max" in fr:
                    payload["samples_peak_max"] = fr.get("samples_peak_max")
                self._record_frame(payload)
                consecutive_errors = 0  # Reset on success
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    self._log.warning(f"Device appears disconnected after {consecutive_errors} consecutive errors, disconnecting")
                    try:
                        self.disconnect()
                    except Exception:
                        pass
                    break
                # Swallow and keep trying
                time.sleep(backoff_s)
            finally:
                try:
                    self._dev_lock.release()
                except RuntimeError:
                    pass
            # Pace the loop lightly to avoid hogging CPU/USB
            time.sleep(backoff_s)

    def start_acquisition(self) -> Dict[str, Any]:
        with self._dev_lock:
            if not self._client:
                raise RuntimeError("Not connected")
            self._start_acquisition_locked()
            self._is_acquiring = True
            return {"status": "ok"}

    def stop_acquisition(self) -> Dict[str, Any]:
        with self._dev_lock:
            self._stop_acquisition_locked()
            self._is_acquiring = False
            return {"status": "ok"}
