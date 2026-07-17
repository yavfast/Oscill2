# [C_BTT / SP_BTT_02_*] SerialTransport — the USB (CP210x) realization of Transport.
#
# Behaviour-preserving extraction of the driver's former `serial.Serial` handling: this class now
# owns the pyserial port, the host baud, and the CP210x auto-detect. It is the ORIGINAL code path
# — reverting the feature to serial-only means keeping just this transport (SP_BTT_06_01).
#
# USB-only concerns live here: baud + `set_link_speed` (the host side of the OBEX `0x91`
# speed-raise) and `auto_find_port`. `supports_speed_change = True`.

import time
from typing import Optional

import serial
from serial.tools import list_ports

from transport import Transport, TransportCapabilities, TransportError

# CP210x (Silicon Labs) USB VID/PID used to auto-detect the scope's serial port.
VENDOR_ID = 0x10C4
PRODUCT_ID = 0x840E

_SERIAL_CAPABILITIES = TransportCapabilities(supports_speed_change=True)


class SerialTransport(Transport):
    """[SP_BTT] pyserial-backed byte stream. Constructed with a port (or None for auto-detect
    handled by the factory) + baud; the driver drives read/write/reset/timeout/speed through the
    Transport contract, unaware it is a UART."""

    def __init__(self, port: str, baud: int = 115200, timeout: float = 3.0):
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._ser: Optional[serial.Serial] = None

    # ---- state ----
    @property
    def is_open(self) -> bool:
        return self._ser is not None and bool(getattr(self._ser, "is_open", False))

    @property
    def read_timeout(self) -> float:
        if self._ser is not None and self._ser.timeout is not None:
            return self._ser.timeout
        return self._timeout

    @read_timeout.setter
    def read_timeout(self, value: float) -> None:
        self._timeout = value
        if self._ser is not None:
            self._ser.timeout = value

    @property
    def capabilities(self) -> TransportCapabilities:
        return _SERIAL_CAPABILITIES

    # ---- lifecycle ----
    def open(self) -> None:
        # [SP_BTT_02_01] Re-open over a live port would leak the previous handle (SP_OCL guard).
        if self.is_open:
            raise TransportError("Serial port already open; call close() first")
        try:
            self._ser = serial.Serial(self._port, self._baud, timeout=self._timeout)
        except (serial.SerialException, OSError) as e:
            raise TransportError(f"serial open failed on {self._port}: {e}") from e

    def close(self) -> None:
        # [SP_BTT_02_01] Best-effort + idempotent; never raises.
        try:
            if self._ser is not None and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass
        finally:
            self._ser = None

    # ---- I/O ----
    def read(self, n: int) -> bytes:
        # [SP_BTT_02_02] pyserial's read already returns b"" on timeout, so the b""-on-timeout
        # invariant (DEC_04) holds without translation.
        assert self._ser is not None, "read before open"
        try:
            return self._ser.read(n)
        except (serial.SerialException, OSError) as e:
            raise TransportError(f"serial read failed: {e}") from e

    def write(self, data: bytes) -> None:
        # [SP_BTT_02_03] pyserial's write is blocking and writes all bytes.
        assert self._ser is not None, "write before open"
        try:
            self._ser.write(data)
        except (serial.SerialException, OSError) as e:
            raise TransportError(f"serial write failed: {e}") from e

    def reset_buffers(self) -> None:
        # [SP_BTT_02_04] Never raises when open.
        if self._ser is not None:
            try:
                self._ser.reset_input_buffer()
                self._ser.reset_output_buffer()
            except Exception:
                pass

    def set_link_speed(self, baud: int) -> None:
        # [SP_BTT_02_05] Host-side baud switch (the driver builds the device-side `0x91` packet
        # itself). Records the baud so a subsequent open() uses it; if open, switches live, lets
        # the device UART settle, and flushes stale bytes — preserving the former _set_host_baud.
        self._baud = baud
        if self._ser is not None:
            self._ser.baudrate = baud
            time.sleep(0.05)  # let the device's UART settle at the new rate
            self.reset_buffers()

    def describe(self) -> str:
        return f"serial:{self._port}@{self._baud}"

    # ---- device/port utils (USB-only concern) ----
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
