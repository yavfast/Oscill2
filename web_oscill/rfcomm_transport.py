# [C_BTT / SP_BTT_02_02..07] RfcommTransport — the Bluetooth Classic (RFCOMM/SPP) realization of
# Transport, plus SPP channel resolution.
#
# The link is a stdlib AF_BLUETOOTH / BTPROTO_RFCOMM socket (no pybluez, no /dev/rfcomm bind,
# no root — C_BTT_DEC_03). OBEX framing is unchanged; this is purely a different byte stream.
# `supports_speed_change = False` — the serial `0x91` speed-raise is meaningless over RFCOMM.
#
# The socket recipe here is LIFTED VERBATIM from the live-verified scripts/test_bt_quick.py
# (Phase 7 PASS, 2026-07-17): INSECURE RFCOMM (BT_SECURITY_LOW) before connect + ≥8 s connect
# timeout. See skill oscill_bluetooth_transport for the full "why".

import logging
import re
import socket
import struct
import subprocess
import sys
from typing import Optional

from transport import Transport, TransportCapabilities, TransportError, UnsupportedCapability

log = logging.getLogger("rfcomm_transport")

# [C_BTT] Cross-platform guard. This whole RFCOMM recipe (AF_BLUETOOTH socket + the
# BT_SECURITY_LOW setsockopt + the (addr, channel) address tuple) is BlueZ-specific and
# live-verified on Linux only (skill oscill_bluetooth_transport). Windows/macOS either lack
# `socket.AF_BLUETOOTH` or use an incompatible address/security model, so calling `open()` there
# would raise a raw AttributeError/OSError. We gate on it and raise a clean, actionable
# BluetoothUnreachable instead. The portable BT path on Windows is the OS virtual COM port
# (pair the scope → Windows exposes an outgoing COMx) driven through SerialTransport — no BT
# socket needed. Native Windows RFCOMM is a separate, unverified feature (deferred).
_BT_RFCOMM_SUPPORTED = (
    sys.platform.startswith("linux")
    and hasattr(socket, "AF_BLUETOOTH")
    and hasattr(socket, "BTPROTO_RFCOMM")
)

# --- RFCOMM insecure-security socket option (SP_BTT_02_01, live-verified required) ---
# Without BT_SECURITY_LOW the kernel elevates auth/encryption on connect and the Oscill stalls
# → connect timeout. Mirrors the old Android app's createInsecureRfcommSocket.
_SOL_BLUETOOTH = 274
_BT_SECURITY = 4
_BT_SECURITY_LOW = 1

# RFCOMM bring-up is ~3.5 s; the connect budget must clear it (SP_BTT_02_01).
_CONNECT_TIMEOUT_S = 8.0

SPP_UUID_SHORT = "1101"  # Bluetooth Serial Port Profile
_FALLBACK_CHANNEL = 1

# [SP_BTT_02_11] Default device-name substring for paired-device discovery. The per-unit BD_ADDR
# varies between scopes but the name is stable ("Oscill DSO").
BT_NAME_DEFAULT = "Oscill"

# Matches a `bluetoothctl devices`/`paired-devices` line: "Device <BD_ADDR> <Name>".
_PAIRED_LINE_RE = re.compile(r"Device\s+([0-9A-Fa-f:]{17})\s+(.*)")

_RFCOMM_CAPABILITIES = TransportCapabilities(supports_speed_change=False)


class BluetoothUnreachable(TransportError):
    """[SP_BTT_02_09] The RFCOMM connect failed (host down / refused / timeout). The scope must be
    powered, connectable, and OS-paired (PIN 0000)."""


class ChannelResolutionError(TransportError):
    """[SP_BTT_02_07] SDP ran and the device is reachable, but exposes no SPP service."""


def find_paired_device_by_name(name_substr: str = BT_NAME_DEFAULT) -> Optional[str]:
    """[SP_BTT_02_11] Return the BD_ADDR of the first OS-paired device whose name contains
    `name_substr` (case-insensitive), or None if the tool is unavailable or nothing matches.

    Scope is the *paired* list — not an active inquiry — because Bluetooth Classic only connects to
    a bonded device (pairing is an OS precondition), mirroring the old Android app's
    GetPairedDevices(). Fast, no scan.
    """
    text = _run_bluetoothctl(["devices", "Paired"])
    if not text:
        # Older BlueZ exposes the paired list via the legacy subcommand.
        text = _run_bluetoothctl(["paired-devices"])
    if not text:
        return None
    needle = name_substr.lower()
    for line in text.splitlines():
        m = _PAIRED_LINE_RE.match(line.strip())
        if m and needle in m.group(2).strip().lower():
            log.info(f"paired device '{m.group(2).strip()}' matches '{name_substr}' → {m.group(1)}")
            return m.group(1)
    return None


def _run_bluetoothctl(args: list) -> Optional[str]:
    """Run `bluetoothctl <args>` and return combined stdout+stderr, or None on failure."""
    try:
        out = subprocess.run(
            ["bluetoothctl", *args],
            capture_output=True, text=True, timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.info(f"bluetoothctl {args} unavailable/timeout ({e.__class__.__name__})")
        return None
    return (out.stdout or "") + (out.stderr or "")


def resolve_spp_channel(address: str) -> int:
    """[SP_BTT_02_07 / SP_BTT_DEC_02] Determine the RFCOMM channel of the device's Serial Port
    (SPP, UUID 0x1101) service.

    Resolution order: (explicit channel is handled by the caller before this runs) → SDP query via
    `sdptool` → warned fallback to channel 1. `sdptool` returns the SPP record only while an ACL
    link is active; an empty result is tolerated (→ fallback), not treated as an error. The device
    advertises BOTH Object Push and Serial Port, so we target the Serial Port block specifically;
    the fallback-to-1 is a best-effort last resort (unverified) per the dual-service caveat.
    """
    channel = _sdp_query_spp_channel(address)
    if channel is not None:
        log.info(f"SDP resolved SPP RFCOMM channel {channel} for {address}")
        return channel
    log.warning(
        f"SDP did not return an SPP channel for {address} (no active ACL / sdptool missing); "
        f"falling back to unverified channel {_FALLBACK_CHANNEL}"
    )
    return _FALLBACK_CHANNEL


def _sdp_query_spp_channel(address: str) -> Optional[int]:
    """Run `sdptool browse` and parse the Serial Port service's RFCOMM channel. Returns None if
    sdptool is unavailable/timed out or no channel could be parsed (caller then falls back)."""
    try:
        out = subprocess.run(
            ["sdptool", "browse", "--tree", address],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.info(f"sdptool unavailable/timeout ({e.__class__.__name__}); skipping SDP")
        return None
    text = (out.stdout or "") + (out.stderr or "")
    if "Serial Port" not in text and SPP_UUID_SHORT not in text.replace("0x", ""):
        # Try the flat (non-tree) form as a fallback parse.
        try:
            out = subprocess.run(
                ["sdptool", "browse", address],
                capture_output=True, text=True, timeout=15,
            )
            text = (out.stdout or "") + (out.stderr or "")
        except Exception:
            pass
    return _parse_spp_channel(text)


def _parse_spp_channel(text: str) -> Optional[int]:
    """Parse `sdptool browse` output for the RFCOMM channel of the Serial Port (SPP) record.

    The SPP record is identified by its service-class UUID `0x1101` (or the class string "serial
    port") appearing within the record — NOT by the service *name*, which on this device is
    "Dev B", not "Serial Port" (SP_BTT_02_07 dual-service caveat). Each `Service RecHandle` line
    starts a new record; within a record the class list (carrying 0x1101) precedes the RFCOMM
    `Channel:` line, so the SPP flag is set before its channel is read. Returns the first SPP
    channel found; else the first channel seen anywhere (weak fallback); else None.
    """
    spp_first_channel: Optional[int] = None
    first_channel: Optional[int] = None
    cur_is_spp = False
    for line in text.splitlines():
        low = line.lower()
        if "service rechandle" in low:
            cur_is_spp = False  # new record boundary
        if "0x1101" in low or "serial port" in low:
            cur_is_spp = True
        m = re.search(r"channel[:/]?\s*(\d+)", low)
        if m:
            ch = int(m.group(1))
            if first_channel is None:
                first_channel = ch
            if cur_is_spp and spp_first_channel is None:
                spp_first_channel = ch
    return spp_first_channel if spp_first_channel is not None else first_channel


class RfcommTransport(Transport):
    """[SP_BTT] Bluetooth Classic RFCOMM/SPP byte stream over an AF_BLUETOOTH socket. Precondition:
    the device is OS-paired/bonded (PIN 0000) — pairing is not done by this software."""

    def __init__(self, address: str, channel: int, timeout: float = 3.0):
        self._address = address
        self._channel = channel
        self._read_timeout = timeout
        self._sock: Optional[socket.socket] = None

    # ---- state ----
    @property
    def is_open(self) -> bool:
        return self._sock is not None

    @property
    def read_timeout(self) -> float:
        return self._read_timeout

    @read_timeout.setter
    def read_timeout(self, value: float) -> None:
        self._read_timeout = value

    @property
    def capabilities(self) -> TransportCapabilities:
        return _RFCOMM_CAPABILITIES

    # ---- lifecycle ----
    def open(self) -> None:
        # [SP_BTT_02_01] INSECURE RFCOMM + generous connect timeout, then switch to the per-op
        # read timeout. Verbatim from the live-proven test_bt_quick.py recipe.
        if self.is_open:
            raise TransportError("RFCOMM socket already open; call close() first")
        if not _BT_RFCOMM_SUPPORTED:
            # [C_BTT] Non-Linux platform: the BlueZ RFCOMM socket recipe is unavailable. Fail with
            # an actionable message pointing to the portable COM-port path instead of an
            # AttributeError. On Windows: pair the scope in OS Bluetooth settings, then connect to
            # the auto-created outgoing COM port as a serial device (transport="serial").
            raise BluetoothUnreachable(
                f"Bluetooth RFCOMM is supported on Linux only (this platform is "
                f"'{sys.platform}'). On Windows/macOS: pair the scope in the OS, then connect to "
                f"its virtual serial (COM) port using transport='serial'."
            )
        try:
            sock = socket.socket(
                socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
            )
            sock.setsockopt(
                _SOL_BLUETOOTH, _BT_SECURITY,
                struct.pack("BB", _BT_SECURITY_LOW, 0),
            )
            sock.settimeout(_CONNECT_TIMEOUT_S)
            sock.connect((self._address, self._channel))
        except OSError as e:
            try:
                sock.close()  # type: ignore[possibly-undefined]
            except Exception:
                pass
            raise BluetoothUnreachable(
                f"RFCOMM connect to {self._address} ch{self._channel} failed: {e}. "
                f"Power on & make the scope connectable; pair it in the OS first (PIN 0000)."
            ) from e
        # Blocking with a bounded per-read timeout for normal I/O.
        sock.setblocking(True)
        sock.settimeout(self._read_timeout)
        self._sock = sock

    def close(self) -> None:
        # [SP_BTT_02_01] Best-effort + idempotent; never raises.
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:
            pass
        finally:
            self._sock = None

    # ---- I/O ----
    def read(self, n: int) -> bytes:
        # [SP_BTT_02_02 / DEC_04] Return up to n bytes; translate socket timeout → b"" (the driver's
        # _read_exact treats an empty return as "stop"). Raise TransportError on a real link error.
        assert self._sock is not None, "read before open"
        self._sock.settimeout(self._read_timeout)
        try:
            return self._sock.recv(n)
        except socket.timeout:
            return b""
        except OSError as e:
            raise TransportError(f"RFCOMM read failed (peer gone?): {e}") from e

    def write(self, data: bytes) -> None:
        # [SP_BTT_02_03] Full send — sendall loops until every byte is delivered.
        assert self._sock is not None, "write before open"
        try:
            self._sock.sendall(data)
        except OSError as e:
            raise TransportError(f"RFCOMM write failed (peer gone?): {e}") from e

    def reset_buffers(self) -> None:
        # [SP_BTT_02_04] Non-blocking drain of any pending inbound bytes. Never raises when open.
        if self._sock is None:
            return
        self._sock.setblocking(False)
        try:
            while True:
                if not self._sock.recv(4096):
                    break
        except (BlockingIOError, socket.timeout, OSError):
            pass
        finally:
            try:
                self._sock.setblocking(True)
                self._sock.settimeout(self._read_timeout)
            except OSError:
                pass

    def set_link_speed(self, baud: int) -> None:
        # [SP_BTT_02_05] RFCOMM has no host-side speed knob; the driver capability-gates this off,
        # so reaching here is a programming error.
        raise UnsupportedCapability("RFCOMM does not support link-speed change")

    def describe(self) -> str:
        return f"bluetooth:{self._address}/ch{self._channel}"
