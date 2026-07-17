#!/usr/bin/env python3
"""
[C_BTT / SP_BTT_02_09] Standalone hardware-free test of DeviceService.connect over a fake
Bluetooth transport.

Per project rule PythonTestsAreStandaloneScripts: no pytest, runnable as
`python3 scripts/test_bluetooth_connect.py`. Prints PASS/FAIL per case, exits non-zero on failure.
No socket / hardware is touched — DeviceService.build_transport is monkeypatched to return the
FakeObexTransport from test_transport.py.

Covers (SP_BTT_05_01 / 05_02 / 05_04):
  - BT happy path: connect succeeds, status is connected, NO speed-raise attempted
  - ConfigError when transport=bluetooth but no address anywhere
  - error mapping: BluetoothUnreachable propagates from a failed open()
"""

import os
import sys

_SCRIPTS = os.path.dirname(__file__)
sys.path.insert(0, _SCRIPTS)
sys.path.insert(0, os.path.join(_SCRIPTS, "..", "web_oscill"))

from test_transport import FakeObexTransport  # noqa: E402

import device_service  # noqa: E402
from device_service import DeviceService  # noqa: E402
from endpoints import (  # noqa: E402
    BluetoothEndpoint,
    ConfigError,
    DeviceNotFound,
    SerialEndpoint,
    resolve_endpoint,
)
from rfcomm_transport import BluetoothUnreachable  # noqa: E402

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


def _patch_build_transport(factory):
    """Swap device_service.build_transport for a fake factory; return a restore callable."""
    orig = device_service.build_transport
    device_service.build_transport = factory
    return lambda: setattr(device_service, "build_transport", orig)


def test_bt_happy_path_no_speed_raise():
    print("BT happy path: connects, no speed-raise (SP_BTT_05_02):")
    fake = FakeObexTransport(supports_speed_change=False)
    restore = _patch_build_transport(lambda ep, timeout=3.0: fake)
    svc = DeviceService()
    try:
        res = svc.connect(BluetoothEndpoint("20:13:04:24:20:55", 1))
        check(res.get("is_connected") is True, "status is_connected == True")
        check(svc.is_connected(), "service reports connected")
        check(fake.set_link_speed_calls == [], "no set_link_speed call over BT")
        speed_pkts = [w for w in fake.device.writes if w and w[0] == 0x91]
        check(speed_pkts == [], "no 0x91 speed packet sent over BT")
        check(res.get("transport") == "fake-obex", "response carries transport label")
    finally:
        try:
            svc.disconnect()
        except Exception:
            pass
        svc.shutdown()
        restore()


def test_config_error_no_address_no_name_match():
    print("ConfigError when bluetooth + no address AND no name match (SP_BTT_02_11 / 05_04):")
    # No explicit address, no OSCILL_BT_ADDR, and a name pattern that matches no paired device →
    # ConfigError. (With the default "Oscill" name this host WOULD resolve the paired scope — the
    # new name-discovery feature — so we force a non-matching name to exercise the error path.)
    saved_addr = os.environ.pop("OSCILL_BT_ADDR", None)
    saved_name = os.environ.get("OSCILL_BT_NAME")
    os.environ["OSCILL_BT_NAME"] = "NoSuchDeviceXYZ"
    try:
        expect_raises(ConfigError, lambda: resolve_endpoint(transport="bluetooth"),
                      "resolve_endpoint(bluetooth, no addr, no name match) → ConfigError")
        os.environ["OSCILL_TRANSPORT"] = "bluetooth"
        svc = DeviceService()
        try:
            expect_raises(ConfigError, lambda: svc.connect(),
                          "connect() env bluetooth, no addr, no name match → ConfigError")
        finally:
            svc.shutdown()
    finally:
        os.environ.pop("OSCILL_TRANSPORT", None)
        if saved_name is not None:
            os.environ["OSCILL_BT_NAME"] = saved_name
        else:
            os.environ.pop("OSCILL_BT_NAME", None)
        if saved_addr is not None:
            os.environ["OSCILL_BT_ADDR"] = saved_addr


def test_error_mapping_unreachable():
    print("Error mapping: failed open() → BluetoothUnreachable (SP_BTT_05_04):")
    fake = FakeObexTransport(
        supports_speed_change=False,
        open_should_raise=BluetoothUnreachable("Host is down"),
    )
    restore = _patch_build_transport(lambda ep, timeout=3.0: fake)
    svc = DeviceService()
    try:
        expect_raises(BluetoothUnreachable,
                      lambda: svc.connect(BluetoothEndpoint("20:13:04:24:20:55", 1)),
                      "connect over unreachable BT → BluetoothUnreachable")
        check(not svc.is_connected(), "service stays disconnected after failed connect")
    finally:
        svc.shutdown()
        restore()


def _patch(name, value):
    """Swap a device_service module attribute; return a restore callable."""
    orig = getattr(device_service, name)
    setattr(device_service, name, value)
    return lambda: setattr(device_service, name, orig)


def test_auto_prefers_usb():
    print("connect_auto prefers USB when present (SP_BTT_02_12):")
    serial_fake = FakeObexTransport(supports_speed_change=True)

    def build(ep, timeout=3.0):
        if isinstance(ep, SerialEndpoint):
            return serial_fake
        raise AssertionError("BT must not be built when USB succeeds")

    r1 = _patch("build_transport", build)
    # A paired BT device exists, but USB should win before BT is even attempted.
    r2 = _patch("resolve_bt_address_optional", lambda: "20:13:04:24:20:55")
    svc = DeviceService()
    try:
        res = svc.connect_auto()
        check(res.get("transport_kind") == "serial", "connected over serial (USB)")
        check(svc.get_status().get("transport_kind") == "serial", "get_status reports serial")
    finally:
        svc.disconnect(); svc.shutdown(); r2(); r1()


def test_auto_falls_back_to_bt():
    print("connect_auto falls back to BT when USB absent (SP_BTT_02_12):")
    bt_fake = FakeObexTransport(supports_speed_change=False)

    def build(ep, timeout=3.0):
        if isinstance(ep, SerialEndpoint):
            raise DeviceNotFound("no CP210x")
        return bt_fake

    r1 = _patch("build_transport", build)
    r2 = _patch("resolve_bt_address_optional", lambda: "20:13:04:24:20:55")
    svc = DeviceService()
    try:
        res = svc.connect_auto()
        check(res.get("transport_kind") == "bluetooth", "fell back to BT")
        check(svc.get_status().get("transport_kind") == "bluetooth", "get_status reports bluetooth")
    finally:
        svc.disconnect(); svc.shutdown(); r2(); r1()


def test_auto_no_device_at_all():
    print("connect_auto with neither USB nor paired BT → DeviceNotFound (SP_BTT_02_12):")

    def build(ep, timeout=3.0):
        raise DeviceNotFound("no CP210x")

    r1 = _patch("build_transport", build)
    r2 = _patch("resolve_bt_address_optional", lambda: None)  # no paired BT → serial-only candidate
    svc = DeviceService()
    try:
        expect_raises(DeviceNotFound, lambda: svc.connect_auto(),
                      "no USB + no paired BT → DeviceNotFound")
        check(not svc.is_connected(), "stays disconnected")
    finally:
        svc.shutdown(); r2(); r1()


def test_status_transport_kind_null_when_disconnected():
    print("get_status transport_kind is null when disconnected (SP_BTT_02_09):")
    svc = DeviceService()
    try:
        check(svc.get_status().get("transport_kind") is None, "disconnected → transport_kind null")
    finally:
        svc.shutdown()


def main() -> int:
    test_bt_happy_path_no_speed_raise()
    test_config_error_no_address_no_name_match()
    test_error_mapping_unreachable()
    test_auto_prefers_usb()
    test_auto_falls_back_to_bt()
    test_auto_no_device_at_all()
    test_status_transport_kind_null_when_disconnected()
    print("-" * 60)
    if _failures:
        print(f"RESULT: FAIL ({_failures} check(s) failed)")
        return 1
    print("RESULT: PASS (all cases passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
