#!/usr/bin/env python3
"""
[SP_DSV lifecycle] Standalone hardware-free tests for DeviceService idle-disconnect +
auto-reconnect.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_lifecycle.py`. Exits non-zero on any failure. No hardware — build_transport is
monkeypatched to the FakeObexTransport from test_transport.py; the monitor decision helpers
(`_maybe_idle_disconnect` / `_maybe_reconnect`) are driven directly for deterministic timing.

Covers: idle-disconnect fires (and does NOT arm reconnect); error → reconnect replays the same
target; user disconnect cancels a pending reconnect; reconnect is bounded (gives up); connection_state.
"""

import os
import sys
import time

_SCRIPTS = os.path.dirname(__file__)
sys.path.insert(0, _SCRIPTS)
sys.path.insert(0, os.path.join(_SCRIPTS, "..", "web_oscill"))

from test_transport import FakeObexTransport  # noqa: E402

import device_service  # noqa: E402
from device_service import DeviceService  # noqa: E402
from endpoints import BluetoothEndpoint, DeviceNotFound, SerialEndpoint  # noqa: E402

_failures = 0


def check(cond: bool, label: str) -> None:
    global _failures
    if cond:
        print(f"  [PASS] {label}")
    else:
        _failures += 1
        print(f"  [FAIL] {label}")


def _patch(name, value):
    orig = getattr(device_service, name)
    setattr(device_service, name, value)
    return lambda: setattr(device_service, name, orig)


def test_idle_disconnect_fires_no_reconnect():
    print("Idle-disconnect fires after timeout and does NOT arm reconnect:")
    r = _patch("build_transport", lambda ep, timeout=3.0: FakeObexTransport(supports_speed_change=True))
    svc = DeviceService()
    try:
        svc._idle_disconnect_s = 0.5
        svc.connect(SerialEndpoint(port="/dev/ttyUSB0"))
        check(svc.is_connected(), "connected")
        svc.stop()                                   # acquisition stopped → idle clock starts
        svc._idle_since = time.monotonic() - 10      # pretend it has been idle a while
        svc._maybe_idle_disconnect()                 # drive the monitor decision directly
        check(not svc.is_connected(), "auto-disconnected after idle timeout")
        check(svc._pending_reconnect is False, "idle-disconnect did NOT arm reconnect")
        check(svc.get_status().get("connection_state") == "disconnected", "state = disconnected")
    finally:
        svc.shutdown(); r()


def test_idle_disconnect_off_when_acquiring():
    print("Idle-disconnect never fires while acquiring:")
    r = _patch("build_transport", lambda ep, timeout=3.0: FakeObexTransport(supports_speed_change=True))
    svc = DeviceService()
    try:
        svc._idle_disconnect_s = 0.5
        svc.connect(SerialEndpoint(port="/dev/ttyUSB0"))  # auto-starts acquisition
        svc._idle_since = time.monotonic() - 10           # stale, but we are acquiring
        svc._maybe_idle_disconnect()
        check(svc.is_connected(), "stays connected while acquiring")
    finally:
        svc.shutdown(); r()


def test_error_reconnect_replays_target():
    print("Error → reconnect replays the same target (SP_DSV):")
    r = _patch("build_transport", lambda ep, timeout=3.0: FakeObexTransport(supports_speed_change=False))
    svc = DeviceService()
    try:
        target = BluetoothEndpoint("20:13:04:24:20:55", 1)
        svc.connect(target)
        check(svc.get_status().get("transport_kind") == "bluetooth", "connected over BT")
        # Simulate the acq-loop error path: drop the link + arm reconnect (as _acq_loop does).
        svc._disconnect_internal()
        svc._pending_reconnect = True
        svc._reconnect_attempts = 0
        svc._next_reconnect_ts = 0.0
        check(not svc.is_connected(), "dropped (error)")
        svc._maybe_reconnect()                        # drive one reconnect tick
        check(svc.is_connected(), "reconnected over the same target")
        check(svc.get_status().get("transport_kind") == "bluetooth", "same link (bluetooth)")
        check(svc._pending_reconnect is False, "reconnect disarmed on success")
    finally:
        svc.shutdown(); r()


def test_user_disconnect_cancels_reconnect():
    print("User disconnect cancels a pending reconnect:")
    r = _patch("build_transport", lambda ep, timeout=3.0: FakeObexTransport(supports_speed_change=True))
    svc = DeviceService()
    try:
        svc.connect(SerialEndpoint(port="/dev/ttyUSB0"))
        svc._pending_reconnect = True                 # pretend an error armed it
        svc.disconnect()                              # user action
        check(svc._pending_reconnect is False, "pending reconnect cleared by user disconnect")
        svc._maybe_reconnect()                        # must be a no-op
        check(not svc.is_connected(), "stays disconnected (no auto-reconnect)")
    finally:
        svc.shutdown(); r()


def test_reconnect_bounded_gives_up():
    print("Auto-reconnect is bounded (gives up after max attempts):")
    r = _patch("build_transport", lambda ep, timeout=3.0: (_ for _ in ()).throw(DeviceNotFound("no dev")))
    svc = DeviceService()
    try:
        svc._reconnect_target = SerialEndpoint(port=None)
        svc._pending_reconnect = True
        svc._reconnect_attempts = 0
        svc._reconnect_backoff = 1.0
        for _ in range(svc._RECONNECT_MAX_ATTEMPTS + 2):
            svc._next_reconnect_ts = 0.0              # force each tick to attempt
            svc._maybe_reconnect()
        check(svc._pending_reconnect is False, "gave up (pending cleared)")
        check(svc._reconnect_attempts == svc._RECONNECT_MAX_ATTEMPTS,
              f"stopped at {svc._RECONNECT_MAX_ATTEMPTS} attempts")
        check(svc.get_status().get("connection_state") == "disconnected", "state = disconnected")
    finally:
        svc.shutdown(); r()


def test_user_disconnect_wins_epoch_race():
    print("User disconnect wins the epoch race vs acq-loop error-arming:")
    r = _patch("build_transport", lambda ep, timeout=3.0: FakeObexTransport(supports_speed_change=True))
    svc = DeviceService()
    try:
        svc.connect(SerialEndpoint(port="/dev/ttyUSB0"))
        acq_epoch = svc._lifecycle_epoch          # what _acq_loop captured for this session
        svc.disconnect()                          # user action → bumps epoch, disarms
        check(svc._lifecycle_epoch != acq_epoch, "user disconnect bumped the lifecycle epoch")
        # Replay the EXACT guard the acq-loop uses when arming on its 5th error:
        with svc._dev_lock:
            if svc._lifecycle_epoch == acq_epoch and svc._reconnect_target is not None:
                svc._pending_reconnect = True     # must NOT run — epoch is stale
        check(svc._pending_reconnect is False, "stale-epoch arming refused → no resurrection")
        svc._maybe_reconnect()
        check(not svc.is_connected(), "device stays disconnected")
    finally:
        svc.shutdown(); r()


def test_connection_state_reconnecting():
    print("connection_state = 'reconnecting' while armed + disconnected:")
    svc = DeviceService()
    try:
        svc._pending_reconnect = True
        check(svc.get_status().get("connection_state") == "reconnecting",
              "armed + disconnected → 'reconnecting'")
        svc._pending_reconnect = False
        check(svc.get_status().get("connection_state") == "disconnected",
              "disarmed → 'disconnected'")
    finally:
        svc.shutdown()


def main() -> int:
    test_idle_disconnect_fires_no_reconnect()
    test_idle_disconnect_off_when_acquiring()
    test_error_reconnect_replays_target()
    test_user_disconnect_cancels_reconnect()
    test_reconnect_bounded_gives_up()
    test_user_disconnect_wins_epoch_race()
    test_connection_state_reconnecting()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} check(s) failed)")
        return 1
    print("RESULT: PASS (all cases passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
