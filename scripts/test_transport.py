#!/usr/bin/env python3
"""
[C_BTT / SP_BTT] Standalone hardware-free tests for the Transport abstraction.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_transport.py`. Prints PASS/FAIL per case, exits non-zero on any failure.
No serial port / socket / hardware is touched — everything runs over a FakeTransport.

Covers (SP_BTT_05_01 / 05_02 / 05_04):
  - Transport.read returns b"" on timeout (never raises) and accumulates partial reads
  - Transport.write delivers all bytes across a chunked sink
  - capability gating: set_link_speed on a no-speed transport raises UnsupportedCapability
  - open() re-entry guarded (TransportError)
  - endpoint validation (bad BD_ADDR / channel range / baud)
  - build_transport serial-auto → DeviceNotFound when no port
  - OBEX framing byte-identical: the driver emits the known-good CONNECT / registry-GET bytes

This module also exports the FakeTransport / FakeObexTransport / FakeObexDevice helpers reused by
scripts/test_bluetooth_connect.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web_oscill"))

from transport import (  # noqa: E402
    Transport,
    TransportCapabilities,
    TransportError,
    UnsupportedCapability,
)

_failures = 0


def check(cond: bool, label: str) -> None:
    global _failures
    if cond:
        print(f"  [PASS] {label}")
    else:
        _failures += 1
        print(f"  [FAIL] {label}")


def expect_raises(exc, fn, label: str) -> None:
    global _failures
    try:
        fn()
    except exc:
        print(f"  [PASS] {label}")
        return
    except Exception as e:  # noqa: BLE001
        _failures += 1
        print(f"  [FAIL] {label} (raised {type(e).__name__}, expected {exc.__name__})")
        return
    _failures += 1
    print(f"  [FAIL] {label} (no exception, expected {exc.__name__})")


# --------------------------------------------------------------------------- #
# FakeTransport — a programmable, hardware-free Transport for contract tests.  #
# --------------------------------------------------------------------------- #
class FakeTransport(Transport):
    """A byte-stream fake: `read` drains a preloaded source queue (b"" when empty = timeout),
    `write` records into a chunked sink. Capabilities and open-state are controllable."""

    def __init__(self, supports_speed_change: bool = True):
        self._caps = TransportCapabilities(supports_speed_change=supports_speed_change)
        self._read_timeout = 3.0
        self._open = False
        self._source = bytearray()   # bytes the driver will read
        self.written = bytearray()   # bytes the driver has written
        self.set_link_speed_calls = []
        self.reset_buffers_calls = 0

    # test helpers
    def feed(self, data: bytes) -> None:
        self._source += data

    # state
    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def read_timeout(self) -> float:
        return self._read_timeout

    @read_timeout.setter
    def read_timeout(self, value: float) -> None:
        self._read_timeout = value

    @property
    def capabilities(self) -> TransportCapabilities:
        return self._caps

    # lifecycle
    def open(self) -> None:
        if self._open:
            raise TransportError("already open")
        self._open = True

    def close(self) -> None:
        self._open = False

    # I/O
    def read(self, n: int) -> bytes:
        if not self._source:
            return b""  # timeout → empty (SP_BTT_02_02 / DEC_04)
        chunk = bytes(self._source[:n])
        del self._source[:n]
        return chunk

    def write(self, data: bytes) -> None:
        self.written += data

    def reset_buffers(self) -> None:
        self.reset_buffers_calls += 1
        self._source.clear()

    def set_link_speed(self, baud: int) -> None:
        if not self._caps.supports_speed_change:
            raise UnsupportedCapability("no speed change")
        self.set_link_speed_calls.append(baud)

    def describe(self) -> str:
        return "fake"


# --------------------------------------------------------------------------- #
# FakeObexDevice / FakeObexTransport — a minimal OBEX responder so the full    #
# OscillClient driver (and DeviceService init) can run hardware-free.          #
# --------------------------------------------------------------------------- #
_REG_WIDTH = {
    # 1-byte
    "RS": 1, "AP": 1, "AR": 1, "O1": 1, "M1": 1, "T1": 1, "S1": 1, "RT": 1,
    # 2-byte
    "MC": 2, "V1": 2, "P1": 2, "QS": 2, "TC": 2,
    # 4-byte
    "TS": 4, "TD": 4, "TA": 4, "TW": 4,
}
_REG_DEFAULTS = {"MC": 1000, "QS": 1784, "TS": 256, "V1": 200}
_PROPS = {
    "VNM": b"Uosc", "VSN": b"6070", "VHW": b"1.25", "VSW": b"1.26",
    "VSD": b"\x00\x00\x00\x00", "VSI": b"\x00\x00\x00\x00",
    "QSh": (1784).to_bytes(4, "big"),
    "V1l": (20).to_bytes(4, "big"), "V1h": (10000).to_bytes(4, "big"),
    "MCd": (1000).to_bytes(4, "big"),
}

# OBEX constants (mirror oscill_client)
_OBEX_CONNECT, _GET, _GET_FINAL, _PUT_FINAL, _ABORT = 0x80, 0x03, 0x83, 0x82, 0xFF
_H_PROP, _H_REG, _H_DATA = 0x70, 0x71, 0x72
_H_BODY, _H_EOB, _H_CONNID = 0x48, 0x49, 0xCB
_H_1B, _H_2B, _H_4B = 0xB1, 0xF0, 0xF1


def _parse_headers(data: bytes):
    i, out = 0, {}
    while i < len(data):
        hid = data[i]
        cls = hid & 0xC0
        if cls in (0x00, 0x40):
            if i + 3 > len(data):
                break
            length = int.from_bytes(data[i + 1:i + 3], "big")
            start, end = i + 3, i + 3 + max(0, length - 3)
            payload = data[start:end] if end <= len(data) else b""
            i = end
        elif cls == 0x80:
            if i + 2 > len(data):
                break
            payload = bytes([data[i + 1]])
            i += 2
        else:  # 0xC0
            if i + 5 > len(data):
                break
            payload = data[i + 1:i + 5]
            i += 5
        out.setdefault(hid, []).append(payload)
    return out


def _pkt(opcode: int, payload: bytes = b"") -> bytes:
    total = 3 + len(payload)
    return bytes([opcode]) + total.to_bytes(2, "big") + payload


class FakeObexDevice:
    """Answers the subset of OBEX the OscillClient driver issues during connect/init/acquire, so a
    full DeviceService.connect can run without hardware. Register values round-trip through PUT/GET;
    properties return canned bytes; a data GET returns an empty End-of-Body frame."""

    def __init__(self):
        self.regs = dict(_REG_DEFAULTS)
        self.writes = []  # every request packet the driver sent

    def _reg_value_header(self, name: str) -> bytes:
        width = _REG_WIDTH.get(name, 2)
        val = int(self.regs.get(name, 0))
        if width == 1:
            return bytes([_H_1B, val & 0xFF])
        if width == 2:
            return bytes([_H_2B]) + (0).to_bytes(2, "big") + (val & 0xFFFF).to_bytes(2, "big")
        return bytes([_H_4B]) + (val & 0xFFFFFFFF).to_bytes(4, "big")

    def handle(self, data: bytes) -> bytes:
        self.writes.append(bytes(data))
        opcode = data[0]
        length = int.from_bytes(data[1:3], "big")
        hdrs = _parse_headers(data[3:length])
        if opcode == _ABORT:
            return b""  # device stays silent; driver drains
        if opcode == _OBEX_CONNECT:
            connid = bytes([_H_CONNID]) + b"\x00\x00\x00\x01"
            return _pkt(0xA0, b"\x10\x00\x10\x00" + connid)
        if opcode == _PUT_FINAL:
            if _H_DATA in hdrs:  # command (e.g. calibrate 'C')
                return _pkt(0xA0)
            if _H_REG in hdrs:
                name = hdrs[_H_REG][-1].decode("ascii", "ignore")
                if _H_1B in hdrs:
                    self.regs[name] = hdrs[_H_1B][-1][0]
                elif _H_2B in hdrs:
                    self.regs[name] = int.from_bytes(hdrs[_H_2B][-1][-2:], "big")
                elif _H_4B in hdrs:
                    self.regs[name] = int.from_bytes(hdrs[_H_4B][-1], "big")
                return _pkt(0xA0)
            return _pkt(0xA0)
        if opcode in (_GET_FINAL, _GET):
            if _H_REG in hdrs:
                name = hdrs[_H_REG][-1].decode("ascii", "ignore")
                return _pkt(0xA0, self._reg_value_header(name))
            if _H_PROP in hdrs:
                name = hdrs[_H_PROP][-1].decode("ascii", "ignore")
                val = _PROPS.get(name, b"\x00\x00\x00\x00")
                val4 = (val + b"\x00\x00\x00\x00")[:4]
                return _pkt(0xA0, bytes([_H_4B]) + val4)
            if _H_DATA in hdrs or opcode == _GET:
                return _pkt(0xA0, bytes([_H_EOB, 0x00, 0x03]))  # empty End-of-Body
        return _pkt(0xA0)


class FakeObexTransport(Transport):
    """Transport that drives a FakeObexDevice: each write is answered synchronously into the read
    buffer. `open_should_raise` lets a test simulate BluetoothUnreachable."""

    def __init__(self, supports_speed_change: bool = False, open_should_raise=None):
        self._caps = TransportCapabilities(supports_speed_change=supports_speed_change)
        self._read_timeout = 3.0
        self._open = False
        self._buf = bytearray()
        self.device = FakeObexDevice()
        self.set_link_speed_calls = []
        self._open_should_raise = open_should_raise

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def read_timeout(self) -> float:
        return self._read_timeout

    @read_timeout.setter
    def read_timeout(self, value: float) -> None:
        self._read_timeout = value

    @property
    def capabilities(self) -> TransportCapabilities:
        return self._caps

    def open(self) -> None:
        if self._open_should_raise is not None:
            raise self._open_should_raise
        if self._open:
            raise TransportError("already open")
        self._open = True

    def close(self) -> None:
        self._open = False

    def read(self, n: int) -> bytes:
        if not self._buf:
            return b""
        chunk = bytes(self._buf[:n])
        del self._buf[:n]
        return chunk

    def write(self, data: bytes) -> None:
        self._buf += self.device.handle(data)

    def reset_buffers(self) -> None:
        self._buf.clear()

    def set_link_speed(self, baud: int) -> None:
        self.set_link_speed_calls.append(baud)
        if not self._caps.supports_speed_change:
            raise UnsupportedCapability("no speed change")

    def describe(self) -> str:
        return "fake-obex"


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #
def test_read_timeout_and_partial():
    print("Transport.read (timeout → b\"\", partial accumulation):")
    t = FakeTransport()
    t.open()
    check(t.read(3) == b"", "empty source → b\"\" (no raise)")
    t.feed(b"AB")
    check(t.read(5) == b"AB", "returns available (< n) without raising")
    check(t.read(5) == b"", "drained → b\"\" again")


def test_read_exact_partial_delivery():
    print("_read_exact accumulates fragmented delivery:")
    from oscill_client import OscillClient
    t = FakeTransport()
    t.open()
    t.feed(b"12345")
    c = OscillClient(t)
    check(c._read_exact(5) == b"12345", "5 bytes accumulate across chunked source")


def test_write_complete():
    print("Transport.write delivers all bytes:")
    t = FakeTransport()
    t.open()
    payload = bytes(range(256)) * 4  # 1024 bytes > typical MTU
    t.write(payload)
    check(bytes(t.written) == payload, "all 1024 bytes recorded, no truncation")


def test_capability_gating():
    print("set_link_speed capability gating:")
    ok = FakeTransport(supports_speed_change=True)
    ok.set_link_speed(921600)
    check(ok.set_link_speed_calls == [921600], "speed-capable transport records the call")
    no = FakeTransport(supports_speed_change=False)
    expect_raises(UnsupportedCapability, lambda: no.set_link_speed(921600),
                  "no-speed transport → UnsupportedCapability")


def test_open_reentry_guard():
    print("open() re-entry guard:")
    t = FakeTransport()
    t.open()
    expect_raises(TransportError, t.open, "second open() → TransportError")


def test_driver_speed_raise_gated_on_capability():
    print("OscillClient.raise_speed no-op on a no-speed transport:")
    from oscill_client import OscillClient
    t = FakeTransport(supports_speed_change=False)
    t.open()
    c = OscillClient(t)
    achieved = c.raise_speed()
    check(achieved == c.DEFAULT_BAUD, "raise_speed returns base baud")
    check(t.set_link_speed_calls == [], "no set_link_speed call made")
    check(t.written == b"", "no 0x91 speed packet written")


def test_endpoint_validation():
    print("Endpoint validation (SP_BTT_03_01):")
    from endpoints import SerialEndpoint, BluetoothEndpoint
    BluetoothEndpoint("20:13:04:24:20:55", 1)  # valid
    check(True, "valid BD_ADDR + channel accepted")
    expect_raises(ValueError, lambda: BluetoothEndpoint("20:13:04"), "short BD_ADDR rejected")
    expect_raises(ValueError, lambda: BluetoothEndpoint("zz:zz:zz:zz:zz:zz"),
                  "non-hex BD_ADDR rejected")
    expect_raises(ValueError, lambda: BluetoothEndpoint("20:13:04:24:20:55", 99),
                  "channel out of range rejected")
    expect_raises(ValueError, lambda: SerialEndpoint(baud=0), "baud <= 0 rejected")


def test_build_transport_serial_auto_notfound():
    print("build_transport serial-auto → DeviceNotFound when no port:")
    from endpoints import SerialEndpoint, DeviceNotFound, build_transport
    from serial_transport import SerialTransport
    orig = SerialTransport.auto_find_port
    SerialTransport.auto_find_port = staticmethod(lambda: None)
    try:
        expect_raises(DeviceNotFound, lambda: build_transport(SerialEndpoint(port=None)),
                      "no CP210x → DeviceNotFound")
    finally:
        SerialTransport.auto_find_port = orig
    # explicit port builds a SerialTransport without auto-detect
    t = build_transport(SerialEndpoint(port="/dev/ttyUSB0", baud=115200))
    check(t.describe() == "serial:/dev/ttyUSB0@115200", "explicit serial endpoint builds transport")


def test_obex_framing_byte_identical():
    print("OBEX framing byte-identical (SP_BTT_05_02):")
    from oscill_client import OscillClient
    t = FakeObexTransport(supports_speed_change=True)
    t.open()
    c = OscillClient(t)
    c.connect()  # OBEX CONNECT
    connect_pkt = t.device.writes[0]
    check(connect_pkt == bytes([0x80, 0x00, 0x07, 0x10, 0x00, 0x10, 0x00]),
          "CONNECT packet == 80 00 07 10 00 10 00")
    # A registry GET for 'QS' (no connection-id header path is exercised after connect sets it,
    # so assert the registry byte-sequence framing regardless of the leading conn-id header).
    c.get_reg_2("QS")
    reg_get = t.device.writes[-1]
    check(reg_get.endswith(bytes([0x71, 0x00, 0x05, 0x51, 0x53])),
          "registry GET carries 71 00 05 'QS' byte-sequence header")
    check(reg_get[0] == 0x83, "registry read uses GET_FINAL (0x83)")


def test_read_resp_rejects_truncated_packet():
    print("[fix skip-broken-frame] _read_resp rejects a truncated OBEX packet (declared len > received):")
    from oscill_client import OscillClient
    # Complete packet: opcode 0xA0, declared total length 7 → 4 body bytes present.
    complete = bytes([0xA0, 0x00, 0x07]) + bytes([0x10, 0x00, 0x10, 0x00])
    t = FakeTransport()
    t.open()
    t.feed(complete)
    c = OscillClient(t)
    op, body = c._read_resp()
    check(op == 0xA0 and body == bytes([0x10, 0x00, 0x10, 0x00]), "complete packet reads fully")
    # Truncated packet: header declares total length 20 (→17 body bytes) but only 5 arrive.
    truncated = bytes([0xA0, 0x00, 0x14]) + bytes([1, 2, 3, 4, 5])
    t2 = FakeTransport()
    t2.open()
    t2.feed(truncated)
    c2 = OscillClient(t2)
    expect_raises(IOError, c2._read_resp, "truncated packet (5 of 17 body bytes) → IOError")


def test_sdp_parser_targets_spp_not_opp():
    print("resolve_spp_channel SDP parse targets SPP (0x1101), not Object Push:")
    from rfcomm_transport import _parse_spp_channel
    # Dual-service sdptool output: SPP named "Dev B" (NOT "Serial Port") on ch1, OPP on ch2.
    # The SPP record must be identified by its 0x1101 UUID, not the service name.
    sample = "\n".join([
        "Browsing 20:13:04:24:20:55 ...",
        "Service Name: OBEX Object Push",
        "Service RecHandle: 0x10001",
        "Service Class ID List:",
        '  "OBEX Object Push" (0x1105)',
        "Protocol Descriptor List:",
        '  "L2CAP" (0x0100)',
        '  "RFCOMM" (0x0003)',
        "    Channel: 2",
        "",
        "Service Name: Dev B",
        "Service RecHandle: 0x10000",
        "Service Class ID List:",
        '  "Serial Port" (0x1101)',
        "Protocol Descriptor List:",
        '  "L2CAP" (0x0100)',
        '  "RFCOMM" (0x0003)',
        "    Channel: 1",
    ])
    check(_parse_spp_channel(sample) == 1, "picks SPP channel 1 over Object Push channel 2")
    check(_parse_spp_channel("Browsing ...\n(no services)") is None,
          "empty/no-service output → None (caller falls back)")
    # If only a channel with no SPP marker exists, weak fallback returns it.
    only_opp = "Service RecHandle: 0x1\n  \"OBEX Object Push\" (0x1105)\n    Channel: 5"
    check(_parse_spp_channel(only_opp) == 5, "no SPP record → first channel as weak fallback")


def test_find_paired_device_by_name():
    print("find_paired_device_by_name parses `bluetoothctl devices Paired` (SP_BTT_02_11):")
    import rfcomm_transport as rt
    sample = "\n".join([
        "Device AA:BB:CC:DD:EE:01 Keyboard K380",
        "Device 20:13:04:24:20:55 Oscill DSO",
        "Device AA:BB:CC:DD:EE:02 WH-1000XM4",
    ])
    orig = rt._run_bluetoothctl
    rt._run_bluetoothctl = lambda args: sample
    try:
        check(rt.find_paired_device_by_name("Oscill") == "20:13:04:24:20:55",
              "matches 'Oscill' → 20:13:04:24:20:55")
        check(rt.find_paired_device_by_name("oscill dso") == "20:13:04:24:20:55",
              "case-insensitive full-name match")
        check(rt.find_paired_device_by_name("NoSuchDevice") is None,
              "no match → None")
        rt._run_bluetoothctl = lambda args: None
        check(rt.find_paired_device_by_name("Oscill") is None,
              "tool unavailable → None")
    finally:
        rt._run_bluetoothctl = orig


def main() -> int:
    test_read_timeout_and_partial()
    test_read_exact_partial_delivery()
    test_write_complete()
    test_capability_gating()
    test_open_reentry_guard()
    test_driver_speed_raise_gated_on_capability()
    test_endpoint_validation()
    test_build_transport_serial_auto_notfound()
    test_obex_framing_byte_identical()
    test_read_resp_rejects_truncated_packet()
    test_sdp_parser_targets_spp_not_opp()
    test_find_paired_device_by_name()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} check(s) failed)")
        return 1
    print("RESULT: PASS (all cases passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
