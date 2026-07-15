import time
import serial
from serial.tools import list_ports
from typing import Optional, Dict, Any, Tuple, List

# OBEX opcodes
OBEX_CONNECT = 0x80
OBEX_GET = 0x03
OBEX_GET_FINAL = 0x83
OBEX_PUT_FINAL = 0x82
OBEX_ABORT = 0xFF
# [task_qs-raise] SET-SPEED is a device-specific OBEX opcode (mirrors Android
# ClientSession.setSpeed → sendRequest(Header.OSCILL_SPEED, {coeff})). Body = one
# speed-coefficient byte; baud = 1842000 / coeff. Sent at the CURRENT baud; the device
# switches its UART after acking, so the host must switch to match immediately after.
OSCILL_SPEED = 0x91

# Headers
OSCILL_PROPERTY = 0x70
OSCILL_REGISTRY = 0x71
OSCILL_DATA = 0x72
BODY = 0x48
END_OF_BODY = 0x49
CONNECTION_ID = 0xCB
OSCILL_1BYTE = 0xB1
OSCILL_2BYTE = 0xF0
OSCILL_4BYTE = 0xF1

VENDOR_ID = 0x10c4
PRODUCT_ID = 0x840E

# [task_config-limits] Canonical device step lists — single source of truth.
# Kept in the Layer-0 device client so higher layers (auto_adjust, device_service)
# depend downward (LayerDependencyDirection) and share one definition
# (SingleSourceForSharedConstants). auto_adjust re-exports these for compatibility.
VDIV_VALUES_MV = [20.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0]
TDIV_VALUES_MS = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]

class OscillClient:
    # [task_qs-raise] Default/fallback sampling density (samples per division). The
    # ACTIVE density is the per-instance `self.samples_per_div`, derived at connect and
    # on mode change from the device's QSh ceiling (refresh_samples_per_div). QSh is
    # mode-dependent (8-bit modes ~1788 → 223/div; 16-bit hi-res ~894 → 111/div), so a
    # single constant cannot be optimal for every mode.
    SAMPLES_PER_DIV = 32
    MAX_SAMPLES_PER_DIV = 256  # safety ceiling on the derived density
    H_DIVS = 8

    # [task_qs-raise] Serial speed control. Init/handshake happens at DEFAULT_BAUD (per
    # the device docs — the session starts at a low speed); after init the link is raised
    # to HIGH_BAUD so large frames (big QS) transfer fast. baud = 1842000 / coeff.
    DEFAULT_BAUD = 115200
    HIGH_BAUD = 921600           # host side; device runs 921000 (1842000/2) — 0.065% off, well in tolerance
    SPEED_115200 = 0x10          # coeff for 115200
    SPEED_921000 = 0x02          # coeff for 921000

    # Channel data format codes (bits 2..0 of the FIRST channel attribute byte)
    # Mapping follows Android implementation in ChannelSWMode + OscillData docs.
    SAMPLE_FORMATS = {
        0x00: {"name": "AVG", "value_bits": 8, "components": 1},
        0x01: {"name": "AVG_HIRES", "value_bits": 16, "components": 1},
        0x02: {"name": "PEAK_INTERLACED", "value_bits": 8, "components": 1},
        0x03: {"name": "PEAK_DOUBLE", "value_bits": 8, "components": 2},
        0x04: {"name": "NORMAL", "value_bits": 8, "components": 1},
    }

    def __init__(self, port: str, baud: int = 115200, timeout: float = 3.0):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self.conn_id: Optional[bytes] = None
        # [task_qs-raise] Active sampling density; refreshed from QSh per mode.
        self.samples_per_div: int = self.SAMPLES_PER_DIV
        # Cached values
        self._cpu_tick_10ps: Optional[int] = None  # machine cycle length in 10ps units
        # [task_qs-raise] Cached per-frame acquisition wait (QS × sample_period). Recomputed
        # lazily after invalidation on a QS/TS/MC change, so steady-state frames make no
        # per-frame register reads (each costs a CP210x USB round-trip — the dominant cost
        # once the link is at high baud).
        self._frame_wait_s: Optional[float] = None

    def open(self):
        # [PL_AUDIT_WEB_B14] Guard against re-opening over a live port (SP_OCL
        # invariant): silently replacing self.ser would leak the previous handle.
        if self.ser is not None and getattr(self.ser, "is_open", False):
            raise AssertionError("Serial port already open; call close() first")
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

    def close(self, restore: bool = True):
        # [task_qs-raise] Return the device to the base baud before closing so the next
        # session's low-speed handshake succeeds (the device keeps its UART speed across
        # an OBEX disconnect — reset() is a software ABORT, not a UART reset). Best-effort:
        # if comms are already dead, we still drop the host baud. Pass restore=False from
        # the connect-time rescue path to avoid recursion.
        try:
            if restore:
                self.restore_default_speed()
        except Exception:
            pass
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.ser = None
            self.conn_id = None
            self.baud = self.DEFAULT_BAUD

    # ---------- Serial speed control (task_qs-raise) ----------
    def set_speed(self, coeff: int) -> bool:
        """Send the OBEX SET-SPEED request (opcode 0x91) with a 1-byte coefficient at the
        CURRENT baud. The device acks at the OLD baud (response opcode 0x0F, echoing the
        coefficient) and THEN switches its UART, so the host must switch immediately after
        (see _set_host_baud). Returns True if the device acked. NOTE: the device switches on
        receipt regardless of this return, so callers must switch the host even if this is
        False (see raise_speed) — otherwise the link desyncs."""
        assert self.ser is not None
        self.ser.write(self._build_packet(OSCILL_SPEED, bytes([coeff & 0xFF])))
        # The ack (0x0F) is immediate; use a short read timeout so a dead/desynced port
        # can't block the full serial timeout (~3 s) here — this runs inside connect's 5 s
        # executor budget (rescue does two of these) and inside disconnect under _dev_lock.
        old_timeout = self.ser.timeout
        try:
            self.ser.timeout = 0.5
            opcode, _ = self._read_resp()
        finally:
            self.ser.timeout = old_timeout
        # 0x0F = device's SET-SPEED ack (observed); accept the OBEX OK/Continue codes too.
        return opcode in (0x0F, 0xA0, 0x90)

    def _set_host_baud(self, baud: int) -> None:
        """Switch the host serial baud to match the device, then flush stale bytes."""
        assert self.ser is not None
        self.ser.baudrate = baud
        self.baud = baud
        time.sleep(0.05)  # let the device's UART settle at the new rate
        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except Exception:
            pass

    def _verify_link(self) -> bool:
        """Confirm two-way comms at the current baud by reading a known register."""
        try:
            return int(self.get_reg_2('QS', signed=False)) > 0
        except Exception:
            return False

    def raise_speed(self, coeff: int = SPEED_921000, baud: int = HIGH_BAUD) -> int:
        """Raise the serial speed AFTER the low-speed init/handshake. Commands the device
        (SET-SPEED at the current baud), switches the host, and verifies the link. Reverts
        to the base baud on any failure. Returns the achieved baud."""
        if self.ser is None or self.baud == baud:
            return self.baud
        try:
            # The device switches its UART on RECEIPT of this command, so we must switch
            # the host regardless of the ack — bailing here (not switching) is exactly what
            # desyncs the link. set_speed's bool is advisory (logged), not a gate.
            self.set_speed(coeff)
            self._set_host_baud(baud)
            if self._verify_link():
                return self.baud
            # Unverified at the raised baud: both ends are high now, so SET-SPEED(115200)
            # still reaches the device — bring both back down cleanly.
            self.restore_default_speed()
            return self.baud
        except Exception:
            try:
                self.restore_default_speed()
            except Exception:
                pass
            return self.baud

    def restore_default_speed(self) -> None:
        """Return the device (and host) to the base baud. Best-effort — safe to call even
        if comms are dead; the host baud is dropped regardless so a reopen starts clean."""
        if self.ser is None or self.baud == self.DEFAULT_BAUD:
            return
        try:
            self.set_speed(self.SPEED_115200)
            self._set_host_baud(self.DEFAULT_BAUD)
        except Exception:
            # Comms may have died mid-restore. Drop BOTH the real port baud and our
            # bookkeeping to 115200 so they stay in agreement (setting only self.baud
            # would leave the host actually at the high baud → a full-session data outage).
            if self.ser is not None:
                try:
                    self.ser.baudrate = self.DEFAULT_BAUD
                except Exception:
                    pass
            self.baud = self.DEFAULT_BAUD

    def open_and_handshake(self) -> None:
        """Open at the base baud and complete the OBEX handshake (reset + connect). If the
        device is stuck at a raised baud from a previous ungraceful session, rescue it:
        reopen at HIGH_BAUD, command it back to 115200, then reopen at base and retry."""
        self.baud = self.DEFAULT_BAUD
        self.open()
        try:
            self.reset()
            self.connect()
            return
        except Exception:
            pass
        # Rescue path — the device may still be at HIGH_BAUD.
        try:
            self.close(restore=False)
            self.baud = self.HIGH_BAUD
            self.open()
            try:
                self.set_speed(self.SPEED_115200)
                time.sleep(0.05)
            finally:
                self.close(restore=False)
        except Exception:
            try:
                self.close(restore=False)
            except Exception:
                pass
        # Retry the handshake at the base baud (raises if the device is truly unreachable).
        self.baud = self.DEFAULT_BAUD
        self.open()
        self.reset()
        self.connect()

    def _build_packet(self, opcode: int, headers: bytes = b"") -> bytes:
        total = 3 + len(headers)
        return bytes([opcode]) + total.to_bytes(2, 'big') + headers

    def _build_byte_seq(self, header_id: int, payload: bytes) -> bytes:
        length = len(payload) + 3
        return bytes([header_id]) + length.to_bytes(2, 'big') + payload

    def _build_4byte(self, header_id: int, payload4: bytes) -> bytes:
        assert len(payload4) == 4
        return bytes([header_id]) + payload4

    def _read_exact(self, n: int) -> bytes:
        buf = b""
        assert self.ser is not None
        while len(buf) < n:
            chunk = self.ser.read(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return buf

    def _read_resp(self) -> Tuple[int, bytes]:
        head = self._read_exact(3)
        if len(head) < 3:
            raise IOError("OBEX header read timeout")
        opcode = head[0]
        length = int.from_bytes(head[1:3], 'big')
        rest = self._read_exact(max(0, length - 3))
        return opcode, rest

    def _parse_headers(self, data: bytes) -> Dict[int, List[bytes]]:
        i = 0
        out: Dict[int, List[bytes]] = {}
        while i < len(data):
            hid = data[i]
            cls = hid & 0xC0
            if cls in (0x00, 0x40):
                if i + 3 > len(data): break
                length = int.from_bytes(data[i+1:i+3], 'big')
                payload_len = max(0, length - 3)
                start = i + 3
                end = start + payload_len
                payload = data[start:end] if end <= len(data) else b""
                i = end
            elif cls == 0x80:
                if i + 2 > len(data): break
                payload = bytes([data[i+1]])
                i += 2
            elif cls == 0xC0:
                if i + 5 > len(data): break
                payload = data[i+1:i+5]
                i += 5
            else:
                break
            out.setdefault(hid, []).append(payload)
        return out

    # ---------- Device/port utils ----------
    @staticmethod
    def auto_find_port() -> Optional[str]:
        for p in list_ports.comports():
            try:
                if p.vid is not None and p.pid is not None:
                    if int(p.vid) == VENDOR_ID and int(p.pid) == PRODUCT_ID:
                        return p.device
            except Exception:
                # Some platforms don't expose vid/pid
                pass
        # Fallback: common serial names
        for guess in ("/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0"):
            try:
                with serial.Serial(guess) as _:
                    return guess
            except Exception:
                continue
        return None

    def reset(self):
        assert self.ser is not None
        pkt = self._build_packet(OBEX_ABORT)
        self.ser.write(pkt)
        time.sleep(0.3)
        # drain
        self.ser.timeout = 0.05
        while self.ser.read(256):
            pass
        self.ser.timeout = self.timeout

    def connect(self):
        assert self.ser is not None
        # version, flags, max_rx
        tail = bytes([0x10, 0x00]) + (0x1000).to_bytes(2, 'big')
        self.ser.write(self._build_packet(OBEX_CONNECT, tail))
        opcode, body = self._read_resp()
        if opcode != 0xA0:
            raise IOError(f"Connect failed 0x{opcode:02x}")
        extra = body[4:] if len(body) >= 4 else b""
        hdrs = self._parse_headers(extra)
        if CONNECTION_ID in hdrs and hdrs[CONNECTION_ID]:
            self.conn_id = hdrs[CONNECTION_ID][-1]
        else:
            self.conn_id = None
        # Warm up caches
        self._cpu_tick_10ps = None

    def get_property(self, name: str) -> Optional[bytes]:
        assert self.ser is not None
        headers = b""
        if self.conn_id:
            headers += self._build_4byte(CONNECTION_ID, self.conn_id)
        headers += self._build_byte_seq(OSCILL_PROPERTY, name.encode('ascii'))
        self.ser.write(self._build_packet(OBEX_GET_FINAL, headers))
        opcode, body = self._read_resp()
        if opcode not in (0xA0, 0x90):
            return None
        hdrs = self._parse_headers(body)
        if OSCILL_4BYTE in hdrs and hdrs[OSCILL_4BYTE]:
            return hdrs[OSCILL_4BYTE][-1]
        if OSCILL_2BYTE in hdrs and hdrs[OSCILL_2BYTE]:
            return hdrs[OSCILL_2BYTE][-1]
        return None

    def _compute_frame_wait_s(self) -> Optional[float]:
        """Estimate the per-frame acquisition wait = QS × sample_period (+5% margin, capped
        at 3 s). Reads QS/TS registers. Returns None on a read failure so the caller does
        NOT cache it — the next frame retries, preserving per-frame self-healing on a
        transient glitch (a bad value cached here would stick until the next config change)."""
        try:
            qs = self.get_reg_2('QS')
            sample_s = self.get_sample_period_ps() / 1e12
            est = float(qs) * float(sample_s)
            return min(max(est * 1.05, 0.0), 3.0)
        except Exception:
            return None

    def get_data_single(self, before_delay_ms: int = 0) -> Optional[bytes]:
        assert self.ser is not None
        headers = b""
        if self.conn_id:
            headers += self._build_4byte(CONNECTION_ID, self.conn_id)
        headers += self._build_byte_seq(OSCILL_DATA, b"D")
        # Allow device to prepare; for long time/div add adaptive wait based on QS and sample period
        wait_s = 0.0
        if before_delay_ms > 0:
            wait_s = max(wait_s, before_delay_ms / 1000.0)
        else:
            # [task_qs-raise] Use the cached wait (QS × sample_period); recompute only after
            # a config change invalidated it. Avoids per-frame register reads (~2 CP210x USB
            # round-trips) that dominate the frame time once the link is at high baud.
            if self._frame_wait_s is None:
                self._frame_wait_s = self._compute_frame_wait_s()  # stays None on failure → retried next frame
            if self._frame_wait_s is not None:
                wait_s = self._frame_wait_s
            else:
                # Transient read failure: fall back to a t/div heuristic for THIS frame
                # only (do not cache), matching the pre-cache self-healing behaviour.
                try:
                    tdiv = self.get_time_div_ms() / 1000
                    wait_s = min(tdiv, 0.5) if tdiv >= 0.02 else 0.0
                except Exception:
                    wait_s = 0.0
        if wait_s > 0:
            time.sleep(wait_s)
        # Temporarily extend serial timeout to cover slow acquisitions
        old_timeout = self.ser.timeout
        try:
            # Budget timeout to acquisition estimate + margin, cap to 10s
            budget = wait_s + 1.0
            if old_timeout is None or old_timeout < budget:
                self.ser.timeout = min(max(budget, 1.5), 10.0)

            # Initial request (final flag ok). Some devices will return Continue for long data or ROLL mode.
            self.ser.write(self._build_packet(OBEX_GET_FINAL, headers))
            opcode, body = self._read_resp()

            # Collect body chunks across potential Continue responses until End-of-Body arrives.
            chunks: List[bytes] = []
            start_t = time.monotonic()
            max_chunks = 4  # return after a few chunks for ROLL
            while True:
                hdrs = self._parse_headers(body)
                if BODY in hdrs:
                    for b in hdrs[BODY]:
                        if b:
                            chunks.append(b)
                if END_OF_BODY in hdrs and hdrs[END_OF_BODY]:
                    # End-of-Body may carry the final payload chunk. Return all collected data.
                    eob = hdrs[END_OF_BODY][-1]
                    if chunks:
                        return b"".join(chunks + ([eob] if eob else []))
                    return eob
                # Time/iteration budget: return what we have in ROLL or very slow modes
                if chunks and (
                    (time.monotonic() - start_t) > (budget * 1.25) or
                    len(chunks) >= max_chunks
                ):
                    return b"".join(chunks)
                if opcode not in (0x90,):
                    # No continuation indicated and no EoB; fall back to concatenated chunks if any
                    if chunks:
                        return b"".join(chunks)
                    return None
                # Ask for next chunk with GET (no Final); include only connection id header
                # Tiny backoff helps devices that need time to collect next packet
                time.sleep(min(0.05, max(0.0, budget / 8.0)))
                cont_headers = b""
                if self.conn_id:
                    cont_headers += self._build_4byte(CONNECTION_ID, self.conn_id)
                self.ser.write(self._build_packet(OBEX_GET, cont_headers))
                opcode, body = self._read_resp()
        finally:
            self.ser.timeout = old_timeout
        # Unreachable: loop returns upon success or lack of chunks

    # ---------- Registry helpers ----------
    def _get_registry(self, name: str) -> Dict[int, List[bytes]]:
        assert self.ser is not None
        headers = b""
        if self.conn_id:
            headers += self._build_4byte(CONNECTION_ID, self.conn_id)
        headers += self._build_byte_seq(OSCILL_REGISTRY, name.encode('ascii'))
        self.ser.write(self._build_packet(OBEX_GET_FINAL, headers))
        opcode, body = self._read_resp()
        if opcode not in (0xA0, 0x90):
            raise IOError(f"GET registry {name} failed 0x{opcode:02x}")
        return self._parse_headers(body)

    def get_reg_1(self, name: str) -> int:
        hdrs = self._get_registry(name)
        if OSCILL_1BYTE in hdrs and hdrs[OSCILL_1BYTE]:
            return hdrs[OSCILL_1BYTE][-1][0]
        raise KeyError(f"No 1B registry value for {name}")

    def get_reg_2(self, name: str, signed: bool = False) -> int:
        hdrs = self._get_registry(name)
        if OSCILL_2BYTE in hdrs and hdrs[OSCILL_2BYTE]:
            raw = hdrs[OSCILL_2BYTE][-1]
            # Some implementations return 2-byte values padded to 4 bytes for 0xF0.
            # Per protocol, the significant 2 bytes are the lower two in big-endian.
            low2 = raw[-2:] if len(raw) >= 2 else raw
            val = int.from_bytes(low2, 'big', signed=signed)
            return val
        raise KeyError(f"No 2B registry value for {name}")

    def get_reg_4(self, name: str, signed: bool = False) -> int:
        hdrs = self._get_registry(name)
        if OSCILL_4BYTE in hdrs and hdrs[OSCILL_4BYTE]:
            raw = hdrs[OSCILL_4BYTE][-1]
            val = int.from_bytes(raw[-4:], 'big', signed=signed)
            return val
        raise KeyError(f"No 4B registry value for {name}")

    def _put_registry(self, name: str, value_header: int, payload: bytes) -> Dict[int, List[bytes]]:
        assert self.ser is not None
        headers = b""
        if self.conn_id:
            headers += self._build_4byte(CONNECTION_ID, self.conn_id)
        headers += self._build_byte_seq(OSCILL_REGISTRY, name.encode('ascii'))
        if value_header in (OSCILL_1BYTE,):
            headers += bytes([value_header, payload[0]])
        elif value_header in (OSCILL_2BYTE, OSCILL_4BYTE):
            headers += bytes([value_header]) + payload
        else:
            raise ValueError("Unsupported value header")
        self.ser.write(self._build_packet(OBEX_PUT_FINAL, headers))
        opcode, body = self._read_resp()
        if opcode not in (0xA0, 0x90):
            raise IOError(f"PUT registry {name} failed 0x{opcode:02x}")
        return self._parse_headers(body)

    def set_reg_1(self, name: str, val: int) -> int:
        valb = max(0, min(255, int(val)))
        hdrs = self._put_registry(name, OSCILL_1BYTE, bytes([valb]))
        return self.get_reg_1(name)

    def set_reg_2(self, name: str, val: int, signed: bool = False) -> int:
        if signed:
            val = int(val) & 0xFFFF
        else:
            val = max(0, min(0xFFFF, int(val)))
        # Protocol uses header 0xF0 (OSCILL_2BYTE) which carries 4 bytes total.
        # Embed the 16-bit value in the lower 2 bytes of a 4-byte big-endian field.
        payload = (0).to_bytes(2, 'big') + val.to_bytes(2, 'big', signed=False)
        hdrs = self._put_registry(name, OSCILL_2BYTE, payload)
        return self.get_reg_2(name, signed=signed)

    def set_reg_4(self, name: str, val: int, signed: bool = False) -> int:
        if signed:
            val = int(val) & 0xFFFFFFFF
        else:
            val = max(0, min(0xFFFFFFFF, int(val)))
        payload = val.to_bytes(4, 'big', signed=False)
        hdrs = self._put_registry(name, OSCILL_4BYTE, payload)
        return self.get_reg_4(name, signed=signed)

    # ---------- High-level config ----------
    def get_cpu_tick_10ps(self) -> int:
        if self._cpu_tick_10ps is not None:
            return self._cpu_tick_10ps
        # Prefer current register MC, fallback to default property MCd
        try:
            mc = self.get_reg_2('MC', signed=False)
        except Exception:
            prop = self.get_property('MCd')
            mc = int.from_bytes(prop[-2:], 'big') if prop else 1000  # default 1000 = 10ns
        self._cpu_tick_10ps = mc
        return mc

    def get_v_div_mV(self) -> int:
        return self.get_reg_2('V1', signed=False)

    def set_v_div_mV(self, mv_per_div: int) -> int:
        return self.set_reg_2('V1', mv_per_div, signed=False)

    def read_device_limits(self) -> Dict[str, Optional[int]]:
        """[task_config-limits] Read device-reported parameter bounds via property
        GETs (0x70, 2-byte big-endian). V1l/V1h = the two channel-sensitivity bounds
        in mV/div (same unit as get_v_div_mV; see caller note on min/max). QSh = max
        output sample count for the current settings. None for any bound omitted."""
        def _prop_int(name: str) -> Optional[int]:
            b = self.get_property(name)
            return int.from_bytes(b, 'big') if b else None
        # Raw property values — caller derives min/max via min()/max() because the
        # V1l/V1h "low/high" labels do not reliably map to numeric min/max across units.
        return {
            'v1l_mv': _prop_int('V1l'),
            'v1h_mv': _prop_int('V1h'),
            'qsh': _prop_int('QSh'),
        }

    def get_offset_volts(self) -> float:
        native = self.get_reg_2('P1', signed=True)
        sens_mv = max(1, self.get_v_div_mV())
        # offset [mV] = (sens[mV/div] * 8 / 256) * native
        mv = (sens_mv * 8.0 / 256.0) * native
        return mv / 1000.0

    def set_offset_volts(self, offset_v: float) -> float:
        sens_mv = max(1, self.get_v_div_mV())
        native = round((offset_v * 1000.0) / (sens_mv * 8.0 / 256.0))
        self.set_reg_2('P1', native, signed=True)
        return self.get_offset_volts()

    def get_offset_raw(self) -> int:
        """Returns the offset as a raw 0..255 UI value mapped from signed P1 register."""
        native = self.get_reg_2('P1', signed=True)
        return max(0, min(0xFF, native + 128))

    def set_offset_raw(self, value: int) -> int:
        """Applies a UI raw 0..255 offset by mapping to the signed P1 register (doc §2.3)."""
        raw = max(0, min(0xFF, int(value)))
        native = raw - 128
        self.set_reg_2('P1', native, signed=True)
        return self.get_offset_raw()

    def get_trigger_level(self) -> int:
        return self.get_reg_1('S1')

    def set_trigger_level(self, level_0_255: int) -> int:
        return self.set_reg_1('S1', level_0_255)

    def get_trigger_mode(self) -> int:
        # T1 bitfield per docs
        return self.get_reg_1('T1')

    def set_trigger_mode(self, t1_bits: int) -> int:
        return self.set_reg_1('T1', t1_bits)

    def set_cpu_freq_mhz(self, freq_mhz: float) -> int:
        """Sets the CPU frequency by calculating and setting the MC register."""
        if freq_mhz <= 0:
            raise ValueError("Frequency must be positive")
        # MC value is clock period in 10ps units. Period (s) = 1 / Freq (Hz)
        # Period (10ps) = (1 / (freq_mhz * 1e6)) * 1e11 = 1e5 / freq_mhz
        mc_value = int(round(1e5 / freq_mhz))
        self.set_reg_2('MC', mc_value, signed=False)
        # Invalidate caches (MC changes the sample period → frame wait)
        self._cpu_tick_10ps = None
        self._frame_wait_s = None
        return self.get_cpu_tick_10ps()

    def set_channel_hw_mode(self, o1_bits: int) -> int:
        """Sets the channel hardware mode (O1). 1-byte value."""
        return self.set_reg_1('O1', o1_bits)

    def get_channel_hw_mode(self) -> int:
        """Returns raw O1 register bits for channel hardware mode."""
        return self.get_reg_1('O1')

    def set_channel_sw_mode(self, m1_bits: int) -> int:
        """Sets the channel software/processing mode (M1). 1-byte value."""
        return self.set_reg_1('M1', m1_bits)

    def get_channel_sw_mode(self) -> int:
        """Returns raw M1 register bits for channel software mode."""
        return self.get_reg_1('M1')

    def get_rs_mode(self) -> int:
        return self.get_reg_1('RS')

    def set_rs_mode(self, rs_bits: int) -> int:
        return self.set_reg_1('RS', rs_bits)

    def get_ts_native(self) -> int:
        return self.get_reg_4('TS', signed=False)

    def set_ts_native(self, ts_native: int) -> int:
        self._frame_wait_s = None  # sample period changed → invalidate cached frame wait
        return self.set_reg_4('TS', ts_native, signed=False)

    def get_sample_period_ps(self) -> float:
        ts = self.get_ts_native()
        cpu_10ps = self.get_cpu_tick_10ps()
        # ts is in MC*256; MC in 10ps; so sample_ps = ts * (cpu_10ps*10) / 256
        sample_ps = (ts * (cpu_10ps * 10.0)) / 256.0
        return sample_ps

    def set_time_div_ms(self, t_div_ms: float) -> float:
        # sample period = t_div_ms / SAMPLES_PER_DIV
        sample_ps = max(1, (float(t_div_ms) * 1e9) / self.samples_per_div)
        cpu_ps = self.get_cpu_tick_10ps() * 10.0
        ts_native = int(round(sample_ps * 256.0 / cpu_ps))
        self.set_ts_native(ts_native)
        return self.get_time_div_ms()

    def get_time_div_ms(self) -> float:
        return (self.get_sample_period_ps() * self.samples_per_div) / 1e9



    def set_scan_delay(self, value: int) -> int:
        """
        Sets the scan delay (TD).
        :param value: 4-byte unsigned integer for the delay.
        :return: The actual value set in the register.
        """
        return self.set_reg_4('TD', value, signed=False)

    def set_max_sync_wait_auto(self, value: int) -> int:
        """
        Sets the max sync wait time for auto-start (TA).
        :param value: 4-byte unsigned integer for the wait time.
        :return: The actual value set in the register.
        """
        return self.set_reg_4('TA', value, signed=False)

    def set_max_sync_wait_on_trig(self, value: int) -> int:
        """
        Sets the max sync wait time for waiting-start (TW).
        :param value: 4-byte unsigned integer for the wait time.
        :return: The actual value set in the register.
        """
        return self.set_reg_4('TW', value, signed=False)

    def set_avg_passes(self, value: int) -> int:
        """
        Sets the number of averaging/peak passes (AP).
        :param value: 1-byte integer for the number of passes.
        :return: The actual value set in the register.
        """
        return self.set_reg_1('AP', value)

    def set_min_ris_passes(self, value: int) -> int:
        """
        Sets the minimum number of passes in RIS mode (AR).
        :param value: 1-byte integer for the number of passes.
        :return: The actual value set in the register.
        """
        return self.set_reg_1('AR', value)

    def get_sync_type(self) -> int:
        """Returns raw RT register bits describing acquisition sync type."""
        return self.get_reg_1('RT')

    def set_sync_type(self, value: int) -> int:
        """Sets the RT register controlling acquisition sync type."""
        return self.set_reg_1('RT', value)

    def set_samples_offset(self, value: int) -> int:
        """
        Sets the samples offset/centering (TC).
        :param value: 2-byte unsigned integer for the offset.
        :return: The actual value set in the register.
        """
        clamped = max(0, min(0xFFFF, int(value)))
        self.set_reg_2('TC', clamped, signed=False)
        return self.get_reg_2('TC', signed=False)

    def ensure_qs(self, total_samples: Optional[int] = None) -> int:
        total = total_samples or (self.samples_per_div * self.H_DIVS)
        self._frame_wait_s = None  # QS changed → invalidate cached frame wait
        return self.set_reg_2('QS', total, signed=False)

    def refresh_samples_per_div(self) -> int:
        """[task_qs-raise] Derive the sampling density from the device's QSh ceiling for
        the CURRENT mode and store it in self.samples_per_div. QSh is the max output
        sample count for the active regime (mode/RS/TS/AP); dividing by H_DIVS gives the
        max samples-per-division that fits. Bounded to [SAMPLES_PER_DIV, MAX_SAMPLES_PER_DIV].
        Returns the new density; leaves it unchanged if QSh cannot be read.

        Caller must hold the device lock and have already applied any mode change, since
        QSh depends on the mode. Changing the density changes the time-per-sample for a
        given t/div, so the caller must re-apply the timebase (set_time_div_ms) and QS
        (ensure_qs) afterwards.
        """
        try:
            b = self.get_property('QSh')
            qsh = int.from_bytes(b, 'big') if b else None
        except Exception:
            qsh = None
        if qsh and qsh > 0:
            derived = qsh // self.H_DIVS
            self.samples_per_div = max(self.SAMPLES_PER_DIV, min(self.MAX_SAMPLES_PER_DIV, derived))
        return self.samples_per_div

    # ---------- Frame parsing ----------
    @staticmethod
    def _process_avg_samples(raw_data: bytes, limit: int) -> List[int]:
        """Process averaging mode samples (1 byte per sample)."""
        return list(raw_data[:limit])

    @staticmethod
    def _process_avg_hires_samples(raw_data: bytes, limit: int) -> List[int]:
        """Process high-resolution averaging mode samples (2 bytes per sample, big-endian)."""
        samples = []
        for i in range(0, limit, 2):
            if i + 2 <= limit:
                val = int.from_bytes(raw_data[i:i + 2], 'big')
                samples.append(val)
        return samples

    @staticmethod
    def _process_normal_samples(raw_data: bytes, limit: int) -> List[int]:
        """Process normal mode samples (1 byte per sample)."""
        return list(raw_data[:limit])

    @staticmethod
    def _process_peak_interlaced_samples(raw_data: bytes, value_bytes: int) -> Tuple[List[int], List[int], List[int]]:
        """Process interlaced peak mode (alternating min/max) with interpolation and min/max validation."""
        return OscillClient._process_peak_samples(raw_data, value_bytes)

    @staticmethod
    def _process_peak_samples(raw_data: bytes, value_bytes: int) -> Tuple[List[int], List[int], List[int]]:
        """
        Process peak mode data with interpolation and min/max validation.
        
        Args:
            raw_data: Raw bytes from the channel data
            value_bytes: Number of bytes per value (1 or 2)
            
        Returns:
            Tuple of (samples, peak_min, peak_max) where samples is the expanded/interpolated list
        """
        raw_peak_min: List[int] = []
        raw_peak_max: List[int] = []
        samples: List[int] = []
        
        stride = value_bytes * 2
        limit = len(raw_data) - (len(raw_data) % stride)
        
        # Extract min/max pairs from raw data
        for i in range(0, limit, stride):
            lo_bytes = raw_data[i:i + value_bytes]
            hi_bytes = raw_data[i + value_bytes:i + stride]
            if len(lo_bytes) < value_bytes or len(hi_bytes) < value_bytes:
                break
            lo_val = int.from_bytes(lo_bytes, 'big')
            hi_val = int.from_bytes(hi_bytes, 'big')
            # Ensure min <= max as per peak mode semantics
            if lo_val > hi_val:
                lo_val, hi_val = hi_val, lo_val
            raw_peak_min.append(lo_val)
            raw_peak_max.append(hi_val)
        
        # Expand Peak samples to match other modes' sample count
        # Each peak interval [min, max] becomes 2 samples with smooth interpolation
        peak_min: List[int] = []
        peak_max: List[int] = []
        count = len(raw_peak_min)
        
        for i in range(count):
            # Add original values: samples contains average of min and max
            samples.append((raw_peak_min[i] + raw_peak_max[i]) // 2)
            peak_min.append(raw_peak_min[i])
            peak_max.append(raw_peak_max[i])
            
            # Add interpolated values
            if i < count - 1:
                # Interpolated peak_min: average between current min and next min
                interpolated_min = (raw_peak_min[i] + raw_peak_min[i + 1]) // 2
                # Interpolated peak_max: average between current max and next max
                interpolated_max = (raw_peak_max[i] + raw_peak_max[i + 1]) // 2
                # Interpolated sample: average of interpolated min and max
                interpolated = (interpolated_min + interpolated_max) // 2
            else:
                # Last interval: use average of min and max
                interpolated = (raw_peak_min[i] + raw_peak_max[i]) // 2
                interpolated_min = interpolated
                interpolated_max = interpolated
            
            samples.append(interpolated)
            peak_min.append(interpolated_min)
            peak_max.append(interpolated_max)
        
        return samples, peak_min, peak_max

    @staticmethod
    def _process_peak_double_samples(raw_data: bytes, value_bytes: int, total_bytes_per_sample: int) -> Tuple[List[int], List[int], List[int]]:
        """Process double peak mode (paired min/max) with interpolation (no swap needed)."""
        samples = []
        peak_min = []
        peak_max = []
        limit = len(raw_data) - (len(raw_data) % total_bytes_per_sample)
        count = limit // total_bytes_per_sample
        for i in range(count):
            idx = i * total_bytes_per_sample
            min_val = int.from_bytes(raw_data[idx:idx + value_bytes], 'big')
            max_val = int.from_bytes(raw_data[idx + value_bytes:idx + total_bytes_per_sample], 'big')
            samples.append((min_val + max_val) // 2)
            peak_min.append(min_val)
            peak_max.append(max_val)
            
            if i < count - 1:
                next_idx = (i + 1) * total_bytes_per_sample
                next_min = int.from_bytes(raw_data[next_idx:next_idx + value_bytes], 'big')
                next_max = int.from_bytes(raw_data[next_idx + value_bytes:next_idx + total_bytes_per_sample], 'big')
                interpolated_min = (min_val + next_min) // 2
                interpolated_max = (max_val + next_max) // 2
                interpolated = (interpolated_min + interpolated_max) // 2
            else:
                interpolated = (min_val + max_val) // 2
                interpolated_min = interpolated
                interpolated_max = interpolated
            
            samples.append(interpolated)
            peak_min.append(interpolated_min)
            peak_max.append(interpolated_max)
        return samples, peak_min, peak_max

    @staticmethod
    def parse_frame(body: bytes) -> Dict[str, Any]:
        # Body format: [2B attrs][ per-channel: 2B ch_attrs, 2B size, N bytes data ] * channels
        if not body or len(body) < 2:
            return {"channels": 0, "samples": []}
        attrs = int.from_bytes(body[0:2], 'big')
        ch_count = ((attrs >> 6) & 0x3) + 1
        pos = 2
        channels = []
        for ch in range(ch_count):
            if pos + 4 > len(body):
                break
            ch_attrs = int.from_bytes(body[pos:pos+2], 'big'); pos += 2
            size = int.from_bytes(body[pos:pos+2], 'big'); pos += 2
            data = body[pos:pos+size]; pos += size
            channels.append({"attrs": ch_attrs, "size": size, "data": data})

        first_channel = channels[0] if channels else None
        if not first_channel:
            return {"channels": ch_count, "samples": []}

        channel_attrs = first_channel["attrs"]
        sample_format = (channel_attrs >> 8) & 0x07
        fmt_info = OscillClient.SAMPLE_FORMATS.get(sample_format, {"name": "UNKNOWN", "value_bits": 8, "components": 1})
        value_bits = max(1, fmt_info.get("value_bits", 8))
        components = max(1, fmt_info.get("components", 1))
        value_bytes = max(1, value_bits // 8)
        total_bytes_per_sample = value_bytes * components
        raw_data = first_channel["data"]

        samples: List[int] = []
        peak_min: Optional[List[int]] = None
        peak_max: Optional[List[int]] = None

        limit = len(raw_data) - (len(raw_data) % total_bytes_per_sample)
        if sample_format == 0x00:  # AVG
            samples = OscillClient._process_avg_samples(raw_data, limit)
        elif sample_format == 0x01:  # AVG_HIRES
            samples = OscillClient._process_avg_hires_samples(raw_data, limit)
        elif sample_format == 0x02:  # PEAK_INTERLACED
            samples, peak_min, peak_max = OscillClient._process_peak_interlaced_samples(raw_data, value_bytes)
        elif sample_format == 0x03:  # PEAK_DOUBLE
            samples, peak_min, peak_max = OscillClient._process_peak_double_samples(raw_data, value_bytes, total_bytes_per_sample)
        elif sample_format == 0x04:  # NORMAL
            samples = OscillClient._process_normal_samples(raw_data, limit)
        else:
            # Unknown format, fallback to normal
            samples = OscillClient._process_normal_samples(raw_data, limit)

        sample_bits = value_bits
        frame: Dict[str, Any] = {
            "channels": ch_count,
            "samples": samples,
            "sample_format": sample_format,
            "sample_format_label": fmt_info.get("name", "UNKNOWN"),
            "sample_bytes": value_bytes,
            "sample_bits": sample_bits,
            "sample_components": components,
            "frame_attrs": attrs,
            "channel_attrs": channel_attrs,
        }
        if peak_min is not None and peak_max is not None:
            frame["samples_peak_min"] = peak_min
            frame["samples_peak_max"] = peak_max
        return frame

    def get_frame(self) -> Optional[Dict[str, Any]]:
        raw = self.get_data_single()
        if not raw:
            return None
        return self.parse_frame(raw)

    def get_current_status(self) -> Dict[str, Any]:
        # Query key properties and settings
        vnm = self.get_property("VNM")
        vsn = self.get_property("VSN")
        vhw = self.get_property("VHW")
        vsw = self.get_property("VSW")
        # Ensure QS sane
        try:
            self.ensure_qs()
        except Exception:
            pass
        status = {
            "properties": {
                "VNM": (vnm.decode('ascii', 'ignore') if vnm else None),
                "VSN": (vsn.decode('ascii', 'ignore') if vsn else None),
                "VHW": (vhw.decode('ascii', 'ignore') if vhw else None),
                "VSW": (vsw.decode('ascii', 'ignore') if vsw else None),
            },
            "config": {
                "v_div": {"v": self.get_v_div_mV(), "u": "mV"},
                "t_div": {"v": self.get_time_div_ms(), "u": "ms"},
                "v_offset": self.get_offset_raw(),
                "trigger_level": {"v": self.get_trigger_level(), "u": "level"},
                "trigger_mode": {"v": self.get_trigger_mode(), "u": "bits"},
                "rs_mode": {"v": self.get_rs_mode(), "u": "bits"},
            },
        }
        return status

    # ---------- Commands ----------
    def calibrate(self) -> bool:
        assert self.ser is not None
        headers = b""
        if self.conn_id:
            headers += self._build_4byte(CONNECTION_ID, self.conn_id)
        # PUT command 0x72 = "C" (calibration)
        headers += self._build_byte_seq(OSCILL_DATA, b"C")
        self.ser.write(self._build_packet(OBEX_PUT_FINAL, headers))
        opcode, _ = self._read_resp()
        return opcode in (0xA0, 0x90)
