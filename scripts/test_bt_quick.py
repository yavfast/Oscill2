#!/usr/bin/env python3
# [C_BTT / SP_BTT / PL_BTT Phase 7] Quick live check of the Oscill over Bluetooth (RFCOMM/SPP).
#
# Standalone diagnostic — NOT a unit test (requires the scope powered on + OS-paired). It reaches
# the device over a Bluetooth Classic RFCOMM socket and reuses the existing OBEX driver
# (OscillClient) framing unchanged, proving the OBEX-over-BT path end-to-end before the full
# transport refactor lands. It also prototypes SP_BTT_02_07 (resolve_spp_channel) and
# SP_BTT_02_02/03 (RFCOMM read/write, read→b"" on timeout, full-write) via SocketSerial.
#
# Usage:
#   scripts/test_bt_quick.py [--addr XX:XX:XX:XX:XX:XX] [--channel N] [--frame] [--timeout S]
#   OSCILL_BT_ADDR / OSCILL_BT_CHANNEL env vars are honoured as defaults.
#
# Exit codes: 0 = PASS (handshake + property read), 1 = device unreachable, 2 = protocol failure.

import argparse
import os
import re
import socket
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web_oscill"))

from oscill_client import OscillClient  # noqa: E402  (path set above)

DEFAULT_ADDR = "20:13:04:24:20:55"   # Oscill DSO (verified paired to this host)
SPP_UUID_SHORT = "1101"               # Bluetooth Serial Port Profile


# --------------------------------------------------------------------------- #
# SP_BTT_02_07 prototype — resolve the SPP RFCOMM channel via SDP (sdptool).   #
# Resolution order: explicit channel (caller) > SDP query > fallback 1.        #
# --------------------------------------------------------------------------- #
def resolve_spp_channel(address: str) -> int | None:
    """Return the RFCOMM channel of the device's Serial Port service, or None if SDP
    could not run/return (caller then falls back). Mirrors the Windows BT_SearchSPPExServices
    step and SP_BTT_02_07."""
    try:
        out = subprocess.run(
            ["sdptool", "browse", "--tree", address],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  [sdp] sdptool unavailable/timeout ({e.__class__.__name__}); skipping SDP")
        return None
    text = (out.stdout or "") + (out.stderr or "")
    if "Serial Port" not in text and SPP_UUID_SHORT not in text.replace("0x", ""):
        # Try the flat (non-tree) form as a fallback parse.
        try:
            out = subprocess.run(["sdptool", "browse", address],
                                 capture_output=True, text=True, timeout=15)
            text = (out.stdout or "") + (out.stderr or "")
        except Exception:
            pass
    # Find a "Serial Port" service block and its RFCOMM channel.
    channel = None
    in_spp = False
    for line in text.splitlines():
        low = line.lower()
        if "service name" in low and "serial port" in low:
            in_spp = True
        elif "service name" in low:
            in_spp = False
        m = re.search(r"[Cc]hannel[:/]?\s*(\d+)", line)
        if m and (in_spp or channel is None):
            ch = int(m.group(1))
            if in_spp:
                return ch
            channel = ch  # remember first channel seen as a weak fallback
    return channel


# --------------------------------------------------------------------------- #
# SP_BTT_02_02/03/04 prototype — a serial.Serial-compatible view over an       #
# RFCOMM socket, so the unchanged OBEX driver can drive it.                    #
# --------------------------------------------------------------------------- #
class SocketSerial:
    """Minimal pyserial-compatible shim over a connected RFCOMM socket. Implements only
    what OscillClient touches: write/read/timeout/reset_*_buffer/is_open/close/baudrate."""

    def __init__(self, sock: socket.socket, timeout: float = 3.0):
        self._sock = sock
        self._timeout = timeout
        self.is_open = True
        self.baudrate = 115200  # accepted + ignored (RFCOMM negotiates its own rate)

    @property
    def timeout(self) -> float:
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        self._timeout = value

    def write(self, data: bytes) -> int:
        # SP_BTT_02_03: all bytes written before returning.
        self._sock.sendall(data)
        return len(data)

    def read(self, n: int) -> bytes:
        # SP_BTT_02_02 / DEC_04: return up to n bytes; b"" on timeout (never raise on timeout).
        self._sock.settimeout(self._timeout)
        try:
            return self._sock.recv(n)
        except socket.timeout:
            return b""

    def reset_input_buffer(self) -> None:
        self._sock.setblocking(False)
        try:
            while True:
                if not self._sock.recv(4096):
                    break
        except (BlockingIOError, socket.timeout, OSError):
            pass
        finally:
            self._sock.setblocking(True)

    def reset_output_buffer(self) -> None:
        pass  # RFCOMM has no host-side output buffer we control

    def close(self) -> None:
        self.is_open = False
        try:
            self._sock.close()
        except OSError:
            pass


def _decode(b) -> str:
    return b.decode("ascii", "ignore").strip() if b else "—"


def main() -> int:
    ap = argparse.ArgumentParser(description="Quick Oscill-over-Bluetooth check")
    ap.add_argument("--addr", default=os.environ.get("OSCILL_BT_ADDR", DEFAULT_ADDR),
                    help="device BD_ADDR (default: Oscill DSO / OSCILL_BT_ADDR)")
    ap.add_argument("--channel", type=int,
                    default=(int(os.environ["OSCILL_BT_CHANNEL"])
                             if os.environ.get("OSCILL_BT_CHANNEL") else None),
                    help="RFCOMM channel (default: resolve via SDP, else 1)")
    ap.add_argument("--frame", action="store_true", help="also acquire one frame")
    ap.add_argument("--timeout", type=float, default=5.0, help="socket/read timeout (s)")
    args = ap.parse_args()

    print(f"=== Oscill BT quick check → {args.addr} ===")

    # 1) Channel resolution ---------------------------------------------------
    channel = args.channel
    if channel is None:
        channel = resolve_spp_channel(args.addr)
        if channel is None:
            channel = 1
            print(f"  [sdp] no SPP channel resolved → fallback to channel {channel}")
        else:
            print(f"  [sdp] SPP resolved to RFCOMM channel {channel}")
    else:
        print(f"  [cfg] using explicit channel {channel}")

    # 2) RFCOMM connect -------------------------------------------------------
    t0 = time.time()
    try:
        sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM,
                             socket.BTPROTO_RFCOMM)
        # The Oscill requires INSECURE RFCOMM (no auth/encryption elevation) — matches the
        # old Android app's createInsecureRfcommSocket. Without BT_SECURITY_LOW the kernel
        # tries to elevate security on connect and the device stalls → timeout.
        _SOL_BLUETOOTH, _BT_SECURITY, _BT_SECURITY_LOW = 274, 4, 1
        sock.setsockopt(_SOL_BLUETOOTH, _BT_SECURITY,
                        struct.pack("BB", _BT_SECURITY_LOW, 0))
        sock.settimeout(args.timeout)
        sock.connect((args.addr, channel))
    except OSError as e:
        print(f"  ✗ RFCOMM connect failed: {e}")
        print("    → Is the scope powered on and connectable? Pair it in the OS first "
              "(bluetoothctl pair/trust). This mirrors the 'Host is down' precondition.")
        return 1
    print(f"  ✓ RFCOMM connected (channel {channel}, {1000*(time.time()-t0):.0f} ms)")

    # 3) OBEX handshake over the socket (reuse OscillClient framing) -----------
    client = OscillClient(port="bt", baud=115200, timeout=args.timeout)
    client.ser = SocketSerial(sock, timeout=args.timeout)  # bypass serial open()
    rc = 0
    try:
        client.reset()          # OBEX ABORT + drain
        client.connect()        # OBEX CONNECT — must return 0xA0
        print(f"  ✓ OBEX CONNECT ok (conn_id={client.conn_id.hex() if client.conn_id else 'none'})")

        # 4) Read identity/version properties (proves the full request/response path)
        props = {name: _decode(client.get_property(name))
                 for name in ("VNM", "VSN", "VHW", "VSW", "VSD", "VSI")}
        print("  device properties:")
        for k, v in props.items():
            print(f"    {k} = {v}")

        if not any(v not in ("—", "") for v in props.values()):
            print("  ✗ no property returned — protocol path not confirmed")
            rc = 2

        # 5) Optional single frame
        if args.frame and rc == 0:
            try:
                client.set_cpu_freq_mhz(70)
                client.ensure_qs()
                frame = client.get_frame()
                if frame and frame.get("samples"):
                    s = frame["samples"]
                    print(f"  ✓ frame: {len(s)} samples ({frame.get('sample_format_label')}), "
                          f"first={s[:8]}")
                else:
                    print("  ! frame acquisition returned no samples (check trigger/config)")
            except Exception as e:
                print(f"  ! frame acquisition error: {e}")
    except Exception as e:
        print(f"  ✗ OBEX handshake failed: {e}")
        rc = 2
    finally:
        try:
            client.ser.close()
        except Exception:
            pass

    print("=== PASS ===" if rc == 0 else f"=== FAIL (rc={rc}) ===")
    return rc


if __name__ == "__main__":
    sys.exit(main())
