# [C_BTT / SP_BTT_01_03 / SP_BTT_01_04 / SP_BTT_02_01..06] Transport abstraction.
#
# The byte-stream contract consumed ONLY by the OBEX driver (OscillClient). It replaces the
# driver's direct `serial.Serial` handle so the same OBEX framing can run over USB serial or a
# Bluetooth RFCOMM socket without the driver knowing which. OBEX framing is unchanged; a
# Transport is purely "where bytes enter and leave the driver".
#
# This module is Layer 0 and intentionally dependency-free (no serial / no socket imports) so the
# abstract contract stays link-agnostic (rule LayerDependencyDirection, PL_BTT_DEC_01).

import abc
from dataclasses import dataclass


class TransportError(Exception):
    """Raised when a transport link cannot be established, drops mid-operation, or the peer is
    gone. Surfaces to the acquisition loop, which self-heals by disconnecting after N errors
    (rule AcquisitionLoopSelfHealingDisconnect)."""


class UnsupportedCapability(TransportError):
    """Raised when an operation is invoked on a transport that does not support it — e.g.
    `set_link_speed` on RFCOMM (`supports_speed_change = False`). The driver capability-gates such
    calls, so this is a defensive guard, not an expected control-flow path."""


@dataclass(frozen=True)
class TransportCapabilities:
    """[SP_BTT_01_03] Static capability descriptor a transport exposes so the driver can adapt
    without knowing the concrete link type. Constant for the lifetime of a transport instance."""

    # Whether `set_link_speed` is meaningful; gates the OBEX `0x91` speed-raise sequence.
    supports_speed_change: bool


class Transport(abc.ABC):
    """[SP_BTT_01_04] Abstract byte-stream contract. Concrete implementations: SerialTransport
    (USB) and RfcommTransport (Bluetooth Classic / SPP)."""

    # ---- lifecycle / state ----
    @property
    @abc.abstractmethod
    def is_open(self) -> bool:
        """True between `open()` and `close()`."""

    @property
    @abc.abstractmethod
    def read_timeout(self) -> float:
        """Current blocking-read budget in seconds; the driver adjusts it per operation."""

    @read_timeout.setter
    @abc.abstractmethod
    def read_timeout(self, value: float) -> None:
        ...

    @property
    @abc.abstractmethod
    def capabilities(self) -> TransportCapabilities:
        ...

    # ---- contracts (SP_BTT_02) ----
    @abc.abstractmethod
    def open(self) -> None:
        """[SP_BTT_02_01] Establish the link. Raises TransportError if it cannot be established;
        raises TransportError if already open (mirrors the OscillClient open guard)."""

    @abc.abstractmethod
    def close(self) -> None:
        """[SP_BTT_02_01] Tear down the link, best-effort. Idempotent; never raises."""

    @abc.abstractmethod
    def read(self, n: int) -> bytes:
        """[SP_BTT_02_02 / DEC_04] Read up to `n` bytes, bounded by `read_timeout`. On timeout with
        no data returns b"" (never raises on timeout) — the driver's `_read_exact` treats an empty
        return as "stop". Raises TransportError only on a genuine link error."""

    @abc.abstractmethod
    def write(self, data: bytes) -> None:
        """[SP_BTT_02_03] Write ALL bytes before returning (no short write). Raises TransportError
        if the link is closed or the peer is gone."""

    @abc.abstractmethod
    def reset_buffers(self) -> None:
        """[SP_BTT_02_04] Discard any pending inbound/outbound bytes. Never raises when open."""

    @abc.abstractmethod
    def set_link_speed(self, baud: int) -> None:
        """[SP_BTT_02_05] Change the host-side link speed. Capability-gated: implementations that
        report `supports_speed_change = False` raise UnsupportedCapability."""

    @abc.abstractmethod
    def describe(self) -> str:
        """[SP_BTT_02_06] Stable, human-readable label for logs/errors, e.g.
        `serial:/dev/ttyUSB0@115200` or `bluetooth:20:13:04:24:20:55/ch1`."""
