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

class OscillClient:
    SAMPLES_PER_DIV = 32
    H_DIVS = 8

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
        # Cached values
        self._cpu_tick_10ps: Optional[int] = None  # machine cycle length in 10ps units

    def open(self):
        self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        finally:
            self.ser = None
            self.conn_id = None

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
            try:
                # Estimated acquisition time ~ QS * sample_period
                qs = self.get_reg_2('QS')
                sample_s = self.get_sample_period_ps() / 1e12
                est = float(qs) * float(sample_s)
                # Add a small margin and clamp to a reasonable cap
                wait_s = min(max(est * 1.05, 0.0), 3.0)
            except Exception:
                # Fallback heuristic
                try:
                    tdiv = self.get_time_div_ms() / 1000
                    if tdiv >= 0.02:
                        wait_s = min(tdiv, 0.5)
                except Exception:
                    pass
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
        # Invalidate cache
        self._cpu_tick_10ps = None
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
        return self.set_reg_4('TS', ts_native, signed=False)

    def get_sample_period_ps(self) -> float:
        ts = self.get_ts_native()
        cpu_10ps = self.get_cpu_tick_10ps()
        # ts is in MC*256; MC in 10ps; so sample_ps = ts * (cpu_10ps*10) / 256
        sample_ps = (ts * (cpu_10ps * 10.0)) / 256.0
        return sample_ps

    def set_time_div_ms(self, t_div_ms: float) -> float:
        # sample period = t_div_ms / SAMPLES_PER_DIV
        sample_ps = max(1, (float(t_div_ms) * 1e9) / self.SAMPLES_PER_DIV)
        cpu_ps = self.get_cpu_tick_10ps() * 10.0
        ts_native = int(round(sample_ps * 256.0 / cpu_ps))
        self.set_ts_native(ts_native)
        return self.get_time_div_ms()

    def get_time_div_ms(self) -> float:
        return (self.get_sample_period_ps() * self.SAMPLES_PER_DIV) / 1e9



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
        return self.set_reg_2('TC', value, signed=False)

    def ensure_qs(self, total_samples: Optional[int] = None) -> int:
        total = total_samples or (self.SAMPLES_PER_DIV * self.H_DIVS)
        return self.set_reg_2('QS', total, signed=False)

    # ---------- Frame parsing ----------
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
        if sample_format == 0x02:
            # Peak interlaced: alternating min/max values in the data stream
            peak_min = []
            peak_max = []
            stride = value_bytes * 2
            limit = len(raw_data) - (len(raw_data) % stride)
            for i in range(0, limit, stride):
                lo_bytes = raw_data[i:i + value_bytes]
                hi_bytes = raw_data[i + value_bytes:i + stride]
                if len(lo_bytes) < value_bytes or len(hi_bytes) < value_bytes:
                    break
                lo_val = int.from_bytes(lo_bytes, 'big')
                hi_val = int.from_bytes(hi_bytes, 'big')
                peak_min.append(lo_val)
                peak_max.append(hi_val)
                samples.append((lo_val + hi_val) // 2)
        elif components == 1:
            if value_bytes == 2:
                samples = [
                    int.from_bytes(raw_data[i:i + value_bytes], 'big')
                    for i in range(0, limit, value_bytes)
                ]
            else:
                samples = list(raw_data[:limit])
        else:
            peak_min = []
            peak_max = []
            for i in range(0, limit, total_bytes_per_sample):
                first_chunk = raw_data[i:i + value_bytes]
                second_chunk = raw_data[i + value_bytes:i + 2 * value_bytes]
                if len(first_chunk) < value_bytes or len(second_chunk) < value_bytes:
                    break
                first_val = int.from_bytes(first_chunk, 'big')
                second_val = int.from_bytes(second_chunk, 'big')
                peak_min.append(first_val)
                peak_max.append(second_val)
                samples.append((first_val + second_val) // 2)

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
                "offset": {"v": self.get_offset_volts(), "u": "V"},
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
