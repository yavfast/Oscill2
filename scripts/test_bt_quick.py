#!/usr/bin/env python3
# [C_BTT / SP_BTT / PL_BTT Phase 7] Quick live check of the Oscill over Bluetooth (RFCOMM/SPP).
#
# Standalone diagnostic — NOT a unit test (requires the scope powered on + OS-paired). It reaches
# the device over a Bluetooth Classic RFCOMM socket and drives the unchanged OBEX driver
# (OscillClient), proving the OBEX-over-BT path end-to-end. Since the full transport refactor
# landed (Phases 1-3), this now uses the PRODUCTION RfcommTransport + OscillClient directly — it no
# longer carries its own socket/SDP prototype (that logic moved into web_oscill/rfcomm_transport.py
# verbatim).
#
# Usage:
#   scripts/test_bt_quick.py [--addr XX:XX:XX:XX:XX:XX] [--channel N] [--frame] [--timeout S]
#   OSCILL_BT_ADDR / OSCILL_BT_CHANNEL env vars are honoured as defaults.
#
# Exit codes: 0 = PASS (handshake + property read), 1 = device unreachable, 2 = protocol failure.

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "web_oscill"))

from oscill_client import OscillClient  # noqa: E402  (path set above)
from rfcomm_transport import (  # noqa: E402
    BluetoothUnreachable,
    RfcommTransport,
    resolve_spp_channel,
)

DEFAULT_ADDR = "20:13:04:24:20:55"   # Oscill DSO (verified paired to this host)


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

    # 1) Channel resolution (explicit > SDP > fallback 1) --------------------
    if args.channel is not None:
        channel = args.channel
        print(f"  [cfg] using explicit channel {channel}")
    else:
        channel = resolve_spp_channel(args.addr)
        print(f"  [sdp] resolved/fallback RFCOMM channel {channel}")

    # 2) RFCOMM connect (production RfcommTransport: insecure + 8 s connect budget) ---
    t0 = time.time()
    transport = RfcommTransport(args.addr, channel, timeout=args.timeout)
    try:
        transport.open()
    except BluetoothUnreachable as e:
        print(f"  ✗ RFCOMM connect failed: {e}")
        print("    → Is the scope powered on and connectable? Pair it in the OS first "
              "(bluetoothctl pair/trust). This mirrors the 'Host is down' precondition.")
        return 1
    print(f"  ✓ RFCOMM connected (channel {channel}, {1000*(time.time()-t0):.0f} ms)")

    # 3) OBEX handshake over the socket (OscillClient framing unchanged) ------
    client = OscillClient(transport, timeout=args.timeout)
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
        client.close(restore=False)

    print("=== PASS ===" if rc == 0 else f"=== FAIL (rc={rc}) ===")
    return rc


if __name__ == "__main__":
    sys.exit(main())
