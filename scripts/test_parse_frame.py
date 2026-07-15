#!/usr/bin/env python3
"""
SP_OCL — Standalone hardware-free tests for OscillClient.parse_frame().

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_parse_frame.py`. Prints PASS/FAIL per case, exits
non-zero on any failure. No serial port / hardware is touched: parse_frame is
a pure @staticmethod over a byte buffer, so we synthesize valid OBEX frame
bodies directly.

Frame body layout (from parse_frame):
  [2B frame_attrs][ per channel: 2B channel_attrs, 2B size, <size> bytes data ]*
  - channel count = ((frame_attrs >> 6) & 0x3) + 1   -> use 0x0000 for 1 channel
  - sample_format = (channel_attrs >> 8) & 0x07      -> put format code in bits 8..10
"""

import os
import sys
import types

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'web_oscill'))

# oscill_client imports pyserial at module top for the live-device code paths.
# parse_frame is a pure @staticmethod that never touches the serial port, so for
# a hardware-free test we stub the 'serial' package (and serial.tools.list_ports)
# in sys.modules before importing. This keeps the test runnable without pyserial.
if "serial" not in sys.modules:
    _serial = types.ModuleType("serial")
    _serial.Serial = object  # placeholder; never instantiated in these tests
    _tools = types.ModuleType("serial.tools")
    _list_ports = types.ModuleType("serial.tools.list_ports")
    _list_ports.comports = lambda: []
    _tools.list_ports = _list_ports
    _serial.tools = _tools
    sys.modules["serial"] = _serial
    sys.modules["serial.tools"] = _tools
    sys.modules["serial.tools.list_ports"] = _list_ports

from oscill_client import OscillClient  # noqa: E402

_failures = 0


def check(name, cond):
    global _failures
    status = "PASS" if cond else "FAIL"
    if not cond:
        _failures += 1
    print(f"  [{status}] {name}")


def build_single_channel_body(sample_format_code, data):
    """Build a minimal 1-channel frame body with the given format code + raw data."""
    frame_attrs = 0x0000  # bits 6..7 = 0 -> 1 channel
    channel_attrs = (sample_format_code & 0x07) << 8
    body = frame_attrs.to_bytes(2, 'big')
    body += channel_attrs.to_bytes(2, 'big')
    body += len(data).to_bytes(2, 'big')
    body += bytes(data)
    return body


def test_avg_1byte():
    print("AVG (0x00) 1-byte samples:")
    body = build_single_channel_body(0x00, [10, 20, 30, 40])
    frame = OscillClient.parse_frame(body)
    check("channels == 1", frame["channels"] == 1)
    check("sample_format == 0x00", frame["sample_format"] == 0x00)
    check("sample_format_label == AVG", frame["sample_format_label"] == "AVG")
    check("sample_bytes == 1", frame["sample_bytes"] == 1)
    check("sample_bits == 8", frame["sample_bits"] == 8)
    check("sample_components == 1", frame["sample_components"] == 1)
    check("samples decoded", frame["samples"] == [10, 20, 30, 40])
    check("no peak arrays for AVG", "samples_peak_min" not in frame)


def test_avg_hires_2byte():
    print("AVG_HIRES (0x01) 2-byte big-endian samples:")
    # Values 0x0102=258, 0x00FF=255, 0xABCD=43981 -> big-endian byte stream
    data = [0x01, 0x02, 0x00, 0xFF, 0xAB, 0xCD]
    body = build_single_channel_body(0x01, data)
    frame = OscillClient.parse_frame(body)
    check("sample_format == 0x01", frame["sample_format"] == 0x01)
    check("sample_format_label == AVG_HIRES", frame["sample_format_label"] == "AVG_HIRES")
    check("sample_bytes == 2", frame["sample_bytes"] == 2)
    check("sample_bits == 16", frame["sample_bits"] == 16)
    check("sample_components == 1", frame["sample_components"] == 1)
    check("big-endian decode", frame["samples"] == [258, 255, 43981])


def test_normal_1byte():
    print("NORMAL (0x04) 1-byte samples:")
    body = build_single_channel_body(0x04, [1, 2, 3])
    frame = OscillClient.parse_frame(body)
    check("sample_format == 0x04", frame["sample_format"] == 0x04)
    check("sample_format_label == NORMAL", frame["sample_format_label"] == "NORMAL")
    check("sample_bytes == 1", frame["sample_bytes"] == 1)
    check("samples decoded", frame["samples"] == [1, 2, 3])


def test_peak_double():
    print("PEAK_DOUBLE (0x03) paired min/max, 2 components:")
    # Two min/max pairs: (10,20) and (30,40).
    data = [10, 20, 30, 40]
    body = build_single_channel_body(0x03, data)
    frame = OscillClient.parse_frame(body)
    check("sample_format == 0x03", frame["sample_format"] == 0x03)
    check("sample_components == 2", frame["sample_components"] == 2)
    check("sample_bytes == 1", frame["sample_bytes"] == 1)
    # Expansion/interpolation per _process_peak_double_samples:
    #   i=0: sample avg(10,20)=15; interp avg((10+30)//2,(20+40)//2)=avg(20,30)=25
    #   i=1(last): sample avg(30,40)=35; interp=35
    check("interpolated samples", frame["samples"] == [15, 25, 35, 35])
    check("peak_min present", frame.get("samples_peak_min") == [10, 20, 30, 35])
    check("peak_max present", frame.get("samples_peak_max") == [20, 30, 40, 35])


def test_empty_and_short():
    print("degenerate buffers:")
    check("empty body -> channels 0", OscillClient.parse_frame(b"")["samples"] == [])
    check("too-short body -> channels 0", OscillClient.parse_frame(b"\x00")["samples"] == [])


if __name__ == "__main__":
    print("=" * 60)
    print("SP_OCL parse_frame tests")
    print("=" * 60)
    test_avg_1byte()
    test_avg_hires_2byte()
    test_normal_1byte()
    test_peak_double()
    test_empty_and_short()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} failing case(s))")
        sys.exit(1)
    print("RESULT: PASS (all cases passed)")
