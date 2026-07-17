# [C_BTT / SP_BTT_01_01, 01_02, 01_05, 02_08, 03_01] Connection endpoint model + factory.
#
# Immutable value types describing WHERE and HOW to reach the device, the env-driven default
# resolver, and the factory that turns an endpoint into an open-able Transport. This is the single
# validated input to the connection path; the legacy (port, baud) form maps onto SerialEndpoint.
#
# Validation (BD_ADDR format, channel range, required address) happens at construction / resolution
# — before ANY hardware access (SP_BTT_03_01).

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Union

from serial_transport import SerialTransport
from transport import Transport

# BD_ADDR: 6 colon-separated hex octets, case-insensitive (SP_BTT_03_01).
_BD_ADDR_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
_CHANNEL_MIN, _CHANNEL_MAX = 1, 30


class ConfigError(Exception):
    """[SP_BTT_02_09] Misconfiguration that must be fixed by the caller before a connection can be
    attempted — e.g. transport=bluetooth with no address anywhere. Raised before any I/O."""


class DeviceNotFound(Exception):
    """[SP_BTT_02_09] Serial auto-detect found no CP210x device."""


class TransportKind(Enum):
    """[SP_BTT_01_01] The physical link selector."""

    SERIAL = "serial"
    BLUETOOTH = "bluetooth"


@dataclass(frozen=True)
class SerialEndpoint:
    """[SP_BTT_01_02] USB serial connection descriptor. port=None ⇒ auto-detect."""

    port: Optional[str] = None
    baud: int = 115200
    kind: TransportKind = field(default=TransportKind.SERIAL, init=False)

    def __post_init__(self) -> None:
        if self.baud <= 0:
            raise ValueError(f"baud must be > 0, got {self.baud}")

    def describe(self) -> str:
        return f"serial:{self.port or 'auto'}@{self.baud}"


@dataclass(frozen=True)
class BluetoothEndpoint:
    """[SP_BTT_01_02] Bluetooth Classic (RFCOMM/SPP) connection descriptor. channel=None ⇒ resolve
    via SDP (SP_BTT_02_07)."""

    address: str
    channel: Optional[int] = None
    kind: TransportKind = field(default=TransportKind.BLUETOOTH, init=False)

    def __post_init__(self) -> None:
        if not self.address or not _BD_ADDR_RE.match(self.address):
            raise ValueError(
                f"invalid Bluetooth address '{self.address}'; expected XX:XX:XX:XX:XX:XX"
            )
        if self.channel is not None and not (_CHANNEL_MIN <= self.channel <= _CHANNEL_MAX):
            raise ValueError(
                f"RFCOMM channel out of range ({_CHANNEL_MIN}..{_CHANNEL_MAX}): {self.channel}"
            )

    def describe(self) -> str:
        return f"bluetooth:{self.address}/ch{self.channel if self.channel is not None else '?'}"


ConnectionEndpoint = Union[SerialEndpoint, BluetoothEndpoint]


def resolve_default_endpoint(port: Optional[str] = None, baud: int = 115200) -> ConnectionEndpoint:
    """[SP_BTT_02_08] Resolve the endpoint used when a caller connects without an explicit one
    (auto-connect / ensure_connected). An explicit legacy port wins; otherwise the env defaults
    (OSCILL_TRANSPORT / OSCILL_BT_ADDR / OSCILL_BT_CHANNEL) select serial-auto or bluetooth."""
    # Explicit legacy call — a concrete port ("auto"/"" mean auto-detect).
    if port and port != "auto":
        return SerialEndpoint(port=port, baud=baud)
    # env OSCILL_TRANSPORT default is `auto`; as a SINGLE endpoint that resolves to serial-auto
    # (USB, the preferred/faster link). The multi-candidate USB→BT fallback is connect_auto
    # ([SP_BTT_02_12]), not this single-endpoint resolver.
    kind = os.environ.get("OSCILL_TRANSPORT", "auto").strip().lower()
    if kind == "bluetooth":
        addr = resolve_bt_address(os.environ.get("OSCILL_BT_ADDR"))
        ch_env = os.environ.get("OSCILL_BT_CHANNEL")
        try:
            channel = int(ch_env) if ch_env else None
        except ValueError:
            raise ConfigError(f"OSCILL_BT_CHANNEL must be an integer, got '{ch_env}'")
        return BluetoothEndpoint(address=addr, channel=channel)
    return SerialEndpoint(port=None, baud=baud)  # serial auto-detect (auto / serial)


def resolve_endpoint(
    *,
    transport: Optional[str] = None,
    port: Optional[str] = None,
    baud: int = 115200,
    address: Optional[str] = None,
    channel: Optional[int] = None,
) -> ConnectionEndpoint:
    """[SP_BTT_02_10 / 03_01] Build a validated ConnectionEndpoint from loose request/parameters.
    When `transport` is None, falls back to the env/legacy default resolver. Rejects unknown
    transport kinds and missing BT address before any hardware access."""
    if transport is None:
        return resolve_default_endpoint(port, baud)
    kind = transport.strip().lower()
    if kind == "serial":
        return SerialEndpoint(port=port, baud=baud)
    if kind == "bluetooth":
        # [SP_BTT_02_11] explicit → OSCILL_BT_ADDR → name match among paired devices.
        addr = resolve_bt_address(address)
        return BluetoothEndpoint(address=addr, channel=channel)
    raise ValueError(f"unknown transport '{transport}'; expected 'serial' or 'bluetooth'")


def resolve_bt_address(address: Optional[str] = None) -> str:
    """[SP_BTT_02_11] Resolve a Bluetooth device address: explicit argument → `OSCILL_BT_ADDR` →
    name match among OS-paired devices (`OSCILL_BT_NAME`, default "Oscill"). Raises ConfigError when
    nothing resolves."""
    if address:
        return address
    env_addr = os.environ.get("OSCILL_BT_ADDR")
    if env_addr:
        return env_addr
    from rfcomm_transport import BT_NAME_DEFAULT, find_paired_device_by_name

    name = os.environ.get("OSCILL_BT_NAME", BT_NAME_DEFAULT)
    found = find_paired_device_by_name(name)
    if found:
        return found
    raise ConfigError(
        f"no Bluetooth address given and no paired device matching '{name}' found; "
        f"pair the scope in the OS first or set OSCILL_BT_ADDR"
    )


def resolve_bt_address_optional() -> Optional[str]:
    """[SP_BTT_02_12] Best-effort address resolution for the auto path — returns None instead of
    raising when no Bluetooth device is configured/paired (auto then stays serial-only)."""
    try:
        return resolve_bt_address(None)
    except ConfigError:
        return None


def build_transport(endpoint: ConnectionEndpoint, timeout: float = 3.0) -> Transport:
    """[SP_BTT_02_08] Turn a ConnectionEndpoint into an unopened Transport. Serial auto-detects the
    port (DeviceNotFound if none); Bluetooth resolves the SPP channel via SDP when unspecified. No
    link is opened here — the driver's open_and_handshake does that."""
    if isinstance(endpoint, SerialEndpoint):
        port = endpoint.port or SerialTransport.auto_find_port()
        if not port:
            raise DeviceNotFound("No CP210x device found; connect USB or specify a port")
        return SerialTransport(port, endpoint.baud, timeout)
    if isinstance(endpoint, BluetoothEndpoint):
        # Imported lazily so the serial-only path never pulls in the RFCOMM/socket module.
        from rfcomm_transport import RfcommTransport, resolve_spp_channel

        channel = endpoint.channel if endpoint.channel is not None else resolve_spp_channel(
            endpoint.address
        )
        return RfcommTransport(endpoint.address, channel, timeout)
    raise ConfigError(f"unsupported endpoint type: {type(endpoint).__name__}")
