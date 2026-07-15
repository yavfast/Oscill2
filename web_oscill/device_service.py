import threading
import logging
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

import sys
import os
sys.path.append(os.path.dirname(__file__))

from oscill_client import OscillClient, VDIV_VALUES_MV, TDIV_VALUES_MS
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
        # Cached configuration to avoid querying device on every status request
        self._cached_config: Dict[str, Any] = {}
        self._config_lock = threading.Lock()
        # [task_scope-zero-offset] Actual sample count the device last delivered.
        # The device returns fewer samples than QS (empirically QS-2 in AVG/NORMAL),
        # so QS (samples_total) and TC (t_offset) — both in device sample-space —
        # must be reconciled to this delivered-space before the client plots them.
        # Plain int assignment is atomic under the GIL; no dedicated lock needed.
        self._last_delivered_len: Optional[int] = None
        # Single-threaded executor for serializing all device commands with timeout
        self._device_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="device-cmd")
        self._device_timeout = 5.0  # 5 seconds timeout for device operations

    # ---------------- Device lifecycle ----------------
    def _connect_internal(self, port: Optional[str], baud: int) -> Dict[str, Any]:
        """Internal connect method that runs in executor."""
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
            # [task_qs-raise] Open + OBEX handshake at the base baud (device starts a
            # session at low speed); rescues a device left at a raised baud by a prior
            # ungraceful session. Speed is raised only AFTER init (below).
            cli.open_and_handshake()

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
            # [task_qs-raise] Derive the sampling density from the device's QSh ceiling
            # for the mode just set (M1=Normal above), then size QS to it. QSh is
            # mode-dependent, so this must run after set_channel_sw_mode.
            cli.refresh_samples_per_div()
            total_samples = cli.ensure_qs()
            # Timebase 5 ms/div (computed at the new density)
            cli.set_time_div_ms(5)
            # Center the sweep offset so the trigger is in the middle of the displayed window.
            center_offset = total_samples // 2 if isinstance(total_samples, int) and total_samples > 0 else 0
            center_offset = max(0, min(0xFFFF, center_offset))
            cli.set_samples_offset(center_offset)
            # Calibrate at the end
            cli.calibrate()
            # [task_qs-raise] Init/handshake/calibrate all done at the base baud; now raise
            # the serial link so the larger mode-aware frames (QS up to ~1784) transfer fast
            # (~155 ms → ~19 ms at 921600). Best-effort: falls back to 115200 on any failure.
            # On by default (verified stable @921600); set OSCILL_HIGH_BAUD=0 to opt out
            # (e.g. a flaky cable/adapter that can't sustain the higher rate).
            if os.environ.get("OSCILL_HIGH_BAUD", "1") != "0":
                achieved_baud = cli.raise_speed()
                self._log.info(f"Serial link running at {achieved_baud} baud")
            self._client = cli
            self._is_connected = True
            # Start acquisition automatically after successful connection
            self._start_acquisition_locked()
            self._is_acquiring = True
            # Snapshot config after connect
            cfg = self._snapshot_config_locked()
            return {"status": "ok", "port": port, "config": cfg, "cfg_id": self._cfg_id, "is_connected": self._is_connected, "is_acquiring": self._is_acquiring}

    def connect(self, port: Optional[str] = None, baud: int = 115200) -> Dict[str, Any]:
        """Connect to device via executor with timeout."""
        try:
            future = self._device_executor.submit(self._connect_internal, port, baud)
            return future.result(timeout=self._device_timeout)
        except FutureTimeoutError:
            raise TimeoutError(f"Connection timed out after {self._device_timeout}s")
        except Exception as e:
            self._log.error(f"Connect failed: {e}")
            raise

    def _disconnect_internal(self) -> Dict[str, Any]:
        """Internal disconnect method that runs in executor."""
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
        # [task_scope-zero-offset] Reset delivered-length so a reconnect never
        # reconciles against a stale count before its first frame arrives.
        self._last_delivered_len = None
        # Clear cached config
        self._update_cached_config({})
        return {"status": "ok"}

    def disconnect(self) -> Dict[str, Any]:
        """Disconnect from device via executor with timeout."""
        try:
            future = self._device_executor.submit(self._disconnect_internal)
            return future.result(timeout=self._device_timeout)
        except FutureTimeoutError:
            raise TimeoutError(f"Disconnect timed out after {self._device_timeout}s")
        except Exception as e:
            self._log.error(f"Disconnect failed: {e}")
            raise

    # ---------------- Public API (synchronous) ----------------
    def ensure_connected(self, port: Optional[str] = None, baud: int = 115200) -> Dict[str, Any]:
        """
        Ensure device is connected. If not connected, attempt to connect.
        If already connected, return current status.
        
        Args:
            port: Port to connect to (None for auto-detect)
            baud: Baud rate (default: 115200)
            
        Returns:
            Status dict with connection info
        """
        if self._is_connected and self._client:
            return self.get_status()
        
        # Not connected, attempt connection
        try:
            return self.connect(port, baud)
        except Exception as e:
            self._log.warning(f"Auto-connect failed: {e}")
            return {"status": "disconnected", "is_connected": False, "is_acquiring": False, "error": str(e)}

    def is_connected(self) -> bool:
        """Public accessor: True if a device is connected.

        [PL_AUDIT_WEB_01] The web layer must use this instead of reaching into
        the private ``_client`` handle (rule HardwareAccessOnlyThroughDeviceService).
        """
        return bool(self._is_connected and self._client)

    def is_acquiring(self) -> bool:
        """Public accessor: True if the background acquisition loop is running."""
        return bool(self._is_acquiring)

    def display_geometry(self) -> Dict[str, int]:
        """Display grid geometry (single source of truth for the frontend).

        [PL_AUDIT_WEB_06] Exposes the device's horizontal-division count and
        samples-per-division so the web layer need not import OscillClient directly
        (rule HardwareAccessOnlyThroughDeviceService) nor hardcode its own copy.
        [task_qs-raise] samples_per_div is now the live per-connection density (derived
        from QSh per mode); falls back to the class default when disconnected.
        """
        spd = getattr(self._client, "samples_per_div", OscillClient.SAMPLES_PER_DIV) \
            if self._client else OscillClient.SAMPLES_PER_DIV
        return {
            "h_divs": OscillClient.H_DIVS,
            "samples_per_div": int(spd),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get status from cached configuration without querying device."""
        if not self._is_connected or not self._client:
            return {"status": "disconnected", "is_connected": False, "is_acquiring": False}
        
        # Return cached config instead of querying device, reconciled from the
        # device sample-space (QS/TC) to the delivered sample-space the client plots.
        config = self._reconcile_display_geometry(self._get_cached_config())
        return {
            "status": "ok", 
            "config": config, 
            "cfg_id": self._cfg_id, 
            "is_connected": self._is_connected, 
            "is_acquiring": self._is_acquiring
        }

    def _apply_config_internal(self, changes: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Internal apply config method that runs in executor.
        
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
                # [task_config-limits] Cached config carries the parameter limits;
                # apply_config silently clamps incoming values to them before writing.
                cached = self._get_cached_config()
                limits = cached.get("limits") or {}
                if changes.get("v_div") is not None:
                    v_div = changes["v_div"]
                    value_mv = int(convert(v_div["v"], v_div["u"], "mV"))
                    vlim = limits.get("v_div")
                    if isinstance(vlim, dict) and vlim.get("values"):
                        vals = vlim["values"]
                        value_mv = max(int(min(vals)), min(int(max(vals)), value_mv))
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
                    tlim = limits.get("t_div")
                    if isinstance(tlim, dict) and tlim.get("values"):
                        vals = tlim["values"]
                        value_ms = max(float(min(vals)), min(float(max(vals)), value_ms))
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
                    # [task_scope-zero-offset] Incoming t_offset is in delivered
                    # sample-space (see _reconcile_display_geometry). Convert back to
                    # the device TC register — exact inverse of the read-side reconcile:
                    #   TC = delivered_index + (QS - delivered) + 1
                    # so the marker-drag round-trips. No frame yet → treat as raw TC.
                    delivered_index = max(0, int(float(t_offset_raw)))
                    qs = cached.get("samples_total")
                    delivered = self._last_delivered_len
                    if isinstance(qs, int) and delivered and delivered <= qs:
                        tc = delivered_index + (qs - delivered) + 1
                    else:
                        tc = delivered_index
                    # TC is a 2-byte register (bounded by TCh on-device); clamp to
                    # 0xFFFF, not 0xFF — a 0xFF cap collapses the rightmost delivered
                    # index (253→252) and contradicts the advertised t_offset limit.
                    c.set_samples_offset(max(0, min(0xFFFF, tc)))
                if changes.get("trigger_level") is not None:
                    tl = int(changes["trigger_level"])
                    tllim = limits.get("trigger_level")
                    if isinstance(tllim, dict) and "min" in tllim and "max" in tllim:
                        tl = max(int(tllim["min"]), min(int(tllim["max"]), tl))
                    c.set_trigger_level(tl)
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
                # [task_qs-raise] A mode change alters QSh and thus the optimal sampling
                # density. Recompute it only when sw_mode changed (QSh is flat over t/div,
                # verified live). Density scales time-per-sample, so re-apply the current
                # t/div to preserve the timebase; QS = density × H_DIVS then changes, so
                # rescale the sweep offset (TC) proportionally to the resized window — else
                # a centered TC can exceed a shrunk hi-res QS (888) or drift in 8-bit (1784).
                # Runs after the sw_mode register write above.
                density_changed = False
                old_spd = c.samples_per_div
                if "sw_mode" in changes:
                    t_div_now = c.get_time_div_ms()  # at OLD density, before refresh
                    if c.refresh_samples_per_div() != old_spd:
                        density_changed = True
                        c.set_time_div_ms(t_div_now)  # recompute TS → same t/div at new density
                c.ensure_qs()
                if density_changed and old_spd:
                    try:
                        new_qs = c.samples_per_div * c.H_DIVS
                        old_tc = c.get_reg_2('TC', signed=False)
                        new_tc = int(round(old_tc * c.samples_per_div / old_spd))
                        c.set_samples_offset(max(0, min(new_qs - 1, new_tc)))
                    except Exception:
                        pass
                # [task_qs-raise] Any config change cleared the buffer, so the delivered
                # length is stale. Reset it BEFORE the snapshot below so the response
                # reconciles against the requested QS-space — critical when QS changed
                # across modes (e.g. AVG_HIRES 888 → NORMAL 1784). First frame re-establishes it.
                self._last_delivered_len = None
                # Increment config ID on any config change
                self._cfg_id += 1
                # Update cached config; return it reconciled to delivered-space so the
                # apply response matches /api/status and /api/frames (single geometry).
                cfg = self._snapshot_config_locked()
                # [SP_RES_02_01] Enhancement settings are backend-only (no register
                # write above): fold the requested enh_* onto the fresh snapshot,
                # silently clamped, and re-cache. cfg_id already bumped + buffer cleared
                # below, so an enh_*-only change resets the averaging window like any other.
                self._apply_enh_settings(cfg, changes)
                self._update_cached_config(cfg)
                status = {"config": self._reconcile_display_geometry(cfg), "cfg_id": self._cfg_id}
            except Exception as e:
                warnings.append(f"config update failed: {e}")
                status = {}
        
        # Clear frame buffer after config change - old frames are no longer valid
        # (_last_delivered_len was reset above, under the device lock, before the snapshot).
        with self._frames_lock:
            self._frames.clear()
            self._log.info(f"Cleared frame buffer after config change (cfg_id: {self._cfg_id})")
        
        return status, warnings

    def apply_config(self, changes: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """Apply config changes via executor with timeout."""
        if not self._client:
            raise RuntimeError("Not connected")
        try:
            future = self._device_executor.submit(self._apply_config_internal, changes)
            return future.result(timeout=self._device_timeout)
        except FutureTimeoutError:
            raise TimeoutError(f"Config update timed out after {self._device_timeout}s")
        except Exception as e:
            self._log.error(f"Config update failed: {e}")
            raise

    def get_latest_frame(self) -> Optional[Dict[str, Any]]:
        with self._frames_lock:
            if not self._frames:
                return None
            return dict(self._frames[-1])

    def ensure_frame_available(self, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Ensure a frame with samples is available, starting acquisition if needed.
        
        Args:
            timeout: Maximum time to wait for a frame in seconds
            
        Returns:
            Frame data or None if timeout/no frame available
        """
        # First check if we already have a frame
        frame = self.get_latest_frame()
        if frame and frame.get('samples'):
            return frame
        
        # No frame available, check if acquisition is running
        was_acquiring = self._is_acquiring
        
        if not was_acquiring:
            # Start acquisition temporarily
            self.start()
        
        try:
            # Wait for frame to arrive
            start_time = time.time()
            while (time.time() - start_time) < timeout:
                frame = self.get_latest_frame()
                if frame and frame.get('samples'):
                    return frame
                time.sleep(0.05)  # Check every 50ms
            return None
        finally:
            # Stop acquisition if we started it
            if not was_acquiring:
                self.stop()

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

    def _update_cached_config(self, config: Dict[str, Any]):
        """Update the cached configuration in a thread-safe manner."""
        with self._config_lock:
            self._cached_config = config.copy()

    def _get_cached_config(self) -> Dict[str, Any]:
        """Get a copy of the cached configuration in a thread-safe manner."""
        with self._config_lock:
            return self._cached_config.copy()

    def _reconcile_display_geometry(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Reconcile device sample-space (QS/TC) to the delivered sample-space.

        The device returns fewer samples than the requested QS (empirically QS-2 in
        AVG/NORMAL mode), so raw ``samples_total`` (QS) and ``t_offset`` (TC = samples
        before the sync moment) do not match the array the client actually plots.
        Left unreconciled, the zero/trigger marker (placed via TC in QS-space) lands a
        couple of samples right of the real trigger, so the trace looks shifted left.

        We report ``samples_total`` = delivered count and ``t_offset`` = the trigger's
        index inside the delivered array::

            trigger_index = TC - (QS - delivered) - 1

        where ``(QS - delivered)`` is the front-dropped-sample count and the extra ``-1``
        is the device's sync convention (the sample that equals the trigger level sits one
        index before the declared sync sample). Verified against live captures at
        TC=64/128/192 (crossing at 61/125/189 = TC-3, delivered=254). ``apply_config``
        performs the exact inverse so the marker-drag round-trips.
        Falls back to a no-op until the first frame establishes the delivered count.
        """
        cfg = dict(cfg)  # never mutate the caller's dict (may be the cached config)
        delivered = self._last_delivered_len
        qs = cfg.get("samples_total")
        tc = cfg.get("t_offset")
        if not delivered or not isinstance(qs, int) or not isinstance(tc, int) or delivered > qs:
            return cfg
        drop = qs - delivered
        trigger_index = tc - drop - 1
        cfg["samples_total"] = delivered
        cfg["t_offset"] = max(0, min(delivered - 1, trigger_index))
        # [task_config-limits] Reconcile the limits block to delivered-space too, using
        # new dicts (never mutate the possibly-cached nested objects).
        lim = cfg.get("limits")
        if isinstance(lim, dict):
            lim = dict(lim)
            st = lim.get("samples_total")
            if isinstance(st, dict) and isinstance(st.get("max"), int):
                lim["samples_total"] = {**st, "max": max(1, st["max"] - drop)}
            to = lim.get("t_offset")
            if isinstance(to, dict):
                lim["t_offset"] = {**to, "max": max(0, delivered - 1)}
            cfg["limits"] = lim
        return cfg

    def _apply_enh_settings(self, cfg: Dict[str, Any], changes: Dict[str, Any]) -> None:
        """Fold resolution-enhancement settings into cfg, silently clamped.  [SP_RES_02_01 / SP_RES_03_01]

        enh_enabled → bool; enh_depth → [2,64]; enh_sma_window → [1,63] then forced odd
        (even → nearest lower odd). No warning on out-of-range, consistent with the
        v_offset/trigger_level clamp. Backend-only: never passed to oscill_client.
        """
        if changes.get("enh_enabled") is not None:
            cfg["enh_enabled"] = bool(changes["enh_enabled"])
        if changes.get("enh_depth") is not None:
            cfg["enh_depth"] = max(2, min(64, int(changes["enh_depth"])))
        if changes.get("enh_sma_window") is not None:
            w = max(1, min(63, int(changes["enh_sma_window"])))
            if w % 2 == 0:
                w -= 1
            cfg["enh_sma_window"] = w

    def _snapshot_config_locked(self) -> Dict[str, Any]:
        """
        Snapshot current device configuration under device lock.
        
        If any parameter fails to read, raises exception to trigger connection reset.
        All parameters must be readable for config to be valid.
        """
        cfg: Dict[str, Any] = {}
        c = self._client
        if not c:
            return cfg
        
        # Read all parameters - any failure will raise exception
        v_div_mv = c.get_v_div_mV()
        cfg["v_div"] = {"v": v_div_mv, "u": "mV"}
        
        t_div_ms = c.get_time_div_ms()
        cfg["t_div"] = {"v": round(t_div_ms, 6), "u": "ms"}
        
        cfg["v_offset"] = c.get_offset_raw()
        cfg["trigger_level"] = c.get_trigger_level()
        
        cfg["trigger_mode_bits"] = c.get_trigger_mode()
        cfg["trigger_mode"] = {"v": cfg["trigger_mode_bits"], "u": "bits"}
        
        cfg["rs_mode"] = c.get_rs_mode()
        
        # Time offset (TC, samples) and optional delay (TD)
        cfg["t_offset"] = c.get_reg_2('TC', signed=False)
        cfg["t_delay"] = c.get_reg_4('TD', signed=False)
        
        total_samples = c.get_reg_2('QS', signed=False)
        cfg["samples_total"] = max(0, int(total_samples))
        
        # Static geometry info for UI
        # [task_qs-raise] live per-connection density (mode-aware), not the class default.
        cfg["samples_per_div"] = getattr(c, 'samples_per_div', 32)
        # [PL_AUDIT_WEB_08] Expose the device horizontal-division count (device truth
        # = 8, NOT the 10 the frontend historically assumed) so the display grid and
        # time-axis are computed against the real capture window.
        cfg["h_divs"] = getattr(c, 'H_DIVS', 8)
        
        # Channel hardware/software modes and sync metadata
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
        
        sw_bits = c.get_channel_sw_mode() & 0x07
        cfg["sw_mode"] = SW_MODE_LABEL_BY_VALUE.get(sw_bits, "NORMAL")
        cfg["sw_mode_bits"] = sw_bits
        
        sync_bits = c.get_sync_type() & 0x03
        cfg["sync_type"] = SYNC_TYPE_LABEL_BY_VALUE.get(sync_bits, "AUTO")
        cfg["sync_type_bits"] = sync_bits
        
        t1 = cfg["trigger_mode_bits"]
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
        
        # [SP_RES_01_01] Resolution-enhancement controls (backend-only, C_RES_DEC_04 —
        # never written to a device register). Carried forward across re-snapshots from
        # the prior cached config so they survive an unrelated register change; seeded to
        # defaults on first snapshot. apply_config mutates them (clamped) via
        # _apply_enh_settings. Bare scalars, not {v,u} (StructuredConfigValues).
        prev = self._get_cached_config()
        cfg["enh_enabled"] = bool(prev.get("enh_enabled", False))
        cfg["enh_depth"] = int(prev.get("enh_depth", 16))
        cfg["enh_sma_window"] = int(prev.get("enh_sma_window", 1))

        # [task_config-limits] Parameter min/max for client informativeness + clamping.
        # Device-authoritative where a property exists (v_div via V1l/V1h with step-list
        # fallback; samples_total via QSh); structural for raw 0..255 offsets; t_div from
        # the canonical step list (no single device max — roll mode is unbounded).
        # samples_total/t_offset are seeded in raw QS-space and reconciled to
        # delivered-space in _reconcile_display_geometry.
        dev_limits = c.read_device_limits()
        # V1l/V1h "low/high" labels don't reliably map to numeric min/max — derive by
        # value; fall back to the step-list bounds if the device omits a property.
        v_div_bounds = [v for v in (dev_limits.get("v1l_mv"), dev_limits.get("v1h_mv")) if v]
        v_div_min = min(v_div_bounds) if v_div_bounds else VDIV_VALUES_MV[0]
        v_div_max = max(v_div_bounds) if v_div_bounds else VDIV_VALUES_MV[-1]
        qsh = dev_limits.get("qsh") or int(total_samples)
        # Stepped params (v_div, t_div) expose the discrete allowed-value LIST instead
        # of min/max; continuous params keep {min, max}. v_div's list is the step list
        # filtered to the device-supported sensitivity range (V1l/V1h).
        v_div_values = [v for v in VDIV_VALUES_MV if v_div_min <= v <= v_div_max] or list(VDIV_VALUES_MV)
        cfg["limits"] = {
            "v_div": {"values": v_div_values, "u": "mV"},
            "v_offset": {"min": 0, "max": 0xFF},
            "trigger_level": {"min": 0, "max": 0xFF},
            "t_div": {"values": list(TDIV_VALUES_MS), "u": "ms"},
            "samples_total": {"min": 1, "max": int(qsh)},
            "t_offset": {"min": 0, "max": max(0, int(total_samples) - 1)},
            # [SP_RES_01_04] Structural bounds (cap per-poll enhancement cost).
            "enh_depth": {"min": 2, "max": 64},
            "enh_sma_window": {"min": 1, "max": 63},
        }

        cfg["cfg_id"] = self._cfg_id  # Add config ID
        # Update cached config
        self._update_cached_config(cfg)
        return cfg

    def _record_frame(self, payload: Dict[str, Any]):
        with self._frames_lock:
            self._seq += 1
            payload["seq"] = self._seq
            self._frames.append(payload)
        # [task_scope-zero-offset] Remember how many samples the device actually
        # delivered, so get_status()/apply_config() can reconcile QS/TC to it.
        samples = payload.get("samples")
        if samples:
            self._last_delivered_len = len(samples)

    def _acq_loop(self):
        # Soft loop with opportunistic device access
        backoff_s = 0.005  # Reduced from 0.02 to 0.005 (5ms) for lower latency
        consecutive_errors = 0
        max_consecutive_errors = 5  # Disconnect if 5 consecutive errors
        force_disconnect = False
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
                # [PL_AUDIT_WEB_04] Use the cached config instead of re-reading ~15
                # registers over serial on every frame. Config only changes via
                # connect()/apply_config(), both of which refresh the cache under
                # the same lock. A broken device is already detected by get_frame()
                # above (it raises), so the per-frame snapshot health-check is redundant.
                cfg = self._get_cached_config()
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
                self._log.error(f"Acquisition loop error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                if consecutive_errors >= max_consecutive_errors:
                    self._log.error(f"Device communication failed after {consecutive_errors} consecutive errors, forcing disconnect")
                    # [PL_AUDIT_WEB_05] Do NOT call the executor-based disconnect()
                    # from here: we hold _dev_lock and disconnect() submits work to
                    # the device executor, which would block on the same lock (RLock
                    # is not re-entrant across threads) for the full 5s timeout. Flag
                    # it and perform the disconnect after releasing the lock, below.
                    force_disconnect = True
                else:
                    # Swallow and keep trying
                    time.sleep(backoff_s)
            finally:
                try:
                    self._dev_lock.release()
                except RuntimeError:
                    pass
            if force_disconnect:
                break
            # Pace the loop lightly to avoid hogging CPU/USB
            time.sleep(backoff_s)
        if force_disconnect:
            # Now off the device executor path and not holding _dev_lock: safe to
            # tear the connection down directly on this (acquisition) thread.
            try:
                self._disconnect_internal()
            except Exception:
                pass

    def start(self) -> Dict[str, Any]:
        """Start data acquisition from device."""
        with self._dev_lock:
            if not self._client:
                raise RuntimeError("Not connected")
            self._start_acquisition_locked()
            self._is_acquiring = True
            return {"status": "ok"}

    def stop(self) -> Dict[str, Any]:
        """Stop data acquisition from device."""
        with self._dev_lock:
            self._stop_acquisition_locked()
            self._is_acquiring = False
            return {"status": "ok"}

    def shutdown(self):
        """Shutdown the service and cleanup resources."""
        self._log.info("Shutting down DeviceService")
        try:
            self.disconnect()
        except Exception as e:
            self._log.error(f"Error during disconnect on shutdown: {e}")
        
        # Shutdown executor
        try:
            self._device_executor.shutdown(wait=True)
        except Exception as e:
            self._log.error(f"Error shutting down executor: {e}")
