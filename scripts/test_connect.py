#!/usr/bin/env python3
"""
Test script to check connection to the oscilloscope device via USB serial and fetch device status.
"""

import serial
import serial.tools.list_ports
import sys
import time
from typing import Dict, List, Tuple, Optional

# Device VID and PID
VENDOR_ID = 0x10c4  # Silicon Labs
PRODUCT_ID = 0x840E

# OBEX opcodes
OBEX_CONNECT = 0x80
OBEX_GET_FINAL = 0x83
OBEX_ABORT = 0xFF

# OBEX headers
OSCILL_PROPERTY = 0x70  # Byte Sequence (0x40 class) -> needs 2-byte length
OSCILL_REGISTRY = 0x71
OSCILL_DATA = 0x72
OSCILL_1BYTE = 0xB1  # 1 byte (0x80 class)
OSCILL_2BYTE = 0xF0  # 4-byte container for 2B values (0xC0 class)
OSCILL_4BYTE = 0xF1  # 4 bytes (0xC0 class)
CONNECTION_ID = 0xCB  # 4 bytes (0xC0 class)


def find_device_port() -> Optional[str]:
    """Find the USB serial port for the device."""
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if port.vid == VENDOR_ID and port.pid == PRODUCT_ID:
            return port.device
    return None


def build_byte_seq_header(header_id: int, payload: bytes) -> bytes:
    # For 0x40-class headers, include 2-byte length of (id + len + payload)
    length = len(payload) + 3
    return bytes([header_id]) + length.to_bytes(2, "big") + payload


def build_4byte_header(header_id: int, payload4: bytes) -> bytes:
    if len(payload4) != 4:
        raise ValueError("4-byte header requires exactly 4 bytes payload")
    return bytes([header_id]) + payload4


def build_1byte_header(header_id: int, value: int) -> bytes:
    return bytes([header_id, value & 0xFF])


def build_packet(opcode: int, headers: bytes = b"") -> bytes:
    total_len = 3 + len(headers)
    return bytes([opcode]) + total_len.to_bytes(2, "big") + headers


def read_exact(ser: serial.Serial, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = ser.read(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def read_obex_response(ser: serial.Serial) -> Tuple[int, bytes]:
    # Read opcode + length first
    head = read_exact(ser, 3)
    if len(head) < 3:
        raise IOError("Timeout reading OBEX response header")
    opcode = head[0]
    length = int.from_bytes(head[1:3], "big")
    if length < 3:
        raise IOError(f"Invalid OBEX length: {length}")
    rest = read_exact(ser, length - 3)
    if len(rest) != length - 3:
        raise IOError("Timeout reading full OBEX response body")
    return opcode, rest


def parse_obex_headers(data: bytes) -> Dict[int, List[bytes]]:
    i = 0
    out: Dict[int, List[bytes]] = {}
    while i < len(data):
        header_id = data[i]
        cls = header_id & 0xC0
        if cls == 0x40:  # Byte Sequence: id + 2B len + payload
            if i + 3 > len(data):
                break
            length = int.from_bytes(data[i + 1:i + 3], "big")
            payload_len = max(0, length - 3)
            start = i + 3
            end = start + payload_len
            payload = data[start:end] if end <= len(data) else b""
            i = end
        elif cls == 0x80:  # 1 byte quantity
            if i + 2 > len(data):
                break
            payload = bytes([data[i + 1]])
            i += 2
        elif cls == 0xC0:  # 4 byte quantity
            if i + 5 > len(data):
                break
            payload = data[i + 1:i + 5]
            i += 5
        else:
            # 0x00 class (Unicode) — not used here; parse similarly to 0x40
            if i + 3 > len(data):
                break
            length = int.from_bytes(data[i + 1:i + 3], "big")
            payload_len = max(0, length - 3)
            start = i + 3
            end = start + payload_len
            payload = data[start:end] if end <= len(data) else b""
            i = end
        out.setdefault(header_id, []).append(payload)
    return out


def obex_abort(ser: serial.Serial) -> None:
    # Send ABORT without headers (device-specific reset, per Java reset())
    ser.write(build_packet(OBEX_ABORT))
    time.sleep(0.5)
    # Drain any bytes the device might have sent
    ser.timeout = 0.05
    while ser.read(256):
        pass
    ser.timeout = 2


def obex_connect(ser: serial.Serial) -> Tuple[int, Dict[int, List[bytes]]]:
    # Version 0x10, Flags 0x00, Max Rx packet size (use 0x1000 like Android transport)
    max_rx = 0x1000
    req_tail = bytes([0x10, 0x00]) + max_rx.to_bytes(2, "big")
    ser.write(build_packet(OBEX_CONNECT, req_tail))
    opcode, body = read_obex_response(ser)
    if opcode != 0xA0:  # Success
        raise IOError(f"Connect failed, opcode=0x{opcode:02x}")
    # body: version|flags|max_tx(2B) + optional headers
    # Skip 4 bytes then parse remaining headers
    extra = body[4:] if len(body) >= 4 else b""
    headers = parse_obex_headers(extra)
    return opcode, headers


def obex_get_property(ser: serial.Serial, name: str, conn_id: Optional[bytes]) -> Optional[bytes]:
    headers = b""
    if conn_id is not None and len(conn_id) == 4:
        headers += build_4byte_header(CONNECTION_ID, conn_id)
    headers += build_byte_seq_header(OSCILL_PROPERTY, name.encode("ascii"))
    ser.write(build_packet(OBEX_GET_FINAL, headers))
    opcode, body = read_obex_response(ser)
    if opcode not in (0xA0, 0x90):  # Success or Continue
        return None
    hdrs = parse_obex_headers(body)
    # Prefer 0xF1 (4 bytes)
    if OSCILL_4BYTE in hdrs and hdrs[OSCILL_4BYTE]:
        return hdrs[OSCILL_4BYTE][-1]
    # Sometimes returned as 0xF0 (packed 2B into 4B)
    if OSCILL_2BYTE in hdrs and hdrs[OSCILL_2BYTE]:
        return hdrs[OSCILL_2BYTE][-1]
    return None


def test_connection() -> bool:
    device_port = find_device_port()
    if not device_port:
        print("Error: Device not found. Make sure the device is connected via USB.")
        return False

    print(f"Found device on port: {device_port}")

    try:
        ser = serial.Serial(device_port, 115200, timeout=2)
        print("Serial port opened successfully.")

        # Reset first (matches Java: reset() before connect())
        print("Sending device reset (ABORT)...")
        obex_abort(ser)

        print("Sending OBEX CONNECT...")
        _, connect_headers = obex_connect(ser)
        conn_id = None
        if CONNECTION_ID in connect_headers and connect_headers[CONNECTION_ID]:
            conn_id = connect_headers[CONNECTION_ID][-1]
            print(f"Connection ID: {conn_id.hex()}")

        print("Connection established. Fetching device information...\n")

        def read_ascii4(label: str, prop: str):
            val = obex_get_property(ser, prop, conn_id)
            if val:
                try:
                    text = val.decode("ascii", errors="ignore").rstrip("\x00")
                except Exception:
                    text = val.hex()
                print(f"{label}: {text}")
            else:
                print(f"{label}: <unavailable>")

        read_ascii4("Device ID", "VNM")
        read_ascii4("Serial Number", "VSN")
        read_ascii4("Hardware Version", "VHW")
        read_ascii4("Software Version", "VSW")

        return True

    except serial.SerialException as e:
        print(f"Serial error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print("Serial port closed.")
        except Exception:
            pass


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)